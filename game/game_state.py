import random
import pygame
import math
from typing import List, Tuple, Optional, Dict, Any
from models.line import Line
from models.station import Station
from models.train import Train
from models.passenger import Passenger

# --- Stałe ---
STATION_RADIUS: int = 20
LINE_COLORS: List[Tuple[int, int, int]] = [
    (255, 0, 0),    # czerwony
    (0, 255, 0),    # zielony
    (0, 0, 255),    # niebieski
    (255, 165, 0),  # pomarańczowy
    (128, 0, 128),  # fioletowy
]
TRAIN_ICON_SIZE: int = 30
TRAIN_ICON_PADDING: int = 10
INITIAL_UNLOCKED_LINES: int = 3
WEEK_DAYS: List[str] = [
    "Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"
]
STATION_SPAWN_MARGIN: int = 60  # minimalna odległość od krawędzi planszy przy generowaniu stacji
STATION_MIN_DIST: int = 80      # minimalny dystans między stacjami
POISSON_ATTEMPTS_PER_STATION: int = 15
POISSON_RADIUS: int = 50
POISSON_TRIANGLE_TRIALS: int = 20
MIN_TRIANGLE_HEIGHT: int = 20
MAX_TRAINS_PER_LINE: int = 4
MAX_PASSENGERS_ON_STATION: int = 8
OVERLOAD_TIMER_SECONDS: float = 5.0
MIN_SPAWN_INTERVAL_MS: int = 1500
DEFAULT_BASE_SPAWN_INTERVAL: int = 30000


class GameState:
    """
    Klasa główna przechowująca stan gry, obsługująca logikę oraz interakcje użytkownika.
    """

    INGAME_DAY_MS: int = 60 * 1000
    UNLOCK_CYCLE_DAYS: int = 7

    def __init__(self, width: int, height: int) -> None:
        self.width: int = int(width * 1.5)
        self.height: int = int(height * 1.5)
        self.river_y: int = self.height // 2
        self.river_margin: int = 100
        self.stations: List[Station] = []
        self.stations: List[Station] = self.generate_initial_stations()
        self.selected_station: Optional[Station] = None

        self.lines: List[Line] = []
        self.color_to_line: Dict[Tuple[int, int, int], Line] = {}
        self.unlocked_colors: List[Tuple[int, int, int]] = LINE_COLORS[:INITIAL_UNLOCKED_LINES]
        self.selected_line_color: Optional[Tuple[int, int, int]] = None
        self.selected_line: Optional[Line] = None
        self.active_line: Optional[Line] = None

        self.trains: List[Train] = []
        self.available_trains: int = 2
        self.available_carriages: int = 0

        self.dragged_segment: Optional[Tuple[Any, Any]] = None
        self.dragged_line: Optional[Line] = None
        self.hovered_segment: Optional[Tuple[Line, Any, Any]] = None

        self.dragging_train_icon: bool = False
        self.dragging_carriage_icon: bool = False

        self.elapsed_time: int = 0
        self.total_days_passed: int = 0
        self.passenger_count: int = 0
        self.total_score: int = 0
        self.week_day_index: int = 0
        self.week_number: int = 1

        self.station_spawn_timer: int = 0
        self.base_spawn_interval: int = DEFAULT_BASE_SPAWN_INTERVAL

        # Licznik transformacji specjalnych stacji
        self.station_transformations: int = 0

    # --- GENEROWANIE STACJI ---

    # Generowanie pozycji stacji z zachowaniem minimalnego dystansu i z podziałem na "nad/pod rzeką"
    def generate_poisson_stations(
        self, count: int = 3, over_river: bool = True
    ) -> List[Tuple[int, int]]:
        points: List[Tuple[int, int]] = []
        attempts = 0
        max_attempts = count * POISSON_ATTEMPTS_PER_STATION

        while len(points) < count and attempts < max_attempts:
            x = random.randint(STATION_SPAWN_MARGIN, self.width - STATION_SPAWN_MARGIN)
            y = random.randint(STATION_SPAWN_MARGIN, self.height - STATION_SPAWN_MARGIN)

            # Nie umieszczaj stacji na rzece lub w jej bliskiej okolicy
            if self.river_y - self.river_margin < y < self.river_y + self.river_margin:
                attempts += 1
                continue

            if over_river and y > self.river_y - self.river_margin:
                attempts += 1
                continue
            if not over_river and y < self.river_y + self.river_margin:
                attempts += 1
                continue

            # Sprawdź dystans od innych stacji
            if any(self._distance((px, py), (x, y)) < POISSON_RADIUS for px, py in points):
                attempts += 1
                continue

            points.append((x, y))
            attempts += 1

        return points

    # Próbuje znaleźć najbardziej równomierny rozkład 3 punktów (do początkowych stacji)
    def generate_harmonious_poisson_triangle(
        self, count: int = 3, over_river: bool = True
    ) -> List[Tuple[int, int]]:
        best_score = float("inf")
        best_points: Optional[List[Tuple[int, int]]] = None

        for _ in range(POISSON_TRIANGLE_TRIALS):
            points = self.generate_poisson_stations(count=count, over_river=over_river)
            if len(points) < 3:
                continue

            a, b, c = points[:3]
            ys = [a[1], b[1], c[1]]
            height = max(ys) - min(ys)
            if height < MIN_TRIANGLE_HEIGHT:
                continue

            sides = [
                self._distance(a, b),
                self._distance(b, c),
                self._distance(c, a)
            ]
            side_diff = max(sides) - min(sides)

            if side_diff < best_score:
                best_score = side_diff
                best_points = [a, b, c]

        return best_points if best_points is not None else []

    # Odległość euklidesowa 2D
    @staticmethod
    def _distance(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    # Sprawdza, czy dana pozycja jest wystarczająco oddalona od pozostałych stacji
    def is_valid_station_position(self, x: int, y: int) -> bool:
        for s in self.stations:
            if self._distance((x, y), (s.x, s.y)) < STATION_MIN_DIST:
                return False
        return True

    # Tworzy stację o danym kształcie; próbuje znaleźć wolne miejsce, jak nie – zwraca losowe
    def generate_station_with_shape(
        self, shape: str, x: Optional[int] = None, y: Optional[int] = None
    ) -> Station:
        for _ in range(100):
            new_x = x if x is not None else random.randint(STATION_SPAWN_MARGIN, self.width - STATION_SPAWN_MARGIN)
            new_y = y if y is not None else random.randint(STATION_SPAWN_MARGIN, self.height - STATION_SPAWN_MARGIN)
            # Nie na rzece
            if self.river_y - self.river_margin < new_y < self.river_y + self.river_margin:
                continue
            if self.is_valid_station_position(new_x, new_y):
                return Station(new_x, new_y, shape)
        # Awaryjnie, jeśli się nie udało – zwracamy cokolwiek, by nie blokować gry
        return Station(
            random.randint(STATION_SPAWN_MARGIN, self.width - STATION_SPAWN_MARGIN),
            random.randint(STATION_SPAWN_MARGIN, self.height - STATION_SPAWN_MARGIN),
            shape,
        )

    # Generuje początkowe stacje z losowym doborem kształtów i położenia
    def generate_initial_stations(self) -> List[Station]:
        over_river = random.choice([True, False])
        positions = self.generate_harmonious_poisson_triangle(over_river=over_river)
        shapes = ['C', 'T', 'Q']
        random.shuffle(shapes)
        stations: List[Station] = [
            self.generate_station_with_shape(shape, x=x, y=y)
            for (x, y), shape in zip(positions, shapes)
        ]
        return stations

    def add_station(self, shape: str, on_top: bool) -> Station:
        station = self.generate_station_with_shape(shape)
        self.stations.append(station)
        return station

    # === ZARZĄDZANIE KOLORAMI I LINIAMI ===

    def get_available_colors(self) -> List[Tuple[int, int, int]]:
        return [c for c in self.unlocked_colors if c not in self.color_to_line]

    def unlock_next_line(self) -> None:
        if len(self.unlocked_colors) < len(LINE_COLORS):
            self.unlocked_colors.append(LINE_COLORS[len(self.unlocked_colors)])

    def select_line_color(self, color: Tuple[int, int, int]) -> bool:
        if self.selected_line_color == color:
            self.selected_line_color = None
            self.active_line = None
            return False
        self.selected_line_color = color
        if color in self.color_to_line:
            self.active_line = self.color_to_line[color]
        else:
            new_line = Line(color)
            self.lines.append(new_line)
            self.color_to_line[color] = new_line
            self.active_line = new_line
        return True

    # === POCIĄGI I WAGONY ===

    def add_train_to_line(self, color: Tuple[int, int, int]) -> None:
        line = self.color_to_line.get(color)
        if line and self.available_trains > 0:
            trains_on_line = [t for t in self.trains if t.line == line]
            if len(trains_on_line) < MAX_TRAINS_PER_LINE:
                self.trains.append(Train(line))
                self.available_trains -= 1

    def add_carriage_to_train(self, train: Train) -> None:
        if self.available_carriages > 0:
            train.add_carriage()
            self.available_carriages -= 1

    # === SEGMENTY I INTERAKCJE ===

    def find_clicked_segment(
        self, pos: Tuple[int, int]
    ) -> Optional[Tuple[Line, Any, Any]]:
        for line in self.lines:
            for a, b, color in line.get_segments():
                if self.is_near_line_segment(pos, a, b):
                    return line, a, b
        return None

    @staticmethod
    def is_near_line_segment(
        pos: Tuple[int, int], a: Any, b: Any, threshold: int = 10
    ) -> bool:
        px, py = pos
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx ** 2 + dy ** 2
        if length_squared == 0:
            return False
        t = max(0, min(1, ((px - a.x) * dx + (py - a.y) * dy) / length_squared))
        proj_x = a.x + t * dx
        proj_y = a.y + t * dy
        return math.hypot(proj_x - px, proj_y - py) < threshold

    def restart_line(self, color: Tuple[int, int, int]) -> None:
        line = self.color_to_line.get(color)
        if line:
            line.clear_segments()

    # === CZAS I PASAŻEROWIE ===

    def get_current_day_label(self) -> str:
        return f"{WEEK_DAYS[self.week_day_index]} | Tydzień {self.week_number}"

    def get_dynamic_spawn_interval(self) -> float:
        time_factor = max(0.3, 1.0 - (self.elapsed_time / (5 * 60 * 1000)))
        passenger_factor = max(0.3, 1.0 - (self.passenger_count / 200))
        interval = self.base_spawn_interval * time_factor * passenger_factor
        return max(MIN_SPAWN_INTERVAL_MS, interval)

    def register_delivered_passengers(self, count: int) -> None:
        self.total_score += count

    def spawn_random_station(self) -> None:
        basic_shapes = ['T', 'Q', 'C']
        special_shapes = ['D', 'S', 'H', 'X']

        shape_pool = basic_shapes + (['D'] if random.random() < 0.05 else [])
        shape = random.choice(shape_pool)
        on_top = random.choice([True, False])

        if (
            random.random() < 0.2 and
            len(self.stations) >= 10 and
            self.station_transformations < 10
        ):
            candidates = [s for s in self.stations if s.shape not in special_shapes]
            if candidates:
                s = random.choice(candidates)
                available_specials = [sh for sh in special_shapes if sh != s.shape]
                if available_specials:
                    original = s.shape
                    s.shape = random.choice(available_specials)
                    self.station_transformations += 1
                    print(f"✨ Transformacja {self.station_transformations}/10: {original} → {s.shape}")
                    return
        self.add_station(shape, on_top)

    # === AKTUALIZACJA ===

    def update(self, dt: int) -> None:
        self.elapsed_time += dt
        self._advance_time()
        self._update_trains_and_passengers(dt)
        self._update_stations(dt)
        self._try_spawn_station(dt)

    def _advance_time(self) -> None:
        if self.elapsed_time // self.INGAME_DAY_MS > self.total_days_passed:
            self.total_days_passed += 1
            self.week_day_index = (self.week_day_index + 1) % 7

            if self.week_day_index == 0:
                self.week_number += 1
                self.handle_weekly_rewards()

            if self.total_days_passed % self.UNLOCK_CYCLE_DAYS == 0:
                self.unlock_next_line()
                self.available_trains += 1
                self.available_carriages += 1

    def _update_trains_and_passengers(self, dt: int) -> None:
        for train in self.trains:
            train.update()
            self.passenger_count += 1

    def _update_stations(self, dt: int) -> None:
        for station in self.stations:
            if random.random() < 0.001:
                shapes = ['C', 'T', 'Q']
                if station.shape in shapes:
                    dest = random.choice([s for s in shapes if s != station.shape])
                    station.passengers.append(Passenger(dest))

            if len(station.passengers) > MAX_PASSENGERS_ON_STATION:
                station.overload_timer += dt / 1000.0
                if station.overload_timer >= OVERLOAD_TIMER_SECONDS:
                    station.is_overloaded = True
            else:
                station.overload_timer = 0.0
                station.is_overloaded = False

    def _try_spawn_station(self, dt: int) -> None:
        self.station_spawn_timer += dt
        if self.station_spawn_timer >= self.get_dynamic_spawn_interval():
            self.spawn_random_station()
            self.station_spawn_timer = 0

    # === OBSŁUGA MYSZY ===

    def handle_mouse_motion(self, pos: Tuple[int, int], camera: Any) -> None:
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)
        self.hovered_segment = None
        for line in self.lines:
            for a, b, _ in line.get_segments():
                if self.is_near_line_segment(world_pos, a, b, threshold=10):
                    self.hovered_segment = (line, a, b)
                    return

    def handle_mouse_down(self, button: int, pos: Tuple[int, int], camera: Any) -> None:
        if self._try_handle_icon_drag(pos):
            return

        if button == 1 and self.hovered_segment:
            if self._try_delete_segment(pos, camera):
                return

        if button == 1:
            if self._try_select_line_color(pos, camera):
                return
            if self._try_select_station_or_segment(pos, camera):
                return

    def _try_handle_icon_drag(self, pos: Tuple[int, int]) -> bool:
        train_rect = pygame.Rect(30, 30, 60, 30)
        carriage_rect = pygame.Rect(110, 30, 60, 30)
        if train_rect.collidepoint(pos) and self.available_trains > 0:
            self.dragging_train_icon = True
            return True
        if carriage_rect.collidepoint(pos) and self.available_carriages > 0:
            self.dragging_carriage_icon = True
            return True
        return False

    def _try_delete_segment(self, pos: Tuple[int, int], camera: Any) -> bool:
        if not self.hovered_segment:
            return False
        line, a, b = self.hovered_segment
        mx = (a.x + b.x) // 2
        my = (a.y + b.y) // 2
        sx, sy = mx - camera.x, my - camera.y
        if math.hypot(pos[0] - sx, pos[1] - sy) <= 10:
            line.segments = [
                s for s in line.segments if not ((s[0] == a and s[1] == b) or (s[0] == b and s[1] == a))
            ]
            line.update_line_type()
            self.trains = [t for t in self.trains if t.line != line or t.get_current_segment() in line.segments]
            self.hovered_segment = None
            return True
        return False

    def _try_select_line_color(self, pos: Tuple[int, int], camera: Any) -> bool:
        base_x, base_y = 20, camera.screen_height - 50
        size, padding = 30, 10
        for i, color in enumerate(LINE_COLORS):
            rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
            if rect.collidepoint(pos):
                self.select_line_color(color)
                self.selected_station = None
                return True
        return False

    def _try_select_station_or_segment(self, pos: Tuple[int, int], camera: Any) -> bool:
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)
        clicked_station = next(
            (s for s in self.stations if math.hypot(s.x - world_pos[0], s.y - world_pos[1]) <= STATION_RADIUS), None
        )
        if clicked_station:
            if self.selected_station is None:
                self.selected_station = clicked_station
                if self.active_line is None:
                    for line in self.lines:
                        if any(clicked_station in seg[:2] for seg in line.get_segments()):
                            self.active_line = line
                            self.selected_line_color = line.default_color
                            print(f"🔁 Automatycznie aktywowano linię: {line.default_color}")
                            break
            else:
                if self.active_line:
                    if clicked_station != self.selected_station:
                        added = self.active_line.add_segment(self.selected_station, clicked_station)
                        if added:
                            print(f"➕ Dodano segment do linii {self.active_line.default_color}")
                self.selected_station = None
            return True
        else:
            segment_info = self.find_clicked_segment(world_pos)
            if segment_info:
                line, a, b = segment_info
                self.dragged_segment = (a, b)
                self.dragged_line = line
                self.selected_line = line
                return True
        return False

    def handle_mouse_up(self, pos: Tuple[int, int], camera: Any) -> None:
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)

        if self.dragging_train_icon:
            self.dragging_train_icon = False
            segment_info = self.find_clicked_segment(world_pos)
            if segment_info:
                line, a, b = segment_info
                trains_on_line = [t for t in self.trains if t.line == line]
                if len(trains_on_line) < MAX_TRAINS_PER_LINE:
                    self.trains.append(Train(line, game_state=self))
                    self.available_trains -= 1
            return

        if self.dragging_carriage_icon:
            self.dragging_carriage_icon = False
            segment_info = self.find_clicked_segment(world_pos)
            if segment_info:
                line, a, b = segment_info
                for train in self.trains:
                    if train.line == line:
                        train.add_carriage()
                        self.available_carriages -= 1
                        break
            return

        if self.dragged_segment and self.dragged_line:
            a, b = self.dragged_segment

            dropped_station = next(
                (s for s in self.stations if math.hypot(s.x - world_pos[0], s.y - world_pos[1]) <= STATION_RADIUS), None
            )

            if dropped_station and dropped_station not in (a, b):
                segments = self.dragged_line.segments
                for i, (s1, s2, _) in enumerate(segments):
                    if (s1 == a and s2 == b) or (s1 == b and s2 == a):
                        color = self.dragged_line.default_color
                        new_segments = segments[:i] + [
                            (a, dropped_station, color),
                            (dropped_station, b, color)
                        ] + segments[i + 1:]
                        self.dragged_line.segments = new_segments
                        self.dragged_line.update_line_type()

                        for train in self.trains:
                            if train.line == self.dragged_line:
                                try:
                                    original_index = segments.index((a, b, color))
                                except ValueError:
                                    original_index = segments.index((b, a, color))

                                if train.current_segment_index > original_index:
                                    train.current_segment_index += 1
                                elif train.current_segment_index == original_index:
                                    train.on_ghost_segment = True
                                    train.ghost_segment = segments[original_index]
                        break

        self.dragged_segment = None
        self.dragged_line = None


