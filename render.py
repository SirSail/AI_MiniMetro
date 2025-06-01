import pygame
from core import LINE_COLORS
from core import STATION_RADIUS
import math

TRAIN_ICON_SIZE = 30
TRAIN_ICON_PADDING = 10
class Camera:
    def __init__(self, width, height, screen_width, screen_height):
        self.width = width
        self.height = height
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.x = (self.width - self.screen_width) // 2
        self.y = (self.height - self.screen_height) // 2

        self.dragging = False
        self.last_mouse_pos = None
        self.font = pygame.font.SysFont("Arial", 24)

    def center_on_points(self, points):
        if not points:
            return
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)
        center_x = (min_x + max_x) // 2
        center_y = (min_y + max_y) // 2

        self.x = max(0, min(center_x - self.screen_width // 2, self.width - self.screen_width))
        self.y = max(0, min(center_y - self.screen_height // 2, self.height - self.screen_height))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:  # prawy przycisk
            self.dragging = True
            self.last_mouse_pos = event.pos
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.dragging = False
            self.last_mouse_pos = None
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.last_mouse_pos[0]
            dy = event.pos[1] - self.last_mouse_pos[1]
            self.x -= dx
            self.y -= dy
            self.x = max(0, min(self.x, self.width - self.screen_width))
            self.y = max(0, min(self.y, self.height - self.screen_height))
            self.last_mouse_pos = event.pos



    def apply(self, pos):
        return pos[0] - self.x, pos[1] - self.y

    def draw_hud(self, screen, seconds, score):
        hud_rect = pygame.Rect(screen.get_width() - 180, 10, 170, 50)
        pygame.draw.rect(screen, (30, 30, 30), hud_rect, border_radius=8)
        pygame.draw.rect(screen, (200, 200, 200), hud_rect, 2, border_radius=8)

        time_text = self.font.render(f"Czas: {seconds}s", True, (255, 255, 255))
        score_text = self.font.render(f"Punkty: {score}", True, (255, 255, 255))

        screen.blit(time_text, (hud_rect.x + 10, hud_rect.y + 5))
        screen.blit(score_text, (hud_rect.x + 10, hud_rect.y + 25))


# funkcje rysujące z użyciem kamery:
def draw_game(screen, game_state, camera):
    draw_river(screen, game_state, camera)

    # Rysuj wszystkie linie:
    for line in game_state.lines:
        color = line.default_color
        # Jeśli linia jest wybrana - podkreślamy ją grubszą, jaśniejszą linią
        highlight = (255, 255, 0) if game_state.selected_line_color == line.default_color else None

        for (station_a, station_b, _) in line.segments:
            if highlight:
                # najpierw rysujemy szerszą linię w kolorze highlight (żółtym)
                draw_line_between_stations(screen, station_a, station_b, camera, color=highlight)
                # potem trochę węższą w oryginalnym kolorze
                draw_line_between_stations(screen, station_a, station_b, camera, color=color)
            else:
                draw_line_between_stations(screen, station_a, station_b, camera, color=color)

    # Rysuj stacje
    for station in game_state.stations:
        draw_station(screen, station, camera)

    # Podświetlenie wybranej stacji
    if game_state.selected_station is not None:
        x, y = camera.apply((game_state.selected_station.x, game_state.selected_station.y))
        pygame.draw.circle(screen, (255, 255, 0), (x, y), STATION_RADIUS + 5, 3)

    # Rysuj pociągi
    for train in game_state.trains:
        draw_train(screen, train, camera)

    # Rysuj pasek wyboru koloru
    draw_color_picker(screen, game_state)

    draw_train_panel(screen, game_state)

def draw_line_between_stations(screen, station_a, station_b, camera, color=(100, 100, 100)):
    start_pos = camera.apply((station_a.x, station_a.y))
    end_pos = camera.apply((station_b.x, station_b.y))
    pygame.draw.line(screen, color, start_pos, end_pos, 4)



def draw_train(screen, train, camera):
    segment = train.line.segments[train.current_segment_index]
    station_a, station_b, _ = segment


    x = station_a.x + (station_b.x - station_a.x) * train.position
    y = station_a.y + (station_b.y - station_a.y) * train.position
    screen_pos = camera.apply((x, y))

        # Obrót prostokąta zgodnie z kątem kierunku pociągu
    angle = math.atan2(station_b.y - station_a.y, station_b.x - station_a.x)
    length = 30
    width = 12
    rect_surface = pygame.Surface((length, width), pygame.SRCALPHA)
    rect_surface.fill((200, 0, 0))  # kolor lokomotywy

    rotated = pygame.transform.rotate(rect_surface, -math.degrees(angle))
    rect = rotated.get_rect(center=screen_pos)
    screen.blit(rotated, rect)


    offset = 15
    dx = station_b.x - station_a.x
    dy = station_b.y - station_a.y
    length = (dx**2 + dy**2)**0.5
    if length == 0:
        length = 1
    ux = dx / length
    uy = dy / length

    wagon_x = x - ux * offset * train.direction
    wagon_y = y - uy * offset * train.direction
    wagon_pos = camera.apply((wagon_x, wagon_y))
    pygame.draw.circle(screen, (0, 0, 200), wagon_pos, 7)

    dot_radius = 4
    spacing = 10
    offset_y = 20
    max_icons = 8

    passenger_color = train.line.default_color # kolor linii jako kolor pasażera

    for i, p in enumerate(train.passengers[:max_icons]):
        px = screen_pos[0] + (i % 4 - 1.5) * spacing
        py = screen_pos[1] - offset_y - (i // 4) * spacing

        # Możesz też przypisać kolory zależnie od destination_shape:
        # shape_colors = {'C': (255,0,0), 'T': (0,255,0), 'Q': (0,0,255)}
        # passenger_color = shape_colors.get(p.destination_shape, (255,255,255))

        if p.destination_shape == 'C':
            pygame.draw.circle(screen, passenger_color, (int(px), int(py)), dot_radius)
        elif p.destination_shape == 'T':
            pygame.draw.polygon(screen, passenger_color, [
                (int(px), int(py - dot_radius)),
                (int(px - dot_radius), int(py + dot_radius)),
                (int(px + dot_radius), int(py + dot_radius))
            ])
        elif p.destination_shape == 'Q':
            pygame.draw.rect(screen, passenger_color, pygame.Rect(int(px - dot_radius), int(py - dot_radius), dot_radius * 2, dot_radius * 2))

def draw_train_panel(screen, game_state):
    base_x = 20
    base_y = screen.get_height() - 100  # nad paskiem kolorów
    size = TRAIN_ICON_SIZE
    padding = TRAIN_ICON_PADDING

    font = pygame.font.SysFont("Arial", 16)

    for i, color in enumerate(game_state.unlocked_colors):
        rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (0,0,0), rect, 2)
        
        # jeśli na linii jest już pociąg, przyciemnij panelik (oznacza brak dostępnych)
        line = game_state.color_to_line.get(color)
        train_on_line = any(t.line == line for t in game_state.trains) if line else False
        if train_on_line:
            overlay = pygame.Surface((size, size), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))  # półprzezroczyste czarne
            screen.blit(overlay, rect.topleft)

        # tekst "Add"
        text = font.render("Add", True, (255,255,255))
        text_rect = text.get_rect(center=rect.center)
        screen.blit(text, text_rect)
def draw_color_picker(screen, game_state):
    # Pasek kolorów w dolnym pasku ekranu
    base_x = 20
    base_y = screen.get_height() - 50
    size = 30
    padding = 10

    for i, color in enumerate(LINE_COLORS):
        rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
        pygame.draw.rect(screen, color, rect)
        # Obramowanie dla wybranego koloru
        if color == game_state.selected_line_color:
            pygame.draw.rect(screen, (255, 255, 0), rect, 3)
        else:
            pygame.draw.rect(screen, (0, 0, 0), rect, 1)


def draw_river(screen, game_state, camera):
    x, y = camera.apply((0, game_state.river_y - 10))
    rect = pygame.Rect(x, y, game_state.width, 20)
    pygame.draw.rect(screen, (70, 130, 180), rect)

def draw_station(screen, station, camera):
    SHAPES_COLORS = {
        'C': (200, 0, 0),
        'T': (0, 200, 0),
        'Q': (0, 0, 200),
    }

    color = SHAPES_COLORS.get(station.shape, (100, 100, 100))
    x, y = camera.apply((station.x, station.y))

    # Draw base station shape
    if station.shape == 'C':
        pygame.draw.circle(screen, color, (x, y), 20)
    elif station.shape == 'T':
        points = [
            (x, y - 20),
            (x - 20, y + 20),
            (x + 20, y + 20),
        ]
        pygame.draw.polygon(screen, color, points)
    elif station.shape == 'Q':
        pygame.draw.rect(screen, color, pygame.Rect(x - 20, y - 20, 40, 40))
    elif station.shape == 'D':
        pygame.draw.polygon(screen, (255, 215, 0), [
            (x, y - 20), (x + 15, y), (x, y + 20), (x - 15, y)
        ])

    # Draw individual passengers
    max_dots = 8
    spacing = 10
    offset_x = 10
    offset_y = 30
    dot_radius = 4

    for i, p in enumerate(station.passengers[:max_dots]):
        col = i % 2
        row = i // 2
        px = x + (col * offset_x) - (offset_x // 2)
        py = y - offset_y - (row * spacing)

        # Symbol based on passenger's destination shape
        if p.destination_shape == 'C':
            pygame.draw.circle(screen, (0, 0, 0), (px, py), dot_radius)
        elif p.destination_shape == 'T':
            pygame.draw.polygon(screen, (0, 0, 0), [
                (px, py - dot_radius),
                (px - dot_radius, py + dot_radius),
                (px + dot_radius, py + dot_radius)
            ])
        elif p.destination_shape == 'Q':
            pygame.draw.rect(screen, (0, 0, 0), pygame.Rect(px - dot_radius, py - dot_radius, dot_radius * 2, dot_radius * 2))

    # Overload visualization
    if len(station.passengers) > max_dots:
        percent = min(station.overload_timer / 5.0, 1.0)
        s = pygame.Surface((50, 50), pygame.SRCALPHA)
        pygame.draw.circle(s, (0, 0, 0, 100), (25, 25), 25)

        start_angle = -0.5 * math.pi
        end_angle = start_angle + 2 * math.pi * percent
        pygame.draw.arc(s, (255, 0, 0), (0, 0, 50, 50), start_angle, end_angle, 5)
        screen.blit(s, (x - 25, y - 25))

    if getattr(station, 'is_overloaded', False):
        pygame.draw.circle(screen, (255, 0, 0), (x, y), 28, 5)

