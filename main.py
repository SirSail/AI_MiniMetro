import pygame
from game.game_state import GameState
from render import draw_game, draw_hud, Camera



pygame.init()
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Mini Metro AI")
clock = pygame.time.Clock()

game = GameState(SCREEN_WIDTH, SCREEN_HEIGHT)
camera = Camera(game.width, game.height, SCREEN_WIDTH, SCREEN_HEIGHT)

# Ustaw kamerę na startowych stacjach
points = [(s.x, s.y) for s in game.stations]
camera.center_on_points(points)

start_ticks = pygame.time.get_ticks()

running = True
while running:
    dt = clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        camera.handle_event(event)

        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # lewy przycisk myszy
                game.handle_mouse_down(event.button, event.pos, camera)

        if event.type == pygame.MOUSEBUTTONUP:
            game.handle_mouse_up(event.pos, camera)
            
        if event.type == pygame.MOUSEMOTION:
            game.handle_mouse_motion(event.pos, camera)
    


    game.update(dt)

    
    if any(station.is_overloaded for station in game.stations):
        print("🛑 PRZEGRANA! Stacja została przepełniona.")
        running = False  

    screen.fill((255, 255, 255))
    draw_game(screen, game, camera)

    seconds = (pygame.time.get_ticks() - start_ticks) // 1000
    score = seconds * 10
    draw_hud(screen, game)

    pygame.display.flip()

pygame.quit()