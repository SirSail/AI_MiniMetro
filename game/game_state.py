import random
import pygame
import math
from models.line import Line
from models.station import Station
from models.train import Train
from models.passenger import Passenger

STATION_RADIUS = 20

LINE_COLORS = [
    (255, 0, 0),    # czerwony
    (0, 255, 0),    # zielony
    (0, 0, 255),    # niebieski
    (255, 165, 0),  # pomarańczowy
    (128, 0, 128),  # fioletowy
]
TRAIN_ICON_SIZE = 30
TRAIN_ICON_PADDING = 10

INITIAL_UNLOCKED_LINES = 3
WEEK_DAYS = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]

class GameState:
    INGAME_DAY_MS = 60 * 1000
    UNLOCK_CYCLE_DAYS = 7
    
    def __init__(self, width, height):
        self.width = int(width * 1.5)
        self.height = int(height * 1.5)
        self.river_y = self.height // 2
        self.river_margin = 100

        self.stations = []
        self.stations = self.generate_initial_stations()
        self.selected_station = None

        self.lines = []
        self.color_to_line = {}
        self.unlocked_colors = LINE_COLORS[:INITIAL_UNLOCKED_LINES]
        self.selected_line_color = None
        self.selected_line = None
        self.active_line = None  

        self.trains = []
        self.available_trains = 2
        self.available_carriages = 0

        self.dragged_segment = None
        self.dragged_line = None
        self.hovered_segment = None  

        self.dragging_train_icon = False
        self.dragging_carriage_icon = False

        self.elapsed_time = 0
        self.total_days_passed = 0
        self.passenger_count = 0
        self.total_score = 0
        self.week_day_index = 0
        self.week_number = 1

        self.station_spawn_timer = 0
        self.base_spawn_interval = 30000

    # === GENEROWANIE STACJI ===
    def generate_poisson_stations(self, count=3, radius=50, over_river=True):
        width, height = self.width, self.height
        river_y = self.river_y
        margin = self.river_margin
        center_x = width // 2
        bias_range = width // 3

        points = []
        attempts = 0
        max_attempts = count * 15

        while len(points) < count and attempts < max_attempts:
            x = random.randint(center_x - bias_range, center_x + bias_range)
            y = random.randint(50, height - 50)

            if river_y - margin < y < river_y + margin:
                attempts += 1
                continue

            if over_river and y > river_y - margin:
                attempts += 1
                continue
            if not over_river and y < river_y + margin:
                attempts += 1
                continue

            if any((px - x) ** 2 + (py - y) ** 2 < radius ** 2 for px, py in points):
                attempts += 1
                continue

            points.append((x, y))
            attempts += 1

        return points

    def generate_harmonious_poisson_triangle(self, count=3, radius=50, over_river=True, trials=20):
        best_score = float("inf")
        best_points = None
        min_triangle_height = 20  

        for _ in range(trials):
            points = self.generate_poisson_stations(count=count, radius=radius, over_river=over_river)
            if len(points) < 3:
                continue

            a, b, c = points[:3]
            ys = [a[1], b[1], c[1]]
            height = max(ys) - min(ys)
            if height < min_triangle_height:
                continue  

            sides = [
                math.dist(a, b),
                math.dist(b, c),
                math.dist(c, a)
            ]
            side_diff = max(sides) - min(sides)

            if side_diff < best_score:
                best_score = side_diff
                best_points = [a, b, c]

        return best_points

    def is_valid_station_position(self, x, y):
        min_dist = 80
        for s in self.stations:
            if math.hypot(x - s.x, y - s.y) < min_dist:
                return False
        return True

    def generate_station_with_shape(self, shape, x=None, y=None):
        margin = self.river_margin  

        for _ in range(100):
            if x is None or y is None:
                x = random.randint(60, self.width - 60)
                y = random.randint(60, self.height - 60)

            if self.river_y - margin < y < self.river_y + margin:
                continue

            if self.is_valid_station_position(x, y):
                return Station(x, y, shape)

        return Station(random.randint(60, self.width - 60), random.randint(60, self.height - 60), shape)

    def generate_initial_stations(self):
        stations = []
        over_river = random.choice([True, False])
        positions = self.generate_harmonious_poisson_triangle()
        shapes = ['C', 'T', 'Q']
        random.shuffle(shapes)  
        for (x, y), shape in zip(positions, shapes):
            stations.append(self.generate_station_with_shape(shape, x=x, y=y))
        return stations

    def add_station(self, shape, on_top):
        station = self.generate_station_with_shape(shape, on_top)
        self.stations.append(station)
        return station

    # === ZARZĄDZANIE KOLORAMI I LINIAMI ===
    def get_available_colors(self):
        return [c for c in self.unlocked_colors if c not in self.color_to_line]

    def unlock_next_line(self):
        if len(self.unlocked_colors) < len(LINE_COLORS):
            self.unlocked_colors.append(LINE_COLORS[len(self.unlocked_colors)])

    def select_line_color(self, color):
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
    def add_train_to_line(self, color):
        line = self.color_to_line.get(color)
        if line and self.available_trains > 0:
            trains_on_line = [t for t in self.trains if t.line == line]
            if len(trains_on_line) < 4:
                self.trains.append(Train(line))
                self.available_trains -= 1

    def add_carriage_to_train(self, train):
        if self.available_carriages > 0:
            train.add_carriage()
            self.available_carriages -= 1

    # === SEGMENTY I INTERAKCJE ===
    def find_clicked_segment(self, pos):
        for line in self.lines:
            for a, b, color in line.get_segments():
                if self.is_near_line_segment(pos, a, b):
                    return line, a, b
        return None

    def is_near_line_segment(self, pos, a, b, threshold=10):
        px, py = pos
        dx, dy = b.x - a.x, b.y - a.y
        length_squared = dx**2 + dy**2
        if length_squared == 0:
            return False
        t = max(0, min(1, ((px - a.x) * dx + (py - a.y) * dy) / length_squared))
        proj_x = a.x + t * dx
        proj_y = a.y + t * dy
        return math.hypot(proj_x - px, proj_y - py) < threshold

    def restart_line(self, color):
        line = self.color_to_line.get(color)
        if line:
            line.clear_segments()

    # === CZAS I PASAŻEROWIE ===
    def get_current_day_label(self):
        return f"{WEEK_DAYS[self.week_day_index]} | Tydzień {self.week_number}"

    def get_dynamic_spawn_interval(self):
        time_factor = max(0.3, 1.0 - (self.elapsed_time / (5 * 60 * 1000)))
        passenger_factor = max(0.3, 1.0 - (self.passenger_count / 200))
        interval = self.base_spawn_interval * time_factor * passenger_factor
        return max(1500, interval)

    def register_delivered_passengers(self, count):
        self.total_score += count
        
    def spawn_random_station(self):
        basic_shapes = ['T', 'Q', 'C']
        special_shapes = ['D', 'S', 'H', 'X']
        if not hasattr(self, "station_transformations"):
            self.station_transformations = 0

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
    def update(self, dt):
        self.elapsed_time += dt
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

        for train in self.trains:
            train.update()
            self.passenger_count += 1

        for station in self.stations:
            if random.random() < 0.001:
                shapes = ['C', 'T', 'Q']
                if station.shape in shapes:
                    dest = random.choice([s for s in shapes if s != station.shape])
                    station.passengers.append(Passenger(dest))

            if len(station.passengers) > 8:
                station.overload_timer += dt / 1000.0
                if station.overload_timer >= 5.0:
                    station.is_overloaded = True
            else:
                station.overload_timer = 0.0
                station.is_overloaded = False

        self.station_spawn_timer += dt
        if self.station_spawn_timer >= self.get_dynamic_spawn_interval():
            self.spawn_random_station()
            self.station_spawn_timer = 0

    def handle_mouse_motion(self, pos, camera):
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)
        self.hovered_segment = None
        for line in self.lines:
            for a, b, _ in line.get_segments():
                if self.is_near_line_segment(world_pos, a, b, threshold=10):
                    self.hovered_segment = (line, a, b)
                    return

    def handle_mouse_down(self, button, pos, camera):
        train_rect = pygame.Rect(30, 30, 60, 30)
        carriage_rect = pygame.Rect(110, 30, 60, 30)

        if train_rect.collidepoint(pos) and self.available_trains > 0:
            self.dragging_train_icon = True
            return

        if carriage_rect.collidepoint(pos) and self.available_carriages > 0:
            self.dragging_carriage_icon = True
            return

        if button == 1 and self.hovered_segment:
            line, a, b = self.hovered_segment
            mx = (a.x + b.x) // 2
            my = (a.y + b.y) // 2
            sx, sy = mx - camera.x, my - camera.y
            if math.hypot(pos[0] - sx, pos[1] - sy) <= 10:
                line.segments = [s for s in line.segments if not ((s[0] == a and s[1] == b) or (s[0] == b and s[1] == a))]
                line.update_line_type()
                self.trains = [t for t in self.trains if t.line != line or t.get_current_segment() in line.segments]
                self.hovered_segment = None
                return

        if button == 1:
            # Panel wyboru koloru linii (u dołu ekranu)
            base_x, base_y = 20, camera.screen_height - 50
            size, padding = 30, 10
            for i, color in enumerate(LINE_COLORS):
                rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
                if rect.collidepoint(pos):
                    self.select_line_color(color)
                    self.selected_station = None
                    return

            # Wybór stacji lub segmentu na mapie
            world_pos = (pos[0] + camera.x, pos[1] + camera.y)
            clicked_station = next(
                (s for s in self.stations if math.hypot(s.x - world_pos[0], s.y - world_pos[1]) <= STATION_RADIUS), None
            )

            if clicked_station:
                if self.selected_station is None:
                    self.selected_station = clicked_station
                    # Jeśli brak aktywnej linii, sprawdź, czy kliknięta stacja należy do jakiejś
                    if self.active_line is None:
                        for line in self.lines:
                            if any(clicked_station in seg[:2] for seg in line.get_segments()):
                                self.active_line = line
                                self.selected_line_color = line.default_color
                                print("🔁 Automatycznie aktywowano linię:", line.default_color)
                                break
                else:
                    if self.active_line:
                        if clicked_station != self.selected_station:
                            added = self.active_line.add_segment(self.selected_station, clicked_station)
                            if added:
                                print("➕ Dodano segment do linii", self.active_line.default_color)
                    self.selected_station = None

            else:
                segment_info = self.find_clicked_segment(world_pos)
                if segment_info:
                    line, a, b = segment_info
                    self.dragged_segment = (a, b)
                    self.dragged_line = line
                    self.selected_line = line

    def handle_mouse_up(self, pos, camera):
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)

        if self.dragging_train_icon:
            self.dragging_train_icon = False
            segment_info = self.find_clicked_segment(world_pos)
            if segment_info:
                line, a, b = segment_info
                trains_on_line = [t for t in self.trains if t.line == line]
                if len(trains_on_line) < 4:
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
                        ] + segments[i+1:]
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







    