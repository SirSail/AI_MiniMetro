from models.station import Station

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

