class Station:
    def __init__(self, x, y, shape):
        self.x = x
        self.y = y
        self.shape = shape
        self.passengers = []  
        self.overload_timer = 0.0
        self.is_overloaded = False

