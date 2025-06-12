import math
BASE_TRAIN_SPEED = 1  # Zależna od długości segmentu
class Train:
    def __init__(self, line, game_state=None):
        self.line = line
        self.extra_carriages = 0  
        self.current_segment_index = 0
        self.direction = 1
        self.passengers = []
        self.on_ghost_segment = False
        self.ghost_segment = None  
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
                self.ghost_segment = None
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
