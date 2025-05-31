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
        self.color = color
        self.segments = []
        self.is_loop = False
        self.is_bidirectional = False

    def add_segment(self, station_a, station_b):
        if (station_a, station_b) in self.segments or (station_b, station_a) in self.segments:
            return False
        self.segments.append((station_a, station_b))
        self.update_line_type()
        return True

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
        self.current_segment_index = 0
        self.position = 0.0
        self.direction = 1
        self.current_speed = self.calculate_speed()
        self.passengers = []  # lista pasażerów na pokładzie
        self.capacity = 6
    
    def arrive_at_station(self, station):
        # wysadzanie pasażerów
        before = len(self.passengers)
        self.passengers = [p for p in self.passengers if p.destination_shape != station.shape]
        dropped_off = before - len(self.passengers)

        # zabieranie nowych pasażerów
        needed = self.capacity - len(self.passengers)
        if needed > 0:
            candidates = [p for p in station.passengers if p.destination_shape != station.shape]
            to_board = candidates[:needed]
            self.passengers.extend(to_board)
            for p in to_board:
                station.passengers.remove(p)

    def calculate_speed(self):
        segment = self.get_current_segment()
        if not segment:
            return 0
        a, b = segment
        dist = math.hypot(b.x - a.x, b.y - a.y)
        return BASE_TRAIN_SPEED / (dist + 1)

    def update(self):
        if not self.line.segments:
            return
        self.position += self.current_speed * self.direction

        if self.position >= 1.0 or self.position <= 0.0:
            if self.line.is_loop:
                self.current_segment_index = (self.current_segment_index + self.direction) % len(self.line.segments)
                self.position = 0.0 if self.direction == 1 else 1.0
            elif self.line.is_bidirectional:
                if self.position >= 1.0 and self.current_segment_index == len(self.line.segments) - 1:
                    self.direction = -1
                elif self.position <= 0.0 and self.current_segment_index == 0:
                    self.direction = 1
                self.current_segment_index += self.direction
                self.position = 0.0 if self.direction == 1 else 1.0
            else:
                self.position = max(0.0, min(1.0, self.position))

            self.current_speed = self.calculate_speed()
        segment = self.get_current_segment()
        if segment:
            next_station = segment[0] if self.direction == -1 else segment[1]
            self.arrive_at_station(next_station)

    def get_current_segment(self):
        if not self.line.segments:
            return None
        return self.line.segments[self.current_segment_index]
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
        if color not in self.get_available_colors():
            print("Kolor zajęty lub zablokowany")
            return False
        self.selected_line_color = color
        print(f"Wybrano kolor linii: {color}")
        return True

    def add_train_to_line(self, color):
        line = self.color_to_line.get(color)
        if line and not any(t.line == line for t in self.trains):
            self.trains.append(Train(line))
            print(f"Dodano pociąg do linii {color}")

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

    def update(self, dt):
        self.elapsed_time += dt
        days_passed_now = self.elapsed_time // self.INGAME_DAY_MS
        if days_passed_now > self.total_days_passed:
            self.total_days_passed = days_passed_now
            if self.total_days_passed % self.UNLOCK_CYCLE_DAYS == 0:
                self.unlock_next_line()

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
