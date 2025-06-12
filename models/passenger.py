class Passenger:
    def __init__(self, destination_shape):
        self.destination_shape = destination_shape
        self.current_target_station = None  # ← do aktualizacji podczas przesiadek
        self.last_train = None  # zapamiętany ostatni pociąg