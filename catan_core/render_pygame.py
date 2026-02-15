from __future__ import annotations

import math
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .game import Game

from .bot import GreedyBot
from .enums import ResourceType
from .setup import standard_initial_setup_auto


_RESOURCE_COLORS = {
    "Timber": (74, 134, 62),
    "Stone": (133, 133, 133),
    "Meat": (178, 100, 68),
    "Grain": (218, 189, 69),
    "Iron": (92, 122, 156),
    "Wasteland": (184, 162, 126),
}

_PLAYER_COLORS = [
    (220, 70, 70),
    (70, 140, 220),
    (220, 200, 70),
    (170, 80, 190),
]


@dataclass
class UiButton:
    label: str
    rect: Any
    action: str


def run_playable_gui(game: "Game", width: int = 1280, height: int = 820) -> None:
    try:
        pygame = importlib.import_module("pygame")
    except ModuleNotFoundError as exc:
        raise RuntimeError("pygame is not installed. Install it with: pip install pygame-ce") from exc

    if not any(player.settlements for player in game.players.values()):
        standard_initial_setup_auto(game)

    pygame.init()
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Creatures of Catan - Playable GUI")
    clock = pygame.time.Clock()

    board_width = int(width * 0.74)
    center_x = board_width // 2
    center_y = height // 2
    hex_size = min(board_width, height) * 0.07

    small_font = pygame.font.SysFont("arial", 16)
    font = pygame.font.SysFont("arial", 18)
    big_font = pygame.font.SysFont("arial", 22, bold=True)

    pending_action: str | None = None
    message = "Click Roll to start your turn."
    trade_give = ResourceType.TIMBER
    trade_receive = ResourceType.GRAIN

    def cycle_resource(resource: ResourceType, direction: int) -> ResourceType:
        resources = [
            ResourceType.TIMBER,
            ResourceType.STONE,
            ResourceType.MEAT,
            ResourceType.GRAIN,
            ResourceType.IRON,
        ]
        idx = resources.index(resource)
        return resources[(idx + direction) % len(resources)]

    def axial_to_pixel(q: int, r: int) -> tuple[float, float]:
        x = hex_size * math.sqrt(3) * (q + r / 2)
        y = hex_size * 1.5 * r
        return center_x + x, center_y + y

    def compute_vertex_positions() -> dict[int, tuple[float, float]]:
        positions: dict[int, list[tuple[float, float]]] = {}
        for hex_tile in game.board.hexes.values():
            cx, cy = axial_to_pixel(hex_tile.q, hex_tile.r)
            for corner, vertex_id in enumerate(hex_tile.vertex_ids):
                angle = math.radians(60 * corner - 30)
                px = cx + hex_size * math.cos(angle)
                py = cy + hex_size * math.sin(angle)
                positions.setdefault(vertex_id, []).append((px, py))

        averaged: dict[int, tuple[float, float]] = {}
        for vertex_id, pts in positions.items():
            x = sum(p[0] for p in pts) / len(pts)
            y = sum(p[1] for p in pts) / len(pts)
            averaged[vertex_id] = (x, y)
        return averaged

    def get_edge_midpoint(edge_id: int, vertex_positions: dict[int, tuple[float, float]]) -> tuple[float, float]:
        edge = game.board.edges[edge_id]
        v1 = vertex_positions[edge.v1]
        v2 = vertex_positions[edge.v2]
        return ((v1[0] + v2[0]) / 2, (v1[1] + v2[1]) / 2)

    def draw_hexes() -> dict[int, tuple[float, float]]:
        centers: dict[int, tuple[float, float]] = {}
        for hex_tile in game.board.hexes.values():
            cx, cy = axial_to_pixel(hex_tile.q, hex_tile.r)
            centers[hex_tile.hex_id] = (cx, cy)
            color = _RESOURCE_COLORS.get(hex_tile.resource.value, (120, 120, 120))

            points = []
            for corner in range(6):
                angle = math.radians(60 * corner - 30)
                px = cx + hex_size * math.cos(angle)
                py = cy + hex_size * math.sin(angle)
                points.append((px, py))

            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, (35, 35, 40), points, width=2)

            if hex_tile.hex_id == game.robber_hex_id:
                pygame.draw.circle(screen, (20, 20, 20), (int(cx), int(cy - 10)), int(hex_size * 0.2))

            if hex_tile.token is not None:
                pygame.draw.circle(screen, (238, 230, 210), (int(cx), int(cy + 8)), int(hex_size * 0.22))
                token_surface = font.render(str(hex_tile.token), True, (30, 30, 30))
                token_rect = token_surface.get_rect(center=(int(cx), int(cy + 8)))
                screen.blit(token_surface, token_rect)
        return centers

    def draw_graph(vertex_positions: dict[int, tuple[float, float]]) -> None:
        for edge in game.board.edges.values():
            p1 = vertex_positions.get(edge.v1)
            p2 = vertex_positions.get(edge.v2)
            if p1 is None or p2 is None:
                continue

            if edge.road_owner is None:
                pygame.draw.line(screen, (70, 70, 74), p1, p2, width=2)
            else:
                color = _PLAYER_COLORS[edge.road_owner % len(_PLAYER_COLORS)]
                pygame.draw.line(screen, color, p1, p2, width=6)

        for vertex_id, (vx, vy) in vertex_positions.items():
            vertex = game.board.vertices[vertex_id]
            if not vertex.occupied:
                pygame.draw.circle(screen, (230, 230, 230), (int(vx), int(vy)), 4)
                continue

            owner = vertex.building_owner or 0
            color = _PLAYER_COLORS[owner % len(_PLAYER_COLORS)]
            radius = 11 if vertex.building_level == 2 else 8
            pygame.draw.circle(screen, color, (int(vx), int(vy)), radius)
            if vertex.building_level == 2:
                pygame.draw.circle(screen, (20, 20, 24), (int(vx), int(vy)), radius, width=2)

    def sidebar_buttons() -> list[UiButton]:
        panel_x = board_width + 14
        start_y = 160
        w = width - panel_x - 14
        h = 34
        spacing = 8

        items = [
            ("Roll", "roll"),
            ("Resolve Robber", "robber"),
            ("Done Trade", "done_trade"),
            ("End Turn", "end_turn"),
            ("Place Road", "place_road"),
            ("Place Settlement", "place_settlement"),
            ("Upgrade City", "upgrade_city"),
            ("Buy Dev Card", "buy_dev"),
            ("Auto Turn", "auto_turn"),
            ("Save Game", "save"),
            ("Load Game", "load"),
        ]

        result: list[UiButton] = []
        for index, (label, action) in enumerate(items):
            rect = pygame.Rect(panel_x, start_y + index * (h + spacing), w, h)
            result.append(UiButton(label=label, rect=rect, action=action))
        return result

    def draw_sidebar() -> tuple[list[UiButton], dict[str, Any]]:
        panel_rect = pygame.Rect(board_width, 0, width - board_width, height)
        pygame.draw.rect(screen, (28, 30, 36), panel_rect)

        title = big_font.render("Creatures of Catan", True, (235, 235, 240))
        screen.blit(title, (board_width + 12, 12))

        player = game.current_player
        lines = [
            f"Turn: {game.turn_number}",
            f"Phase: {game.turn_phase}",
            f"Current: {player.name}",
            f"VP: {player.victory_points}",
            "",
            "Resources:",
            f"T:{player.resources[ResourceType.TIMBER]} S:{player.resources[ResourceType.STONE]}",
            f"M:{player.resources[ResourceType.MEAT]} G:{player.resources[ResourceType.GRAIN]} I:{player.resources[ResourceType.IRON]}",
            f"Roads:{len(player.roads)} Sett:{len(player.settlements)} Cities:{len(player.cities)}",
            f"Dev cards:{len(player.development_cards)}",
        ]

        y = 46
        for line in lines:
            surf = font.render(line, True, (210, 215, 225))
            screen.blit(surf, (board_width + 12, y))
            y += 20

        trade_rect = pygame.Rect(board_width + 14, height - 136, width - board_width - 28, 108)
        pygame.draw.rect(screen, (38, 40, 48), trade_rect, border_radius=8)
        trade_title = small_font.render("Trade setup (TRADE phase)", True, (210, 215, 225))
        screen.blit(trade_title, (trade_rect.x + 10, trade_rect.y + 8))

        give_rect = pygame.Rect(trade_rect.x + 10, trade_rect.y + 34, trade_rect.width - 20, 28)
        recv_rect = pygame.Rect(trade_rect.x + 10, trade_rect.y + 68, trade_rect.width - 20, 28)
        pygame.draw.rect(screen, (58, 62, 72), give_rect, border_radius=6)
        pygame.draw.rect(screen, (58, 62, 72), recv_rect, border_radius=6)
        screen.blit(small_font.render(f"Give: {trade_give.value}", True, (235, 235, 240)), (give_rect.x + 8, give_rect.y + 6))
        screen.blit(small_font.render(f"Receive: {trade_receive.value}", True, (235, 235, 240)), (recv_rect.x + 8, recv_rect.y + 6))

        give_left = pygame.Rect(give_rect.right - 56, give_rect.y + 4, 22, 20)
        give_right = pygame.Rect(give_rect.right - 28, give_rect.y + 4, 22, 20)
        recv_left = pygame.Rect(recv_rect.right - 56, recv_rect.y + 4, 22, 20)
        recv_right = pygame.Rect(recv_rect.right - 28, recv_rect.y + 4, 22, 20)
        for rect, label in [
            (give_left, "<"),
            (give_right, ">"),
            (recv_left, "<"),
            (recv_right, ">"),
        ]:
            pygame.draw.rect(screen, (90, 95, 110), rect, border_radius=4)
            text = small_font.render(label, True, (245, 245, 250))
            screen.blit(text, text.get_rect(center=rect.center))

        buttons = sidebar_buttons()
        for button in buttons:
            active = pending_action is not None and button.action == pending_action
            fill = (90, 126, 200) if active else (64, 70, 86)
            pygame.draw.rect(screen, fill, button.rect, border_radius=8)
            label = small_font.render(button.label, True, (240, 242, 248))
            screen.blit(label, label.get_rect(center=button.rect.center))

        msg_box = pygame.Rect(12, height - 58, board_width - 24, 44)
        pygame.draw.rect(screen, (40, 42, 50), msg_box, border_radius=8)
        msg = small_font.render(message[:140], True, (235, 235, 240))
        screen.blit(msg, (msg_box.x + 8, msg_box.y + 12))

        controls = {
            "trade_give_left": give_left,
            "trade_give_right": give_right,
            "trade_recv_left": recv_left,
            "trade_recv_right": recv_right,
        }
        return buttons, controls

    def nearest_vertex(mouse_pos: tuple[int, int], vertex_positions: dict[int, tuple[float, float]]) -> int | None:
        best_id = None
        best_dist = 1e9
        for vertex_id, (vx, vy) in vertex_positions.items():
            dist = math.hypot(mouse_pos[0] - vx, mouse_pos[1] - vy)
            if dist < best_dist:
                best_dist = dist
                best_id = vertex_id
        if best_dist <= 16:
            return best_id
        return None

    def nearest_edge(mouse_pos: tuple[int, int], vertex_positions: dict[int, tuple[float, float]]) -> int | None:
        best_id = None
        best_dist = 1e9
        for edge_id in game.board.edges:
            ex, ey = get_edge_midpoint(edge_id, vertex_positions)
            dist = math.hypot(mouse_pos[0] - ex, mouse_pos[1] - ey)
            if dist < best_dist:
                best_dist = dist
                best_id = edge_id
        if best_dist <= 18:
            return best_id
        return None

    def nearest_hex(mouse_pos: tuple[int, int], hex_centers: dict[int, tuple[float, float]]) -> int | None:
        best_id = None
        best_dist = 1e9
        for hex_id, (hx, hy) in hex_centers.items():
            dist = math.hypot(mouse_pos[0] - hx, mouse_pos[1] - hy)
            if dist < best_dist:
                best_dist = dist
                best_id = hex_id
        if best_dist <= hex_size * 0.8:
            return best_id
        return None

    bot = GreedyBot(name="GUIBot")

    running = True
    while running:
        screen.fill((24, 24, 28))

        hex_centers = draw_hexes()
        vertex_positions = compute_vertex_positions()
        draw_graph(vertex_positions)
        buttons, controls = draw_sidebar()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue

            if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
                continue

            mx, my = event.pos

            if controls["trade_give_left"].collidepoint(mx, my):
                trade_give = cycle_resource(trade_give, -1)
                continue
            if controls["trade_give_right"].collidepoint(mx, my):
                trade_give = cycle_resource(trade_give, 1)
                continue
            if controls["trade_recv_left"].collidepoint(mx, my):
                trade_receive = cycle_resource(trade_receive, -1)
                continue
            if controls["trade_recv_right"].collidepoint(mx, my):
                trade_receive = cycle_resource(trade_receive, 1)
                continue

            clicked_button = next((button for button in buttons if button.rect.collidepoint(mx, my)), None)
            if clicked_button is not None:
                action = clicked_button.action
                try:
                    if action == "roll":
                        player_id = game.current_player.player_id
                        d1, d2, total, _ = game.roll_for_turn(player_id)
                        message = f"Rolled {d1}+{d2}={total}"
                    elif action == "robber":
                        pending_action = "move_robber"
                        message = "Click a target hex to move robber."
                    elif action == "done_trade":
                        game.finish_trade_phase(game.current_player.player_id)
                        message = "Trade phase complete."
                    elif action == "end_turn":
                        game.end_turn(game.current_player.player_id)
                        pending_action = None
                        message = "Turn ended."
                    elif action == "place_road":
                        pending_action = "place_road"
                        message = "Click an edge midpoint to build road."
                    elif action == "place_settlement":
                        pending_action = "place_settlement"
                        message = "Click a vertex to build settlement."
                    elif action == "upgrade_city":
                        pending_action = "upgrade_city"
                        message = "Click your settlement vertex to upgrade."
                    elif action == "buy_dev":
                        card = game.buy_development_card(game.current_player.player_id)
                        message = f"Bought dev card: {card.value}"
                    elif action == "auto_turn":
                        player_id = game.current_player.player_id
                        result = bot.take_turn(game, player_id)
                        message = "; ".join(result["events"])[:140]
                    elif action == "save":
                        save_path = Path("gui_save.json")
                        game.save_json(save_path)
                        message = f"Saved to {save_path}"
                    elif action == "load":
                        load_path = Path("gui_save.json")
                        if not load_path.exists():
                            raise ValueError("No gui_save.json found")
                        loaded = game.load_json(load_path)
                        game.__dict__.update(loaded.__dict__)
                        pending_action = None
                        message = "Loaded gui_save.json"
                except Exception as exc:
                    message = f"Error: {exc}"
                continue

            if mx >= board_width:
                continue

            if pending_action is None:
                if game.turn_phase == game.PHASE_TRADE:
                    try:
                        game.trade_with_bank(game.current_player.player_id, trade_give, trade_receive)
                        rate = game.get_best_trade_rate(game.current_player.player_id, trade_give)
                        message = f"Trade complete at {rate}:1"
                    except Exception as exc:
                        message = f"Error: {exc}"
                continue

            try:
                if pending_action == "place_road":
                    edge_id = nearest_edge((mx, my), vertex_positions)
                    if edge_id is None:
                        raise ValueError("No edge selected")
                    game.place_road(game.current_player.player_id, edge_id)
                    message = f"Built road at edge {edge_id}"
                    pending_action = None
                elif pending_action == "place_settlement":
                    vertex_id = nearest_vertex((mx, my), vertex_positions)
                    if vertex_id is None:
                        raise ValueError("No vertex selected")
                    game.place_settlement(game.current_player.player_id, vertex_id)
                    message = f"Built settlement at vertex {vertex_id}"
                    pending_action = None
                elif pending_action == "upgrade_city":
                    vertex_id = nearest_vertex((mx, my), vertex_positions)
                    if vertex_id is None:
                        raise ValueError("No vertex selected")
                    game.upgrade_to_city(game.current_player.player_id, vertex_id)
                    message = f"Upgraded city at vertex {vertex_id}"
                    pending_action = None
                elif pending_action == "move_robber":
                    for discard_player_id in list(game.pending_discards):
                        game.auto_discard_for_seven(discard_player_id)
                    hex_id = nearest_hex((mx, my), hex_centers)
                    if hex_id is None:
                        raise ValueError("No hex selected")
                    victims = game.get_eligible_robber_victims(game.current_player.player_id, hex_id)
                    victim = victims[0] if victims else None
                    result = game.resolve_robber_after_seven(game.current_player.player_id, hex_id, victim)
                    message = f"Robber moved to {result['target_hex_id']}"
                    pending_action = None
            except Exception as exc:
                message = f"Error: {exc}"

        if game.game_over:
            message = f"Game Over! Winner: {game.winner.name if game.winner else 'Unknown'}"

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


def run_basic_board_view(game: "Game", width: int = 1000, height: int = 780) -> None:
    run_playable_gui(game, width=width, height=height)
