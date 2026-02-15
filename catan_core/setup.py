from __future__ import annotations

from collections import Counter

from .enums import ResourceType
from .game import Game


def initial_placement_order(turn_order: list[int]) -> list[int]:
    return turn_order + list(reversed(turn_order))


def grant_starting_resources_for_second_settlement(game: Game, player_id: int, vertex_id: int) -> Counter:
    payout: Counter = Counter()
    vertex = game.board.vertices[vertex_id]

    for hex_id in vertex.touching_hexes:
        hex_tile = game.board.hexes[hex_id]
        if hex_tile.resource == ResourceType.WASTELAND:
            continue
        if game.bank_resources[hex_tile.resource] <= 0:
            continue

        game.players[player_id].add_resource(hex_tile.resource, 1)
        game.bank_resources[hex_tile.resource] -= 1
        payout[hex_tile.resource] += 1

    return payout


def standard_initial_setup_auto(
    game: Game,
    prefer_ports: bool = True,
) -> list[dict[str, int | dict[str, int]]]:
    events: list[dict[str, int | dict[str, int]]] = []
    placement_counts: dict[int, int] = {player_id: 0 for player_id in game.players}

    for player_id in initial_placement_order(game.turn_order):
        candidate_vertices = list(game.board.vertices.keys())
        if prefer_ports:
            with_ports = [
                vertex_id
                for vertex_id in candidate_vertices
                if game.board.get_ports_for_vertex(vertex_id)
            ]
            without_ports = [vertex_id for vertex_id in candidate_vertices if vertex_id not in with_ports]
            candidate_vertices = with_ports + without_ports

        settlement_vertex = None
        for vertex_id in candidate_vertices:
            if game.board.can_place_settlement(vertex_id, player_id, require_connected_road=False):
                settlement_vertex = vertex_id
                break

        if settlement_vertex is None:
            raise RuntimeError(f"No valid initial settlement for player {player_id}")

        game.place_settlement(player_id, settlement_vertex, initial_placement=True)

        road_edge = None
        for edge_id in game.board.vertices[settlement_vertex].adjacent_edges:
            if game.board.can_place_road(edge_id, player_id):
                road_edge = edge_id
                break

        if road_edge is None:
            raise RuntimeError(f"No valid initial road for player {player_id}")

        game.place_road(player_id, road_edge, pay_cost=False, initial_placement=True)

        placement_counts[player_id] += 1
        payout: Counter = Counter()
        if placement_counts[player_id] == 2:
            payout = grant_starting_resources_for_second_settlement(game, player_id, settlement_vertex)

        events.append(
            {
                "player_id": player_id,
                "settlement_vertex": settlement_vertex,
                "road_edge": road_edge,
                "starting_resources": {resource.value: amount for resource, amount in payout.items()},
            }
        )

    return events
