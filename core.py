import random
import pygame
import math

STATION_RADIUS = 20
BASE_TRAIN_SPEED = 1  # Zależna od długości segmentu

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
class Station:
    def __init__(self, x, y, shape):
        self.x = x
        self.y = y
        self.shape = shape
        self.passengers = []  
        self.overload_timer = 0.0
        self.is_overloaded = False

class Line:
    def __init__(self, color):
        self.default_color = color
        self.segments = []  # list of tuples: (station_a, station_b, color)
        self.is_loop = False
        self.is_bidirectional = False
        
    def add_segment(self, station_a, station_b):
        if not isinstance(station_a, Station) or not isinstance(station_b, Station):
            return False
        if station_a == station_b:
            return False  # nie dodajemy segmentu do tej samej stacji

        # Unikalność segmentu
        if any((a == station_a and b == station_b) or (a == station_b and b == station_a) for a, b, _ in self.segments):
            return False

        self.segments.append((station_a, station_b, self.default_color))
        self.update_line_type()
        return True
    def clear_line(self, color):
        line = self.color_to_line.get(color)
        if line:
            line.clear_segments()
            # Usuwamy też pociągi z tej linii
            self.trains = [t for t in self.trains if t.line != line]



    def remove_segment(self, station_a, station_b):
        self.segments = [
            seg for seg in self.segments
            if not ((seg[0] == station_a and seg[1] == station_b) or
                    (seg[0] == station_b and seg[1] == station_a))
        ]
        self.update_line_type()

    def get_segments(self):
        return self.segments


    def update_line_type(self):
        if len(self.segments) < 2:
            self.is_loop = False
            self.is_bidirectional = False
            return
        stations = [seg[0] for seg in self.segments] + [self.segments[-1][1]]
        if stations[0] == stations[-1]:
            self.is_loop = True
            self.is_bidirectional = False
        else:
            self.is_loop = False
            self.is_bidirectional = True

    def clear_segments(self):
        self.segments = []
        self.is_loop = False
        self.is_bidirectional = False

class Train:
    def __init__(self, line, game_state=None):
        self.line = line
        self.extra_carriages = 0  
        self.current_segment_index = 0
        self.direction = 1
        self.passengers = []
        self.on_ghost_segment = False
        self.game_state = game_state

        self.current_segment = line.segments[0] if line.segments else None
        self.position = 0.0
        self.current_speed = self.calculate_speed()

        self.state = "moving"  # "moving", "boarding"
        self.stop_timer = 0.0
        self.boarding_timer = 0.0
        self.boarding_index = 0

    # === GŁÓWNY UPDATE ===
    def update(self):
        if not self.current_segment:
            return

        if self.state == "boarding":
            self.handle_boarding()
            return

        a, b, _ = self.current_segment
        dist = math.hypot(b.x - a.x, b.y - a.y)
        if dist == 0:
            return

        speed = 1.5 * BASE_TRAIN_SPEED / (dist + 1)

        if self.position > 0.8:
            slowdown = (1.0 - self.position) / 0.2
            speed *= max(0.1, slowdown)

        if self.position < 0.3:
            prev_seg = self.get_previous_segment()
            if prev_seg:
                angle = self.calculate_turn_angle(prev_seg, self.current_segment)
                if angle < 90:
                    speed *= 0.3 + 0.7 * ((90 - angle) / 90)
                elif angle < 120:
                    speed *= 0.8

        if self.count_crossings_not_at_station(a, b) > 0:
            speed *= 0.5

        self.position += self.direction * speed

        if self.position >= 1.0:
            self.position = 1.0
            self.state = "boarding"
            self.stop_timer = 0.0
            self.boarding_index = 0

            if self.on_ghost_segment:
                self.on_ghost_segment = False
                # Znajdź pasujący segment po ghost
                for i, seg in enumerate(self.line.segments):
                    if b in seg:
                        # 🔄 Korekta indeksu zależna od pozycji na ghost segmencie
                        if self.direction > 0:
                            self.current_segment_index = i if self.position >= 0.5 else i - 1
                        else:
                            self.current_segment_index = i if self.position <= 0.5 else i + 1

                        # Zabezpieczenie granic
                        self.current_segment_index = max(0, min(self.current_segment_index, len(self.line.segments) - 1))
                        self.current_segment = self.line.segments[self.current_segment_index]
                        break

        elif self.position < 0.0:
            self.position = 0.0
            self.state = "boarding"
            self.stop_timer = 0.0
            self.boarding_index = 0

    # === SEGMENT I RUCH PO LINII ===

    def get_current_segment(self):
        if 0 <= self.current_segment_index < len(self.line.segments):
            return self.line.segments[self.current_segment_index]
        return None

    def move_to_next_segment(self, current_station):
        if not self.line.segments:
            self.current_segment = None
            return

        self.current_segment_index += self.direction
        n = len(self.line.segments)

        if self.current_segment_index >= n:
            if self.line.is_loop:
                self.current_segment_index = 0
            else:
                self.current_segment_index = max(n - 2, 0)
                self.direction = -1
        elif self.current_segment_index < 0:
            if self.line.is_loop:
                self.current_segment_index = n - 1
            else:
                self.current_segment_index = 1 if n > 1 else 0
                self.direction = 1

        if 0 <= self.current_segment_index < n:
            self.current_segment = self.line.segments[self.current_segment_index]
        else:
            self.current_segment = None

    def get_previous_segment(self):
        try:
            return self.line.segments[self.current_segment_index - self.direction]
        except IndexError:
            return None

    def find_segment_index_closest_to_station(self, station):
        for i, (a, b, _) in enumerate(self.line.segments):
            if a == station or b == station:
                return i
        return 0

    def is_on_ghost_segment(self):
        return self.current_segment not in self.line.segments

    def get_station_at_current_position(self):
        if not self.current_segment:
            return None
        a, b, _ = self.current_segment
        return b if self.position >= 1.0 else a if self.position <= 0.0 else None

    # === PASAŻEROWIE ===
    def capacity(self):
        return 6 + self.extra_carriages * 6

    def add_carriage(self):
        self.extra_carriages += 1

    def can_reach_shape_from_here(self, shape, current_station):
        visited = set()
        to_visit = [current_station]

        while to_visit:
            station = to_visit.pop()
            if station in visited:
                continue
            visited.add(station)
            if station.shape == shape:
                return True
            neighbors = self.get_neighbors_on_line(station)
            to_visit.extend(neighbors)
        return False
    def find_transfer_station_toward_shape(self, destination_shape):
        # Znajdź stację na tej linii, która ma połączenie z inną linią prowadzącą do celu
        for station in self.get_all_stations_on_line():
            if station.shape == destination_shape:
                return station
            for other_train in self.game_state.trains:
                if other_train == self:
                    continue
                if other_train.can_reach_shape_from_here(destination_shape, station):
                    return station
        return None
    def get_neighbors_on_line(self, station):
        neighbors = []
        for a, b, _ in self.line.segments:
            if a == station:
                neighbors.append(b)
            elif b == station:
                neighbors.append(a)
        return neighbors
    def get_all_stations_on_line(self):
        stations = set()
        for a, b, _ in self.line.segments:
            stations.add(a)
            stations.add(b)
        return list(stations)

    def handle_boarding(self):
        station = self.get_station_at_current_position()
        if not station:
            self.state = "moving"
            return

        self.stop_timer += 0.016
        if self.stop_timer < 0.3:
            return

        if self.boarding_index == 0:
            delivered = [
                p for p in self.passengers if (
                    p.destination_shape == station.shape or
                    (p.current_target_station is not None and p.current_target_station == station)
                )
            ]

            # Oddziel dostarczonych od przesiadkowiczów
            final_delivered = [p for p in delivered if p.destination_shape == station.shape]
            transfer_delivered = [p for p in delivered if p.current_target_station == station and p.destination_shape != station.shape]

            # Zarejestruj tylko tych, którzy dotarli do celu
            if final_delivered:
                self.game_state.register_delivered_passengers(len(final_delivered))
                print(f"🏆 Dostarczono {len(final_delivered)} pasażerów na stację {station.shape} | Łączny wynik: {self.game_state.total_score}")

            # Przesiadka – pasażerowie wracają na stację
            for p in transfer_delivered:
                station.passengers.append(p)
                p.last_train = self
                print(f"🔁 Pasażer przesiadł się na stacji {station.shape} — jego cel to {p.destination_shape}")

            # Resetuj cel pośredni
            for p in delivered:
                p.current_target_station = None

            # Usuń z pociągu wszystkich, którzy wysiedli (celowo lub na przesiadkę)
            self.passengers = [p for p in self.passengers if p not in delivered]

        # === Boarding logic ===
        candidates = []
        for p in station.passengers:
            if p.last_train == self:
                continue  
            if p.destination_shape == station.shape:
                continue  
            if self.can_reach_shape_from_here(p.destination_shape, station):
                p.current_target_station = None  # jedzie bezpośrednio
            else:
                next_station = self.find_transfer_station_toward_shape(p.destination_shape)
                if next_station:
                    p.current_target_station = next_station
                else:
                    continue  # nie ma sensownej trasy
            candidates.append(p)

        self.boarding_timer += 0.016
        if self.boarding_timer >= 0.2:
            self.boarding_timer = 0
            if candidates and len(self.passengers) < self.capacity():
                p = candidates.pop(0)
                self.passengers.append(p)
                station.passengers.remove(p)
                p.last_train = None 
                self.boarding_index += 1
                return

        if len(self.passengers) >= self.capacity() or not candidates:
            self.state = "moving"
            self.boarding_timer = 0.0
            self.boarding_index = 0
            self.move_to_next_segment(current_station=station)
            self.position = 0.0 if self.direction > 0 else 1.0


    # === OBLICZENIA I GEOMETRIA ===
    def calculate_speed(self):
        if not self.current_segment:
            return 0
        a, b, _ = self.current_segment
        dist = math.hypot(b.x - a.x, b.y - a.y)
        if dist == 0:
            return 0.01
        return BASE_TRAIN_SPEED / (dist + 1)

    def count_crossings_not_at_station(self, a, b):
        count = 0
        for x, y, _ in self.line.segments:
            if (x, y) == (a, b) or (y, x) == (a, b):
                continue
            if self.do_segments_cross(a, b, x, y):
                if x not in [a, b] and y not in [a, b]:
                    count += 1
        return count

    def do_segments_cross(self, a1, a2, b1, b2):
        def ccw(p1, p2, p3):
            return (p3.y - p1.y) * (p2.x - p1.x) > (p2.y - p1.y) * (p3.x - p1.x)
        return (
            ccw(a1, b1, b2) != ccw(a2, b1, b2) and
            ccw(a1, a2, b1) != ccw(a1, a2, b2)
        )

    def calculate_turn_angle(self, seg1, seg2):
        a1, b1, _ = seg1
        a2, b2, _ = seg2

        pivot = None
        if b1 == a2:
            pivot = b1
            vec1 = (a1.x - pivot.x, a1.y - pivot.y)
            vec2 = (b2.x - pivot.x, b2.y - pivot.y)
        elif b1 == b2:
            pivot = b1
            vec1 = (a1.x - pivot.x, a1.y - pivot.y)
            vec2 = (a2.x - pivot.x, a2.y - pivot.y)
        elif a1 == a2:
            pivot = a1
            vec1 = (b1.x - pivot.x, b1.y - pivot.y)
            vec2 = (b2.x - pivot.x, b2.y - pivot.y)
        elif a1 == b2:
            pivot = a1
            vec1 = (b1.x - pivot.x, b1.y - pivot.y)
            vec2 = (a2.x - pivot.x, a2.y - pivot.y)
        else:
            return 180

        dot = vec1[0]*vec2[0] + vec1[1]*vec2[1]
        mag1 = math.hypot(*vec1)
        mag2 = math.hypot(*vec2)
        if mag1 == 0 or mag2 == 0:
            return 180

        cos_angle = dot / (mag1 * mag2)
        return math.degrees(math.acos(max(-1, min(1, cos_angle))))




class Passenger:
    def __init__(self, destination_shape):
        self.destination_shape = destination_shape
        self.current_target_station = None  # ← do aktualizacji podczas przesiadek
        self.last_train = None  # zapamiętany ostatni pociąg


class GameState:
    INGAME_DAY_MS = 60 * 1000
    UNLOCK_CYCLE_DAYS = 7
    

    def __init__(self, width, height):
        # Rozmiar świata i mapa
        self.width = int(width * 1.5)
        self.height = int(height * 1.5)
        self.river_y = self.height // 2
        self.river_margin = 100

        # Stacje
        self.stations = []
        self.stations = self.generate_initial_stations()
        self.selected_station = None

        # Linie i kolory
        self.lines = []
        self.color_to_line = {}
        self.unlocked_colors = LINE_COLORS[:INITIAL_UNLOCKED_LINES]
        self.selected_line_color = None
        self.selected_line = None
        self.active_line = None  

        # Pociągi
        self.trains = []
        self.available_trains = 2
        self.available_carriages = 0

        # Segmenty
        self.dragged_segment = None
        self.dragged_line = None
        self.hovered_segment = None  

        # Interfejs zasobów
        self.dragging_train_icon = False
        self.dragging_carriage_icon = False

        # Czas gry i pasażerowie
        self.elapsed_time = 0
        self.total_days_passed = 0
        self.passenger_count = 0
        self.total_score = 0
        self.week_day_index = 0  # 0 = poniedziałek, 6 = niedziela
        self.week_number = 1

        # Spawn stacji
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
        # Kształty podstawowe
        basic_shapes = ['T', 'Q', 'C']  # Triangle, Square, Circle
        # Kształty specjalne
        special_shapes = ['D', 'S', 'H', 'X']  # Diamond, Star, Hexagon, Cross

        # Inicjalizacja licznika transformacji (jeśli nie ma)
        if not hasattr(self, "station_transformations"):
            self.station_transformations = 0

        # Pula kształtów do nowej stacji
        shape_pool = basic_shapes + (['D'] if random.random() < 0.05 else [])
        shape = random.choice(shape_pool)
        on_top = random.choice([True, False])

        if (
            random.random() < 0.2 and
            len(self.stations) >= 10 and
            self.station_transformations < 10
        ):
            # Szukamy zwykłej stacji do przekształcenia
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

        # Jeśli nie transformujemy, dodajemy nową stację
        self.add_station(shape, on_top)



    # === AKTUALIZACJA ===

    def update(self, dt):
        self.elapsed_time += dt
        # Zmiana dnia
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

        if self.dragged_segment and self.dragged_line and dropped_station is None:
            # Usuwamy segment całkowicie
            a, b = self.dragged_segment
            self.dragged_line.remove_segment(a, b)

        for train in self.trains:
            train.update()
            self.passenger_count += 1  # uproszczone

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

        # ===  Interakcja myszy (przeciąganie zasobów i segmentów) === 
    def handle_mouse_motion(self, pos, camera):
        world_pos = (pos[0] + camera.x, pos[1] + camera.y)
        self.hovered_segment = None
        for line in self.lines:
            for a, b, _ in line.get_segments():
                if self.is_near_line_segment(world_pos, a, b, threshold=10):
                    self.hovered_segment = (line, a, b)
                    return

    def handle_mouse_down(self, button, pos, camera):
        # Recty spójne z UI zasobów
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

                        break


        self.dragged_segment = None
        self.dragged_line = None






    
