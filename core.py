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
            print(f"⚠️ Próba dodania segmentu z nie-stacjami: {station_a}, {station_b}")
            return False
        if station_a == station_b:
            return False  # nie dodajemy segmentu do tej samej stacji

        # Unikalność segmentu
        if any((a == station_a and b == station_b) or (a == station_b and b == station_a) for a, b, _ in self.segments):
            return False

        self.segments.append((station_a, station_b, self.default_color))
        self.update_line_type()
        return True



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
    def __init__(self, line):
        self.line = line
        self.extra_carriages = 0  
        self.current_segment_index = 0
        self.direction = 1
        self.passengers = []
        self.on_ghost_segment = False

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

        speed = BASE_TRAIN_SPEED / (dist + 1)

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
            print(f"⚠️ Niepoprawny current_segment_index: {self.current_segment_index}")
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
    def handle_boarding(self):
        station = self.get_station_at_current_position()
        if not station:
            self.state = "moving"
            return

        self.stop_timer += 0.016
        if self.stop_timer < 0.3:
            return

        if self.boarding_index == 0:
            self.passengers = [p for p in self.passengers if p.destination_shape != station.shape]

        candidates = [p for p in station.passengers if p.destination_shape != station.shape]

        self.boarding_timer += 0.016
        if self.boarding_timer >= 0.2:
            self.boarding_timer = 0
            if candidates and len(self.passengers) < self.capacity():
                p = candidates.pop(0)
                self.passengers.append(p)
                station.passengers.remove(p)
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

class GameState:
    INGAME_DAY_MS = 60 * 1000  
    UNLOCK_CYCLE_DAYS = 7
    def __init__(self, width, height):
            self.width = int(width * 1.5)
            self.height = int(height * 1.5)
            self.river_y = self.height // 2
            self.stations = []  # <-- najpierw inicjalizacja pustej listy
            self.stations = self.generate_initial_stations()  # potem wygenerowanie początkowych stacji
            self.selected_station = None
            self.lines = []
            self.trains = []
            self.selected_line_color = None
            self.color_to_line = {}
            self.unlocked_colors = LINE_COLORS[:INITIAL_UNLOCKED_LINES]
            self.elapsed_time = 0
            self.total_days_passed = 0  # ile dni minęło od startu
            self.station_spawn_timer = 0
            self.base_spawn_interval = 30000  # w ms
            self.passenger_count = 0
            self.dragged_segment = None  # przechowywany przeciągany segment
            self.dragged_line = None     # linia, której segment przeciągamy
            self.selected_line = None
            self.available_trains = 2
            self.available_carriages = 0
            self.dragging_train_icon = False
            self.dragging_carriage_icon = False

        
    def is_valid_station_position(self, x, y):
        min_dist = 80
        max_dist = 300
        for s in self.stations:
            dist = math.hypot(x - s.x, y - s.y)
            if dist < min_dist:
                return False
        return True

    def generate_station_with_shape(self, shape, on_top):
        for _ in range(100):
            center_x = self.width // 2
            x_range = self.width // 3
            x = random.randint(center_x - x_range, center_x + x_range)
            y = random.randint(50, self.river_y - 50) if on_top else random.randint(self.river_y + 50, self.height - 50)
            if self.is_valid_station_position(x, y):
                return Station(x, y, shape)  # <- poprawione!
        # fallback
        return Station(random.randint(100, self.width - 100),
                    random.randint(100, self.height - 100),
                    shape)  # <- poprawione!


    def generate_initial_stations(self):
        shapes = ['C', 'T', 'Q']
        random.shuffle(shapes)
        return [self.generate_station_with_shape(shape, True) for shape in shapes]

    def add_station(self, shape, on_top):
        new_station = self.generate_station_with_shape(shape, on_top)
        self.stations.append(new_station)
        return new_station

    def get_available_colors(self):
        used = set(self.color_to_line.keys())
        return [c for c in self.unlocked_colors if c not in used]

    def unlock_next_line(self):
        if len(self.unlocked_colors) < len(LINE_COLORS):
            self.unlocked_colors.append(LINE_COLORS[len(self.unlocked_colors)])

    def select_line_color(self, color):
        if self.selected_line_color == color:
            # Jeśli kliknięto ponownie ten sam kolor, odznacz
            print(f"Odznaczono kolor linii: {color}")
            self.selected_line_color = None
            return False
        if color not in self.get_available_colors():
            print("Kolor zajęty lub zablokowany")
            return False
        self.selected_line_color = color
        print(f"Wybrano kolor linii: {color}")
        return True


    def add_train_to_line(self, color):
        line = self.color_to_line.get(color)
        if line and self.available_trains > 0:
            # max 4 pociągi na linię
            trains_on_line = [t for t in self.trains if t.line == line]
            if len(trains_on_line) < 4:
                self.trains.append(Train(line))
                self.available_trains -= 1
                print(f"Dodano pociąg do linii {color}")
    def add_carriage_to_train(self, train):
        if self.available_carriages > 0:
            train.add_carriage()
            self.available_carriages -= 1
            print(f"Dodano wagon do pociągu")


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
            print(f"Restartowano linię {color}")

    def handle_train_panel_click(self, pos, screen_height):
        base_x = 20
        base_y = screen_height - 100
        size = TRAIN_ICON_SIZE
        padding = TRAIN_ICON_PADDING

        for i, color in enumerate(self.unlocked_colors):
            rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
            if rect.collidepoint(pos):
                self.add_train_to_line(color)
                break
    def get_dynamic_spawn_interval(self):
        # Bazowe opóźnienie skraca się wraz z postępem
        time_factor = max(0.3, 1.0 - (self.elapsed_time / (5 * 60 * 1000)))  # do 5 minut
        passenger_factor = max(0.3, 1.0 - (self.passenger_count / 200))  # do 200 pasażerów
        interval = self.base_spawn_interval * time_factor * passenger_factor
        return max(1500, interval)  # nigdy mniej niż 1.5 sekundy
    def spawn_random_station(self):
        shapes = ['C', 'T', 'Q']
        if random.random() < 0.05:  # 5% szans na specjalną mutację
            shapes.append('D')  # D = diament (rzadka stacja)
        shape = random.choice(shapes)

        on_top = random.choice([True, False])

        if random.random() < 0.2 and self.stations:  # 20% szans na mutację istniejącej
            s = random.choice(self.stations)
            original_shape = s.shape
            s.shape = shape
            print(f"Stacja {original_shape} zmutowała w {shape}")
        else:
            new_station = self.add_station(shape, on_top)
            print(f"Wygenerowano nową stację: {shape} ({'góra' if on_top else 'dół'})")

    def handle_mouse_down(self, button, pos, camera):
        # Spójne z draw_resource_info
        train_rect = pygame.Rect(30, 30, 60, 30)
        carriage_rect = pygame.Rect(102, 48, 40, 30)

        if train_rect.collidepoint(pos) and self.available_trains > 0:
            self.dragging_train_icon = True
            print("🚂 Rozpoczęto przeciąganie lokomotywy")
            return

        if carriage_rect.collidepoint(pos) and self.available_carriages > 0:
            self.dragging_carriage_icon = True
            print("🚋 Rozpoczęto przeciąganie wagonu")
            return

        if button == 1:
            base_x = 20
            base_y = camera.screen_height - 50
            size = 30
            padding = 10
            for i, color in enumerate(LINE_COLORS):
                rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
                if rect.collidepoint(pos):
                    self.select_line_color(color)
                    self.selected_station = None
                    return

            world_pos = (pos[0] + camera.x, pos[1] + camera.y)
            clicked_station = next((s for s in self.stations if math.hypot(s.x - world_pos[0], s.y - world_pos[1]) <= STATION_RADIUS), None)

            if not clicked_station:
                segment_info = self.find_clicked_segment((pos[0] + camera.x, pos[1] + camera.y))
                if segment_info:
                    line, a, b = segment_info
                    self.dragged_segment = (a, b)
                    self.dragged_line = line
                    self.selected_line = line
                    print(f"Rozpoczęto przeciąganie segmentu między {a.shape} a {b.shape}")
                return

            if self.selected_station is None:
                self.selected_station = clicked_station
                print(f"Wybrano pierwszą stację: {clicked_station.shape}")
            else:
                if self.selected_line_color is None:
                    print("Najpierw wybierz kolor linii do tworzenia")
                    self.selected_station = None
                    return

                line = self.color_to_line.get(self.selected_line_color)
                if line is None:
                    line = Line(self.selected_line_color)
                    self.lines.append(line)
                    self.color_to_line[self.selected_line_color] = line
                    print(f"Utworzono nową linię koloru {self.selected_line_color}")

                if clicked_station != self.selected_station:
                    added = line.add_segment(self.selected_station, clicked_station)
                    if added:
                        print(f"Dodano segment do linii {self.selected_line_color} między {self.selected_station.shape} a {clicked_station.shape}")
                self.selected_station = None
                segment_info = self.find_clicked_segment((pos[0] + camera.x, pos[1] + camera.y))
                if segment_info:
                    line, a, b = segment_info
                    self.dragged_segment = (a, b)
                    self.dragged_line = line
    def handle_mouse_up(self, pos, camera):
        if self.dragging_train_icon:
            self.dragging_train_icon = False
            segment_info = self.find_clicked_segment((pos[0] + camera.x, pos[1] + camera.y))
            if segment_info:
                line, a, b = segment_info
                trains_on_line = [t for t in self.trains if t.line == line]
                if len(trains_on_line) < 4:
                    self.trains.append(Train(line))
                    self.available_trains -= 1
                    print(f"➕ Przeciągnięto pociąg na linię {line.default_color}")
            return

        if self.dragging_carriage_icon:
            self.dragging_carriage_icon = False
            segment_info = self.find_clicked_segment((pos[0] + camera.x, pos[1] + camera.y))
            if segment_info:
                line, a, b = segment_info
                # Znajdź najbliższy pociąg na tej linii
                for train in self.trains:
                    if train.line == line:
                        train.add_carriage()
                        self.available_carriages -= 1
                        print(f"➕ Dodano wagon do pociągu na linii {line.default_color}")
                        break
            return

        if self.selected_line is None:
            return

        if self.dragged_segment and self.dragged_line:
            a, b = self.dragged_segment
            world_pos = (pos[0] + camera.x, pos[1] + camera.y)

            print(f"Mouse world pos: {world_pos}")
            for s in self.stations:
                dist = math.hypot(s.x - world_pos[0], s.y - world_pos[1])
                print(f"Stacja {s.shape} ({s.x}, {s.y}) - dystans od kursora: {dist:.2f}")

            dropped_station = next(
                (s for s in self.stations if math.hypot(s.x - world_pos[0], s.y - world_pos[1]) <= STATION_RADIUS),
                None
            )

            if not dropped_station:
                self.dragged_segment = None
                self.dragged_line = None
                return

            if dropped_station not in (a, b):
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
                                    print(f"🔁 Skorygowano indeks pociągu z powodu edycji wcześniejszego segmentu")

                                elif train.current_segment_index == original_index:
                                    train.on_ghost_segment = True
                                    print(f"👻 Pociąg był na modyfikowanym segmencie — pozostaje na ghost segmencie {a.shape}-{b.shape}")

                        print(f"✅ Segment {a.shape}-{b.shape} rozdzielony przez {dropped_station.shape}")
                        for train in self.trains:
                            if train.line == self.dragged_line:
                                if train.current_segment == (a, b, color) or train.current_segment == (b, a, color):
                                    train.on_ghost_segment = True
                                    print(f"👻 Pociąg wchodzi na ghost segment: {a.shape}-{b.shape}")
                        break
            else:
                print(f"⚠️ Nie znaleziono nowej stacji do przecięcia segmentu lub wybrano stację {a.shape}/{b.shape}")

        self.dragged_segment = None
        self.dragged_line = None





    def update(self, dt):
        self.elapsed_time += dt
        days_passed_now = self.elapsed_time // self.INGAME_DAY_MS
        if days_passed_now > self.total_days_passed:
            self.total_days_passed = days_passed_now
            if self.total_days_passed % self.UNLOCK_CYCLE_DAYS == 0:
                self.unlock_next_line()
                self.available_trains += 1
                self.available_carriages += 1

        for train in self.trains:
            train.update()
            self.passenger_count += 1  # uproszczone, docelowo licz po wysadzeniu pasażerów

        
        for station in self.stations:
            if random.random() < 0.001:
                shapes = ['C', 'T', 'Q']
                if station.shape in shapes:
                    possible_destinations = [s for s in shapes if s != station.shape]
                    destination = random.choice(possible_destinations)
                    station.passengers.append(Passenger(destination))


            if len(station.passengers) > 8:
                station.overload_timer += dt / 1000.0  # dt jest w ms -> konwertujemy na sekundy
                if station.overload_timer >= 5.0:
                    station.is_overloaded = True
            else:
                station.overload_timer = 0.0
                station.is_overloaded = False


        self.station_spawn_timer += dt
        dynamic_interval = self.get_dynamic_spawn_interval()
        if self.station_spawn_timer >= dynamic_interval:
            self.spawn_random_station()
            self.station_spawn_timer = 0
