from __future__ import annotations

import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

from .board import Board
from .enums import DevelopmentCardType, ResourceType
from .player import Player


class Game:
    BUILD_COSTS = {
        "road": {ResourceType.TIMBER: 1, ResourceType.STONE: 1},
        "settlement": {
            ResourceType.TIMBER: 1,
            ResourceType.STONE: 1,
            ResourceType.MEAT: 1,
            ResourceType.GRAIN: 1,
        },
        "city": {ResourceType.GRAIN: 2, ResourceType.IRON: 3},
        "development_card": {ResourceType.MEAT: 1, ResourceType.GRAIN: 1, ResourceType.IRON: 1},
    }

    DEV_CARD_COUNTS = {
        DevelopmentCardType.KNIGHT: 14,
        DevelopmentCardType.VICTORY_POINT: 5,
        DevelopmentCardType.ROAD_BUILDING: 2,
        DevelopmentCardType.YEAR_OF_PLENTY: 2,
        DevelopmentCardType.MONOPOLY: 2,
    }

    PHASE_ROLL = "ROLL"
    PHASE_ROBBER = "ROBBER"
    PHASE_TRADE = "TRADE"
    PHASE_BUILD = "BUILD"
    VICTORY_POINTS_TO_WIN = 10

    def __init__(
        self,
        player_names: list[str],
        board_radius: int = 2,
        seed: int | None = None,
        custom_ports: list[dict[str, Any]] | None = None,
    ):
        if len(player_names) < 2:
            raise ValueError("At least 2 players are required")

        self.seed = seed
        self.rng = random.Random(seed)
        self.board = Board(radius=board_radius, seed=seed, custom_ports=custom_ports)
        self.players: dict[int, Player] = {
            index: Player(player_id=index, name=name) for index, name in enumerate(player_names)
        }
        self.turn_order: list[int] = list(self.players.keys())
        self.current_turn_index: int = 0
        self.turn_number: int = 1
        self.turn_phase: str = self.PHASE_ROLL
        self.dice_history: list[tuple[int, int]] = []
        self.development_deck: list[DevelopmentCardType] = self._create_development_deck()
        self.new_dev_cards_by_player: dict[int, list[DevelopmentCardType]] = {
            player_id: [] for player_id in self.players
        }
        self.dev_card_played_this_turn: bool = False
        self.played_knights: Counter = Counter()
        self.pending_discards: dict[int, int] = {}
        self.longest_road_lengths: dict[int, int] = {player_id: 0 for player_id in self.players}
        self.longest_road_holder: int | None = None
        self.largest_army_holder: int | None = None
        self.robber_hex_id: int = self._initial_robber_hex_id()
        self.game_over: bool = False
        self.winner_player_id: int | None = None

        self.bank_resources = Counter(
            {
                ResourceType.TIMBER: 19,
                ResourceType.STONE: 19,
                ResourceType.MEAT: 19,
                ResourceType.GRAIN: 19,
                ResourceType.IRON: 19,
            }
        )

    @property
    def current_player(self) -> Player:
        return self.players[self.turn_order[self.current_turn_index]]

    @property
    def winner(self) -> Player | None:
        if self.winner_player_id is None:
            return None
        return self.players[self.winner_player_id]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "board_radius": self.board.radius,
            "turn_order": self.turn_order,
            "current_turn_index": self.current_turn_index,
            "turn_number": self.turn_number,
            "turn_phase": self.turn_phase,
            "dice_history": self.dice_history,
            "robber_hex_id": self.robber_hex_id,
            "pending_discards": dict(self.pending_discards),
            "longest_road_lengths": dict(self.longest_road_lengths),
            "longest_road_holder": self.longest_road_holder,
            "largest_army_holder": self.largest_army_holder,
            "played_knights": dict(self.played_knights),
            "game_over": self.game_over,
            "winner_player_id": self.winner_player_id,
            "bank_resources": {resource.value: amount for resource, amount in self.bank_resources.items()},
            "development_deck": [card.value for card in self.development_deck],
            "dev_card_played_this_turn": self.dev_card_played_this_turn,
            "new_dev_cards_by_player": {
                str(player_id): [card.value for card in cards]
                for player_id, cards in self.new_dev_cards_by_player.items()
            },
            "players": {
                str(player_id): {
                    "name": player.name,
                    "resources": {resource.value: amount for resource, amount in player.resources.items()},
                    "development_cards": [card.value for card in player.development_cards],
                    "victory_points": player.victory_points,
                    "settlements": sorted(player.settlements),
                    "cities": sorted(player.cities),
                    "roads": sorted(player.roads),
                }
                for player_id, player in self.players.items()
            },
            "board": {
                "hexes": {
                    str(hex_id): {
                        "resource": hex_tile.resource.value,
                        "token": hex_tile.token,
                    }
                    for hex_id, hex_tile in self.board.hexes.items()
                },
                "vertices": {
                    str(vertex_id): {
                        "building_owner": vertex.building_owner,
                        "building_level": vertex.building_level,
                    }
                    for vertex_id, vertex in self.board.vertices.items()
                },
                "edges": {
                    str(edge_id): {
                        "road_owner": edge.road_owner,
                    }
                    for edge_id, edge in self.board.edges.items()
                },
                "ports": [
                    {
                        "edge_id": port.edge_id,
                        "rate": port.rate,
                        "resource": port.resource.value if port.resource else None,
                    }
                    for port in self.board.ports.values()
                ],
            },
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> Game:
        players_blob = payload["players"]
        player_ids = sorted(int(pid) for pid in players_blob.keys())
        player_names = [players_blob[str(pid)]["name"] for pid in player_ids]

        game = cls(
            player_names=player_names,
            board_radius=int(payload["board_radius"]),
            seed=payload.get("seed"),
            custom_ports=payload.get("board", {}).get("ports"),
        )

        game.turn_order = [int(pid) for pid in payload["turn_order"]]
        game.current_turn_index = int(payload["current_turn_index"])
        game.turn_number = int(payload["turn_number"])
        game.turn_phase = str(payload["turn_phase"])
        game.dice_history = [tuple(item) for item in payload.get("dice_history", [])]

        game.robber_hex_id = int(payload["robber_hex_id"])
        game.pending_discards = {int(pid): int(count) for pid, count in payload.get("pending_discards", {}).items()}
        game.longest_road_lengths = {
            int(pid): int(length) for pid, length in payload.get("longest_road_lengths", {}).items()
        }
        game.longest_road_holder = payload.get("longest_road_holder")
        if game.longest_road_holder is not None:
            game.longest_road_holder = int(game.longest_road_holder)
        game.largest_army_holder = payload.get("largest_army_holder")
        if game.largest_army_holder is not None:
            game.largest_army_holder = int(game.largest_army_holder)
        game.played_knights = Counter({int(pid): int(v) for pid, v in payload.get("played_knights", {}).items()})

        game.game_over = bool(payload.get("game_over", False))
        game.winner_player_id = payload.get("winner_player_id")
        if game.winner_player_id is not None:
            game.winner_player_id = int(game.winner_player_id)

        game.bank_resources = Counter(
            {
                ResourceType(resource_name): int(amount)
                for resource_name, amount in payload["bank_resources"].items()
            }
        )
        game.development_deck = [DevelopmentCardType(card_name) for card_name in payload["development_deck"]]
        game.dev_card_played_this_turn = bool(payload.get("dev_card_played_this_turn", False))
        game.new_dev_cards_by_player = {
            int(pid): [DevelopmentCardType(card_name) for card_name in cards]
            for pid, cards in payload.get("new_dev_cards_by_player", {}).items()
        }

        for pid_str, player_blob in players_blob.items():
            pid = int(pid_str)
            player = game.players[pid]
            player.resources = Counter(
                {
                    ResourceType(resource_name): int(amount)
                    for resource_name, amount in player_blob.get("resources", {}).items()
                }
            )
            player.development_cards = [
                DevelopmentCardType(card_name) for card_name in player_blob.get("development_cards", [])
            ]
            player.victory_points = int(player_blob.get("victory_points", 0))
            player.settlements = set(int(v_id) for v_id in player_blob.get("settlements", []))
            player.cities = set(int(v_id) for v_id in player_blob.get("cities", []))
            player.roads = set(int(e_id) for e_id in player_blob.get("roads", []))

        for hex_id_str, hex_blob in payload.get("board", {}).get("hexes", {}).items():
            hex_tile = game.board.hexes[int(hex_id_str)]
            hex_tile.resource = ResourceType(hex_blob["resource"])
            hex_tile.token = hex_blob.get("token")

        for vertex_id_str, vertex_blob in payload.get("board", {}).get("vertices", {}).items():
            vertex = game.board.vertices[int(vertex_id_str)]
            vertex.building_owner = vertex_blob.get("building_owner")
            if vertex.building_owner is not None:
                vertex.building_owner = int(vertex.building_owner)
            vertex.building_level = int(vertex_blob.get("building_level", 0))

        for edge_id_str, edge_blob in payload.get("board", {}).get("edges", {}).items():
            edge = game.board.edges[int(edge_id_str)]
            edge.road_owner = edge_blob.get("road_owner")
            if edge.road_owner is not None:
                edge.road_owner = int(edge.road_owner)

        return game

    def save_json(self, file_path: str | Path) -> None:
        target = Path(file_path)
        target.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, file_path: str | Path) -> Game:
        source = Path(file_path)
        payload = json.loads(source.read_text(encoding="utf-8"))
        return cls.from_dict(payload)

    def next_turn(self) -> Player:
        self._ensure_game_active()
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        self.turn_phase = self.PHASE_ROLL
        self.dev_card_played_this_turn = False
        if self.current_turn_index == 0:
            self.turn_number += 1
        return self.current_player

    def _create_development_deck(self) -> list[DevelopmentCardType]:
        deck: list[DevelopmentCardType] = []
        for card_type, count in self.DEV_CARD_COUNTS.items():
            deck.extend([card_type] * count)
        self.rng.shuffle(deck)
        return deck

    def _initial_robber_hex_id(self) -> int:
        for hex_tile in self.board.hexes.values():
            if hex_tile.resource == ResourceType.WASTELAND:
                return hex_tile.hex_id
        return next(iter(self.board.hexes))

    def _require_current_player(self, player_id: int) -> None:
        if self.current_player.player_id != player_id:
            raise ValueError("Action must be performed by the current player")

    def _ensure_game_active(self) -> None:
        if self.game_over:
            winner_name = self.winner.name if self.winner else "Unknown"
            raise ValueError(f"Game is over. Winner: {winner_name}")

    def _require_phase(self, allowed_phases: tuple[str, ...]) -> None:
        if self.turn_phase not in allowed_phases:
            allowed = ", ".join(allowed_phases)
            raise ValueError(f"Action not allowed in phase {self.turn_phase}. Allowed: {allowed}")

    def _pay_cost_to_bank(self, player_id: int, cost: dict[ResourceType, int], pay_cost: bool) -> None:
        if not pay_cost:
            return

        player = self.players[player_id]
        player.spend_resources(cost)
        for resource, amount in cost.items():
            self.bank_resources[resource] += amount

    def _total_resource_cards(self, player_id: int) -> int:
        return sum(self.players[player_id].resources.values())

    def _add_victory_points(self, player_id: int, amount: int) -> None:
        self.players[player_id].victory_points += amount
        self._update_game_over_if_needed(player_id)

    def _remove_victory_points(self, player_id: int, amount: int) -> None:
        self.players[player_id].victory_points -= amount

    def _update_game_over_if_needed(self, player_id: int) -> None:
        if self.players[player_id].victory_points >= self.VICTORY_POINTS_TO_WIN:
            self.game_over = True
            self.winner_player_id = player_id

    def _apply_award_change(self, old_holder: int | None, new_holder: int | None) -> None:
        if old_holder is not None and old_holder in self.players:
            self._remove_victory_points(old_holder, 2)
        if new_holder is not None and new_holder in self.players:
            self._add_victory_points(new_holder, 2)

    def _recompute_largest_army(self) -> None:
        best_count = max(self.played_knights.values(), default=0)
        contenders = [player_id for player_id, count in self.played_knights.items() if count == best_count]
        new_holder: int | None = None
        if best_count >= 3:
            if len(contenders) == 1:
                new_holder = contenders[0]
            elif self.largest_army_holder in contenders:
                new_holder = self.largest_army_holder

        if new_holder != self.largest_army_holder:
            self._apply_award_change(self.largest_army_holder, new_holder)
            self.largest_army_holder = new_holder

    def _is_blocking_vertex(self, vertex_id: int, player_id: int) -> bool:
        vertex = self.board.vertices[vertex_id]
        return vertex.occupied and vertex.building_owner is not None and vertex.building_owner != player_id

    def _compute_longest_road_for_player(self, player_id: int) -> int:
        player = self.players[player_id]
        if not player.roads:
            return 0

        def walk(current_vertex: int, used_edges: set[int]) -> int:
            best = len(used_edges)
            if self._is_blocking_vertex(current_vertex, player_id):
                return best

            for edge_id in self.board.vertices[current_vertex].adjacent_edges:
                if edge_id in used_edges:
                    continue
                edge = self.board.edges[edge_id]
                if edge.road_owner != player_id:
                    continue
                next_vertex = edge.v2 if edge.v1 == current_vertex else edge.v1
                best = max(best, walk(next_vertex, used_edges | {edge_id}))
            return best

        best_length = 0
        for edge_id in player.roads:
            edge = self.board.edges[edge_id]
            best_length = max(best_length, walk(edge.v1, {edge_id}))
            best_length = max(best_length, walk(edge.v2, {edge_id}))

        return best_length

    def _recompute_longest_road(self) -> None:
        for player_id in self.players:
            self.longest_road_lengths[player_id] = self._compute_longest_road_for_player(player_id)

        best_length = max(self.longest_road_lengths.values(), default=0)
        contenders = [
            player_id
            for player_id, length in self.longest_road_lengths.items()
            if length == best_length
        ]

        new_holder: int | None = None
        if best_length >= 5:
            if len(contenders) == 1:
                new_holder = contenders[0]
            elif self.longest_road_holder in contenders:
                new_holder = self.longest_road_holder

        if new_holder != self.longest_road_holder:
            self._apply_award_change(self.longest_road_holder, new_holder)
            self.longest_road_holder = new_holder

    def roll_dice(self) -> tuple[int, int, int]:
        d1 = self.rng.randint(1, 6)
        d2 = self.rng.randint(1, 6)
        total = d1 + d2
        self.dice_history.append((d1, d2))
        return d1, d2, total

    def roll_for_turn(self, player_id: int) -> tuple[int, int, int, dict[int, Counter]]:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_ROLL,))
        d1, d2, total = self.roll_dice()
        if total == 7:
            payouts = {pid: Counter() for pid in self.players}
            self.pending_discards = {
                pid: self._total_resource_cards(pid) // 2
                for pid in self.players
                if self._total_resource_cards(pid) > 7
            }
            self.turn_phase = self.PHASE_ROBBER
        else:
            payouts = self.distribute_resources(total)
            self.turn_phase = self.PHASE_TRADE
        return d1, d2, total, payouts

    def finish_trade_phase(self, player_id: int) -> None:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_TRADE,))
        self.turn_phase = self.PHASE_BUILD

    def end_turn(self, player_id: int) -> Player:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_TRADE, self.PHASE_BUILD))
        self.new_dev_cards_by_player[player_id].clear()
        return self.next_turn()

    def get_player_port_rates(self, player_id: int) -> dict[ResourceType | None, int]:
        player = self.players[player_id]
        rates: dict[ResourceType | None, int] = {None: 4}
        occupied_vertices = player.settlements | player.cities

        for port in self.board.ports.values():
            if not occupied_vertices.intersection(port.vertex_ids):
                continue
            if port.resource is None:
                rates[None] = min(rates.get(None, 4), port.rate)
            else:
                rates[port.resource] = min(rates.get(port.resource, 4), port.rate)

        return rates

    def get_best_trade_rate(self, player_id: int, give: ResourceType) -> int:
        rates = self.get_player_port_rates(player_id)
        return min(rates.get(give, 4), rates.get(None, 4))

    def get_robber_target_hexes(self) -> list[int]:
        return [hex_id for hex_id in self.board.hexes if hex_id != self.robber_hex_id]

    def get_eligible_robber_victims(self, acting_player_id: int, target_hex_id: int) -> list[int]:
        return self._eligible_robber_victims(acting_player_id, target_hex_id)

    def get_robber_move_options(self, acting_player_id: int) -> dict[int, list[int]]:
        options: dict[int, list[int]] = {}
        for hex_id in self.get_robber_target_hexes():
            options[hex_id] = self.get_eligible_robber_victims(acting_player_id, hex_id)
        return options

    def discard_for_seven(self, player_id: int, resources_to_discard: list[ResourceType]) -> None:
        self._ensure_game_active()
        self._require_phase((self.PHASE_ROBBER,))
        required = self.pending_discards.get(player_id, 0)
        if required == 0:
            raise ValueError("Player has no pending discard requirement")
        if len(resources_to_discard) != required:
            raise ValueError(f"Player must discard exactly {required} cards")

        player = self.players[player_id]
        staged: Counter = Counter(resources_to_discard)
        for resource, amount in staged.items():
            if not isinstance(resource, ResourceType) or resource == ResourceType.WASTELAND:
                raise ValueError("Discard list contains invalid resource")
            if player.resources[resource] < amount:
                raise ValueError(f"Player lacks enough {resource.value} to discard")

        for resource, amount in staged.items():
            player.remove_resource(resource, amount)
            self.bank_resources[resource] += amount

        del self.pending_discards[player_id]

    def auto_discard_for_seven(self, player_id: int) -> list[ResourceType]:
        self._ensure_game_active()
        self._require_phase((self.PHASE_ROBBER,))
        required = self.pending_discards.get(player_id, 0)
        if required == 0:
            return []

        player = self.players[player_id]
        pool: list[ResourceType] = []
        for resource, amount in player.resources.items():
            if resource == ResourceType.WASTELAND:
                continue
            pool.extend([resource] * amount)

        if len(pool) < required:
            raise ValueError("Not enough resources available to discard")

        discarded: list[ResourceType] = self.rng.sample(pool, required)
        self.discard_for_seven(player_id, discarded)
        return discarded

    def _eligible_robber_victims(self, acting_player_id: int, target_hex_id: int) -> list[int]:
        if target_hex_id not in self.board.hexes:
            raise ValueError("Invalid target hex")

        eligible: list[int] = []
        seen: set[int] = set()
        for vertex_id in self.board.hexes[target_hex_id].vertex_ids:
            vertex = self.board.vertices[vertex_id]
            owner = vertex.building_owner
            if owner is None or owner == acting_player_id:
                continue
            if owner in seen:
                continue
            if self._total_resource_cards(owner) <= 0:
                continue
            seen.add(owner)
            eligible.append(owner)
        return eligible

    def move_robber_and_steal(
        self,
        acting_player_id: int,
        target_hex_id: int,
        victim_player_id: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_game_active()
        self._require_current_player(acting_player_id)
        if target_hex_id not in self.board.hexes:
            raise ValueError("Invalid target hex")
        if target_hex_id == self.robber_hex_id:
            raise ValueError("Robber must move to a different hex")

        eligible_victims = self._eligible_robber_victims(acting_player_id, target_hex_id)
        chosen_victim: int | None = None

        if victim_player_id is not None:
            if victim_player_id not in eligible_victims:
                raise ValueError("Selected victim is not eligible on the target hex")
            chosen_victim = victim_player_id
        elif eligible_victims:
            chosen_victim = self.rng.choice(eligible_victims)

        self.robber_hex_id = target_hex_id

        stolen_resource: ResourceType | None = None
        if chosen_victim is not None:
            victim = self.players[chosen_victim]
            bag: list[ResourceType] = []
            for resource, amount in victim.resources.items():
                if resource == ResourceType.WASTELAND:
                    continue
                bag.extend([resource] * amount)
            if bag:
                stolen_resource = self.rng.choice(bag)
                victim.remove_resource(stolen_resource, 1)
                self.players[acting_player_id].add_resource(stolen_resource, 1)

        return {
            "target_hex_id": target_hex_id,
            "victim_player_id": chosen_victim,
            "stolen_resource": stolen_resource.value if stolen_resource else None,
        }

    def resolve_robber_after_seven(
        self,
        acting_player_id: int,
        target_hex_id: int,
        victim_player_id: int | None = None,
    ) -> dict[str, Any]:
        self._ensure_game_active()
        self._require_current_player(acting_player_id)
        self._require_phase((self.PHASE_ROBBER,))
        if self.pending_discards:
            raise ValueError("All required discards must be completed before moving the robber")

        result = self.move_robber_and_steal(acting_player_id, target_hex_id, victim_player_id)
        self.turn_phase = self.PHASE_TRADE
        return result

    def distribute_resources(self, roll_total: int) -> dict[int, Counter]:
        payouts: dict[int, Counter] = {player_id: Counter() for player_id in self.players}

        for hex_tile in self.board.hexes.values():
            if hex_tile.token != roll_total:
                continue
            if hex_tile.resource == ResourceType.WASTELAND:
                continue
            if hex_tile.hex_id == self.robber_hex_id:
                continue

            for vertex_id in hex_tile.vertex_ids:
                vertex = self.board.vertices[vertex_id]
                if not vertex.occupied:
                    continue

                owner = vertex.building_owner
                if owner is None:
                    continue

                amount = 2 if vertex.building_level == 2 else 1
                available = self.bank_resources[hex_tile.resource]
                to_pay = min(amount, available)
                if to_pay <= 0:
                    continue

                self.players[owner].add_resource(hex_tile.resource, to_pay)
                self.bank_resources[hex_tile.resource] -= to_pay
                payouts[owner][hex_tile.resource] += to_pay

        return payouts

    def place_settlement(self, player_id: int, vertex_id: int, initial_placement: bool = False) -> None:
        self._ensure_game_active()
        if player_id not in self.players:
            raise ValueError("Invalid player_id")

        if not initial_placement:
            self._require_current_player(player_id)
            self._require_phase((self.PHASE_BUILD,))
            self._pay_cost_to_bank(player_id, self.BUILD_COSTS["settlement"], pay_cost=True)

        require_road = not initial_placement
        if not self.board.can_place_settlement(vertex_id, player_id, require_connected_road=require_road):
            if not initial_placement:
                for resource, amount in self.BUILD_COSTS["settlement"].items():
                    self.players[player_id].add_resource(resource, amount)
                    self.bank_resources[resource] -= amount
            raise ValueError("Settlement placement is invalid")

        vertex = self.board.vertices[vertex_id]
        vertex.building_owner = player_id
        vertex.building_level = 1

        player = self.players[player_id]
        player.settlements.add(vertex_id)
        self._add_victory_points(player_id, 1)
        self._recompute_longest_road()

    def upgrade_to_city(self, player_id: int, vertex_id: int, pay_cost: bool = True) -> None:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_BUILD,))

        self._pay_cost_to_bank(player_id, self.BUILD_COSTS["city"], pay_cost=pay_cost)
        player = self.players[player_id]
        vertex = self.board.vertices[vertex_id]

        if vertex.building_owner != player_id or vertex.building_level != 1:
            if pay_cost:
                for resource, amount in self.BUILD_COSTS["city"].items():
                    player.add_resource(resource, amount)
                    self.bank_resources[resource] -= amount
            raise ValueError("Player must own a settlement on this vertex to upgrade")

        vertex.building_level = 2
        if vertex_id in player.settlements:
            player.settlements.remove(vertex_id)
        player.cities.add(vertex_id)
        self._add_victory_points(player_id, 1)

    def place_road(self, player_id: int, edge_id: int, pay_cost: bool = True, initial_placement: bool = False) -> None:
        self._ensure_game_active()
        if player_id not in self.players:
            raise ValueError("Invalid player_id")

        if not initial_placement:
            self._require_current_player(player_id)
            self._require_phase((self.PHASE_BUILD,))

        self._pay_cost_to_bank(player_id, self.BUILD_COSTS["road"], pay_cost=pay_cost)

        if not self.board.can_place_road(edge_id, player_id):
            if pay_cost:
                for resource, amount in self.BUILD_COSTS["road"].items():
                    self.players[player_id].add_resource(resource, amount)
                    self.bank_resources[resource] -= amount
            raise ValueError("Road placement is invalid")

        edge = self.board.edges[edge_id]
        edge.road_owner = player_id
        self.players[player_id].roads.add(edge_id)
        self._recompute_longest_road()

    def trade_with_bank(
        self,
        player_id: int,
        give: ResourceType,
        receive: ResourceType,
        rate: int | None = None,
    ) -> None:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_TRADE,))

        if give == receive:
            raise ValueError("Give and receive resources must differ")
        best_rate = self.get_best_trade_rate(player_id, give)
        resolved_rate = best_rate if rate is None else rate
        if resolved_rate < best_rate:
            raise ValueError("Trade rate is better than player's available port rate")
        if resolved_rate <= 0:
            raise ValueError("Trade rate must be > 0")

        player = self.players[player_id]
        if player.resources[give] < resolved_rate:
            raise ValueError("Player does not have enough resources to trade")
        if self.bank_resources[receive] < 1:
            raise ValueError("Bank does not have requested resource")

        player.remove_resource(give, resolved_rate)
        self.bank_resources[give] += resolved_rate

        player.add_resource(receive, 1)
        self.bank_resources[receive] -= 1

    def buy_development_card(self, player_id: int) -> DevelopmentCardType:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_BUILD,))

        if not self.development_deck:
            raise ValueError("No development cards remain in the deck")

        self._pay_cost_to_bank(player_id, self.BUILD_COSTS["development_card"], pay_cost=True)

        card = self.development_deck.pop()
        player = self.players[player_id]
        player.development_cards.append(card)
        self.new_dev_cards_by_player[player_id].append(card)

        if card == DevelopmentCardType.VICTORY_POINT:
            self._add_victory_points(player_id, 1)

        return card

    def play_development_card(self, player_id: int, card: DevelopmentCardType, **kwargs: Any) -> dict[str, Any]:
        self._ensure_game_active()
        self._require_current_player(player_id)
        self._require_phase((self.PHASE_BUILD,))

        if self.dev_card_played_this_turn:
            raise ValueError("Only one development card can be played per turn")

        player = self.players[player_id]
        if card not in player.development_cards:
            raise ValueError("Player does not have this development card")

        if card == DevelopmentCardType.VICTORY_POINT:
            raise ValueError("Victory Point cards are scored when drawn and are not actively played")

        if card in self.new_dev_cards_by_player[player_id]:
            raise ValueError("Cannot play a development card on the same turn it was purchased")

        player.development_cards.remove(card)

        if card == DevelopmentCardType.KNIGHT:
            target_hex_id = kwargs.get("target_hex_id")
            victim_player_id = kwargs.get("victim_player_id")
            if not isinstance(target_hex_id, int):
                player.development_cards.append(card)
                raise ValueError("KNIGHT requires target_hex_id=<int>")
            robber_result = self.move_robber_and_steal(player_id, target_hex_id, victim_player_id)
            self.played_knights[player_id] += 1
            self._recompute_largest_army()
            self.dev_card_played_this_turn = True
            return {
                "card": card.value,
                "played_knights": self.played_knights[player_id],
                **robber_result,
            }

        if card == DevelopmentCardType.ROAD_BUILDING:
            edge_ids = kwargs.get("edge_ids")
            if not isinstance(edge_ids, (list, tuple)) or len(edge_ids) != 2:
                player.development_cards.append(card)
                raise ValueError("ROAD_BUILDING requires edge_ids=[edge_id_1, edge_id_2]")

            placed_edges: list[int] = []
            try:
                for edge_id in edge_ids:
                    self.place_road(player_id, edge_id=edge_id, pay_cost=False)
                    placed_edges.append(edge_id)
            except Exception as exc:
                for edge_id in placed_edges:
                    self.board.edges[edge_id].road_owner = None
                    self.players[player_id].roads.remove(edge_id)
                player.development_cards.append(card)
                raise ValueError(f"ROAD_BUILDING failed: {exc}") from exc

            self.dev_card_played_this_turn = True
            return {"card": card.value, "placed_edges": placed_edges}

        if card == DevelopmentCardType.YEAR_OF_PLENTY:
            resources = kwargs.get("resources")
            if not isinstance(resources, (list, tuple)) or len(resources) != 2:
                player.development_cards.append(card)
                raise ValueError("YEAR_OF_PLENTY requires resources=[res1, res2]")

            granted: list[ResourceType] = []
            try:
                for resource in resources:
                    if not isinstance(resource, ResourceType):
                        raise ValueError("resources must be ResourceType values")
                    if resource == ResourceType.WASTELAND:
                        raise ValueError("Wasteland cannot be collected")
                    if self.bank_resources[resource] < 1:
                        raise ValueError(f"Bank has no {resource.value} available")
                    self.bank_resources[resource] -= 1
                    player.add_resource(resource, 1)
                    granted.append(resource)
            except Exception as exc:
                for resource in granted:
                    player.remove_resource(resource, 1)
                    self.bank_resources[resource] += 1
                player.development_cards.append(card)
                raise ValueError(f"YEAR_OF_PLENTY failed: {exc}") from exc

            self.dev_card_played_this_turn = True
            return {"card": card.value, "resources": [resource.value for resource in granted]}

        if card == DevelopmentCardType.MONOPOLY:
            resource = kwargs.get("resource")
            if not isinstance(resource, ResourceType) or resource == ResourceType.WASTELAND:
                player.development_cards.append(card)
                raise ValueError("MONOPOLY requires resource=<non-wasteland ResourceType>")

            stolen_total = 0
            for other_id, other_player in self.players.items():
                if other_id == player_id:
                    continue
                amount = other_player.resources[resource]
                if amount <= 0:
                    continue
                other_player.remove_resource(resource, amount)
                player.add_resource(resource, amount)
                stolen_total += amount

            self.dev_card_played_this_turn = True
            return {"card": card.value, "resource": resource.value, "stolen_total": stolen_total}

        player.development_cards.append(card)
        raise ValueError(f"Unsupported development card: {card.value}")
