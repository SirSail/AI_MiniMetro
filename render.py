import pygame
import math
from collections import defaultdict
from game.game_state import GameState


from models.station import Station
from models.line import Line
from models.train import Train
from models.passenger import Passenger
from game.game_state import LINE_COLORS, STATION_RADIUS, TRAIN_ICON_SIZE, TRAIN_ICON_PADDING


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





def draw_hud(screen, game_state):
    hud_rect = pygame.Rect(screen.get_width() - 220, 10, 200, 60)
    pygame.draw.rect(screen, (30, 30, 30), hud_rect, border_radius=8)
    pygame.draw.rect(screen, (200, 200, 200), hud_rect, 2, border_radius=8)
    
    # Tekst dnia i wyniku
    day_label = game_state.get_current_day_label()
    font = pygame.font.SysFont("Arial", 24)
    time_text = font.render(day_label, True, (255, 255, 255))
    score_text = font.render(f"Pasażerowie: {game_state.total_score}", True, (255, 255, 255))
    base_x, base_y = 20, screen.get_height() - 50
    size, padding = 30, 10

    for i, color in enumerate(LINE_COLORS):
        rect = pygame.Rect(base_x + i * (size + padding), base_y, size, size)
        pygame.draw.rect(screen, color, rect)
        if game_state.selected_line_color == color:
            pygame.draw.rect(screen, (0, 0, 0), rect, 3)

    screen.blit(time_text, (hud_rect.x + 10, hud_rect.y + 5))
    screen.blit(score_text, (hud_rect.x + 10, hud_rect.y + 30))


def draw_game(screen, game_state, camera):

    draw_river(screen, game_state, camera)

    # Utwórz słownik: klucz to tuple (station_a, station_b) (w uporządkowanej kolejności), wartość to lista kolorów linii na tym segmencie
    segment_map = defaultdict(list)
    for line in game_state.lines:
        for (station_a, station_b, _) in line.segments:
            if not (hasattr(station_a, 'x') and hasattr(station_b, 'x')):
                print(f"❌ Błędne segmenty: {station_a} ({type(station_a)}), {station_b} ({type(station_b)})")
                continue
            key = tuple(sorted((station_a, station_b), key=lambda s: (s.x, s.y)))
            segment_map[key].append(line.default_color)


    # Teraz narysuj segmenty z offsetem
    for (station_a, station_b), colors in segment_map.items():
        # dla każdej linii przypisz offsety np. -1, 0, 1, 2...
        offsets = list(range(-(len(colors)//2), len(colors)//2 + 1))
        if len(colors) % 2 == 0:
            # jeśli jest parzysta liczba kolorów, usuń zero z offsetów aby uniknąć podwójnego 0
            offsets.remove(0)
        for color, offset in zip(colors, offsets):
            draw_offset_line_between_stations(screen, station_a, station_b, camera, color, offset)
    if game_state.hovered_segment:
        line, a, b = game_state.hovered_segment
        mx = (a.x + b.x) // 2
        my = (a.y + b.y) // 2
        sx, sy = camera.apply((mx, my))
        pygame.draw.circle(screen, (200, 0, 0), (sx, sy), 10)
        pygame.draw.line(screen, (255, 255, 255), (sx - 5, sy - 5), (sx + 5, sy + 5), 2)
        pygame.draw.line(screen, (255, 255, 255), (sx + 5, sy - 5), (sx - 5, sy + 5), 2)
    
    # Rysuj stacje i resztę tak samo jak wcześniej
    for station in game_state.stations:
        draw_station(screen, station, camera)

    # Podświetlenie wybranej stacji
    if game_state.selected_station is not None:
        x, y = camera.apply((game_state.selected_station.x, game_state.selected_station.y))
        pygame.draw.circle(screen, (255, 255, 0), (x, y), STATION_RADIUS + 5, 3)
   
    if game_state.dragging_train_icon:
        segment_info = game_state.find_clicked_segment(pygame.mouse.get_pos())
        if segment_info:
            line, a, b = segment_info
            pygame.draw.line(screen, (255, 255, 255), camera.apply((a.x, a.y)), camera.apply((b.x, b.y)), 4)

# Rysuj pociągi + duchowe segmenty
    for train in game_state.trains:
        if train.on_ghost_segment and train.ghost_segment:
            a, b, color = train.ghost_segment
            base_color = color if isinstance(color, tuple) else (200, 200, 200)
            brightened = tuple(min(255, c + 80) for c in base_color)
            draw_offset_line_between_stations(screen, a, b, camera, brightened, offset=0)


        draw_train(screen, train, camera)



    # Rysuj pasek wyboru koloru
    draw_color_picker(screen, game_state)

    draw_resource_info(screen, game_state)
    if game_state.dragging_train_icon:
        mouse_x, mouse_y = pygame.mouse.get_pos()
        pygame.draw.rect(screen, (255, 255, 255), (mouse_x - 15, mouse_y - 15, 30, 30))  # cień przeciąganej ikony
        pygame.draw.rect(screen, (200, 0, 0), (mouse_x - 15, mouse_y - 15, 30, 30))
        pygame.draw.rect(screen, (255, 255, 255), (mouse_x - 7, mouse_y - 9, 14, 18))    # symbol lokomotywy
    
    draw_hud(screen, game_state)




def draw_line_between_stations(screen, station_a, station_b, camera, color=(100, 100, 100)):
    start_pos = camera.apply((station_a.x, station_a.y))
    end_pos = camera.apply((station_b.x, station_b.y))
    pygame.draw.line(screen, color, start_pos, end_pos, 4)

def draw_offset_line_between_stations(screen, station_a, station_b, camera, color, offset=0):
    start_pos = camera.apply((station_a.x, station_a.y))
    end_pos = camera.apply((station_b.x, station_b.y))
    dx = end_pos[0] - start_pos[0]
    dy = end_pos[1] - start_pos[1]
    length = (dx ** 2 + dy ** 2) ** 0.5
    if length == 0:
        offset_x = offset_y = 0
    else:
        dx /= length
        dy /= length
        offset_x = -dy * offset * 4  # 4 to szerokość przesunięcia w pikselach
        offset_y = dx * offset * 4

    start_shifted = (start_pos[0] + offset_x, start_pos[1] + offset_y)
    end_shifted = (end_pos[0] + offset_x, end_pos[1] + offset_y)
    pygame.draw.line(screen, pygame.Color(color), start_shifted, end_shifted, 6)




def draw_train(screen, train, camera):
    segment = train.current_segment
    if not segment:
        return

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
def draw_resource_info(screen, game_state):
    font = pygame.font.SysFont("Arial", 18)
    panel_rect = pygame.Rect(20, 20, 200, 90)

    # Background panel
    pygame.draw.rect(screen, (0, 0, 0), panel_rect, border_radius=12)
    pygame.draw.rect(screen, (255, 255, 255), panel_rect, 2, border_radius=12)

    # Load icons (you must preload or handle outside for performance)
    train_icon = pygame.image.load("assets/icon_train.png").convert_alpha()
    carriage_icon = pygame.image.load("assets/icon_carriage.png").convert_alpha()
    train_icon = pygame.transform.smoothscale(train_icon, (28, 28))
    carriage_icon = pygame.transform.smoothscale(carriage_icon, (28, 28))

    # Train card
    train_card = pygame.Rect(30, 30, 60, 30)
    pygame.draw.rect(screen, (30, 30, 30), train_card, border_radius=8)
    pygame.draw.rect(screen, (255, 255, 255), train_card, 1, border_radius=8)
    screen.blit(train_icon, (train_card.x + 2, train_card.y + 1))
    train_text = font.render(f"x{game_state.available_trains}", True, (255, 255, 255))
    screen.blit(train_text, (train_card.x + 32, train_card.y + 5))
    game_state.train_card_rect = train_card

    # Carriage card
    carriage_card = pygame.Rect(110, 30, 60, 30)
    pygame.draw.rect(screen, (30, 30, 30), carriage_card, border_radius=8)
    pygame.draw.rect(screen, (255, 255, 255), carriage_card, 1, border_radius=8)
    screen.blit(carriage_icon, (carriage_card.x + 2, carriage_card.y + 1))
    carriage_text = font.render(f"x{game_state.available_carriages}", True, (255, 255, 0))
    screen.blit(carriage_text, (carriage_card.x + 32, carriage_card.y + 5))
    game_state.carriage_card_rect = carriage_card

    mouse_pos = pygame.mouse.get_pos()
    if train_card.collidepoint(mouse_pos):
        tooltip = font.render("Drag to assign train", True, (255, 255, 255))
        screen.blit(tooltip, (panel_rect.right + 10, panel_rect.top))
    elif carriage_card.collidepoint(mouse_pos):
        tooltip = font.render("Drag to assign carriage", True, (255, 255, 255))
        screen.blit(tooltip, (panel_rect.right + 10, panel_rect.top))

    if game_state.dragging_train_icon:
        mx, my = pygame.mouse.get_pos()
        screen.blit(train_icon, (mx - 14, my - 14))

    if game_state.dragging_carriage_icon:
        mx, my = pygame.mouse.get_pos()
        screen.blit(carriage_icon, (mx - 14, my - 14))






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
        'D': (255, 215, 0),
        'S': (255, 255, 0),
        'H': (0, 255, 255),
        'X': (255, 100, 100),  
    }


    color = SHAPES_COLORS.get(station.shape, (100, 100, 100))
    x, y = camera.apply((station.x, station.y))

    # Draw base station shape
# Draw base station shape with black outline
    if station.shape == 'C':
        pygame.draw.circle(screen, color, (x, y), 20)
        pygame.draw.circle(screen, (0, 0, 0), (x, y), 20, 2)
    elif station.shape == 'T':
        points = [(x, y - 20), (x - 20, y + 20), (x + 20, y + 20)]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (0, 0, 0), points, 2)
    elif station.shape == 'Q':
        rect = pygame.Rect(x - 20, y - 20, 40, 40)
        pygame.draw.rect(screen, color, rect)
        pygame.draw.rect(screen, (0, 0, 0), rect, 2)
    elif station.shape == 'D':
        points = [(x, y - 20), (x + 15, y), (x, y + 20), (x - 15, y)]
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (0, 0, 0), points, 2)
    elif station.shape == 'S':
        points = []
        for i in range(10):
            angle = i * math.pi / 5
            radius = 20 if i % 2 == 0 else 8
            px = x + math.cos(angle) * radius
            py = y + math.sin(angle) * radius
            points.append((px, py))
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (0, 0, 0), points, 2)
    elif station.shape == 'H':
        points = []
        for i in range(6):
            angle = math.pi / 3 * i
            px = x + math.cos(angle) * 20
            py = y + math.sin(angle) * 20
            points.append((px, py))
        pygame.draw.polygon(screen, color, points)
        pygame.draw.polygon(screen, (0, 0, 0), points, 2)
    elif station.shape == 'X':
        vbar = pygame.Rect(x - 6, y - 20, 12, 40)
        hbar = pygame.Rect(x - 20, y - 6, 40, 12)
        pygame.draw.rect(screen, color, vbar)
        pygame.draw.rect(screen, color, hbar)
        pygame.draw.rect(screen, (0, 0, 0), vbar, 2)
        pygame.draw.rect(screen, (0, 0, 0), hbar, 2)



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
