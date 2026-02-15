from __future__ import annotations

import math
import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .game import Game


_RESOURCE_COLORS = {
    "Timber": (74, 134, 62),
    "Stone": (133, 133, 133),
    "Meat": (178, 100, 68),
    "Grain": (218, 189, 69),
    "Iron": (92, 122, 156),
    "Wasteland": (184, 162, 126),
}


def run_basic_board_view(game: "Game", width: int = 1000, height: int = 780) -> None:
    try:
        pygame = importlib.import_module("pygame")
    except ModuleNotFoundError as exc:
        raise RuntimeError("pygame is not installed. Install it with: pip install pygame") from exc

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Creatures of Catan - Basic Board View")
    clock = pygame.time.Clock()

    center_x = width // 2
    center_y = height // 2
    hex_size = min(width, height) * 0.06

    def axial_to_pixel(q: int, r: int) -> tuple[float, float]:
        x = hex_size * math.sqrt(3) * (q + r / 2)
        y = hex_size * 1.5 * r
        return center_x + x, center_y + y

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((24, 24, 28))

        for hex_tile in game.board.hexes.values():
            cx, cy = axial_to_pixel(hex_tile.q, hex_tile.r)
            color = _RESOURCE_COLORS.get(hex_tile.resource.value, (120, 120, 120))

            points = []
            for corner in range(6):
                angle = math.radians(60 * corner - 30)
                px = cx + hex_size * math.cos(angle)
                py = cy + hex_size * math.sin(angle)
                points.append((px, py))

            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, (40, 40, 45), points, width=2)

            if hex_tile.hex_id == game.robber_hex_id:
                pygame.draw.circle(screen, (20, 20, 20), (int(cx), int(cy - 8)), int(hex_size * 0.22))

            if hex_tile.token is not None:
                pygame.draw.circle(screen, (238, 230, 210), (int(cx), int(cy + 8)), int(hex_size * 0.22))
                font = pygame.font.SysFont("arial", max(14, int(hex_size * 0.25)), bold=True)
                token_surface = font.render(str(hex_tile.token), True, (30, 30, 30))
                token_rect = token_surface.get_rect(center=(int(cx), int(cy + 8)))
                screen.blit(token_surface, token_rect)

        # Roads
        for edge in game.board.edges.values():
            v1 = game.board.vertices[edge.v1]
            v2 = game.board.vertices[edge.v2]
            if not v1.touching_hexes or not v2.touching_hexes:
                continue

            h1 = game.board.hexes[next(iter(v1.touching_hexes))]
            h2 = game.board.hexes[next(iter(v2.touching_hexes))]
            p1 = axial_to_pixel(h1.q, h1.r)
            p2 = axial_to_pixel(h2.q, h2.r)

            if edge.road_owner is None:
                continue
            color = [(220, 70, 70), (70, 140, 220), (220, 200, 70), (170, 80, 190)][edge.road_owner % 4]
            pygame.draw.line(screen, color, p1, p2, width=5)

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
