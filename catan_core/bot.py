from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .enums import DevelopmentCardType, ResourceType
from .game import Game


@dataclass
class GreedyBot:
    name: str = "GreedyBot"
    max_build_actions: int = 3

    def take_turn(self, game: Game, player_id: int) -> dict[str, Any]:
        if game.current_player.player_id != player_id:
            raise ValueError("Bot can only act for the current player")

        events: list[str] = []
        d1, d2, total, payouts = game.roll_for_turn(player_id)
        events.append(f"rolled {d1}+{d2}={total}")
        if any(payouts.values()):
            events.append("received resources")

        if game.turn_phase == game.PHASE_ROBBER:
            self._resolve_robber_phase(game, player_id, events)

        if game.turn_phase == game.PHASE_TRADE:
            self._trade_phase(game, player_id, events)

        if game.turn_phase == game.PHASE_BUILD:
            self._build_phase(game, player_id, events)

        if not game.game_over:
            game.end_turn(player_id)
            events.append("ended turn")
        else:
            events.append("won game")

        return {"player_id": player_id, "events": events, "game_over": game.game_over}

    def _resolve_robber_phase(self, game: Game, player_id: int, events: list[str]) -> None:
        for discard_player_id in list(game.pending_discards):
            discarded = game.auto_discard_for_seven(discard_player_id)
            if discarded:
                events.append(f"player {discard_player_id} discarded {len(discarded)}")

        options = game.get_robber_move_options(player_id)
        if not options:
            return

        target_hex_id = max(options, key=lambda hex_id: len(options[hex_id]))
        victims = options[target_hex_id]
        victim_player_id = victims[0] if victims else None
        result = game.resolve_robber_after_seven(player_id, target_hex_id, victim_player_id=victim_player_id)
        events.append(
            f"moved robber to {result['target_hex_id']}"
            + (f" stole {result['stolen_resource']}" if result["stolen_resource"] else "")
        )

    def _trade_phase(self, game: Game, player_id: int, events: list[str]) -> None:
        player = game.players[player_id]
        target_costs = [
            game.BUILD_COSTS["city"],
            game.BUILD_COSTS["settlement"],
            game.BUILD_COSTS["road"],
            game.BUILD_COSTS["development_card"],
        ]

        for target_cost in target_costs:
            for _ in range(2):
                if player.can_afford(target_cost):
                    break
                if not self._attempt_single_trade_toward_cost(game, player_id, target_cost):
                    break
                events.append("traded with bank")

        if game.turn_phase == game.PHASE_TRADE:
            game.finish_trade_phase(player_id)

    def _attempt_single_trade_toward_cost(
        self,
        game: Game,
        player_id: int,
        cost: dict[ResourceType, int],
    ) -> bool:
        player = game.players[player_id]

        deficits = [
            resource
            for resource, amount in cost.items()
            if player.resources[resource] < amount
        ]
        if not deficits:
            return False

        for need in deficits:
            give_candidates = sorted(
                [resource for resource in player.resources if resource != need],
                key=lambda resource: player.resources[resource],
                reverse=True,
            )
            for give in give_candidates:
                rate = game.get_best_trade_rate(player_id, give)
                if player.resources[give] >= rate and game.bank_resources[need] > 0:
                    try:
                        game.trade_with_bank(player_id, give=give, receive=need)
                        return True
                    except ValueError:
                        continue
        return False

    def _build_phase(self, game: Game, player_id: int, events: list[str]) -> None:
        self._play_existing_development_card(game, player_id, events)

        for _ in range(self.max_build_actions):
            if game.game_over:
                break
            action_taken = self._take_one_build_action(game, player_id, events)
            if not action_taken:
                break

    def _play_existing_development_card(self, game: Game, player_id: int, events: list[str]) -> None:
        player = game.players[player_id]
        new_cards = set(game.new_dev_cards_by_player.get(player_id, []))

        playable_cards: list[DevelopmentCardType] = []
        for card in player.development_cards:
            if card == DevelopmentCardType.VICTORY_POINT:
                continue
            if card in new_cards:
                continue
            playable_cards.append(card)

        if not playable_cards:
            return

        card = playable_cards[0]
        try:
            if card == DevelopmentCardType.KNIGHT:
                options = game.get_robber_move_options(player_id)
                if not options:
                    return
                target_hex = max(options, key=lambda hex_id: len(options[hex_id]))
                victims = options[target_hex]
                victim = victims[0] if victims else None
                game.play_development_card(player_id, card, target_hex_id=target_hex, victim_player_id=victim)
                events.append("played Knight")
            elif card == DevelopmentCardType.ROAD_BUILDING:
                edge_ids = [edge_id for edge_id in game.board.edges if game.board.can_place_road(edge_id, player_id)][:2]
                if len(edge_ids) == 2:
                    game.play_development_card(player_id, card, edge_ids=edge_ids)
                    events.append("played Road Building")
            elif card == DevelopmentCardType.YEAR_OF_PLENTY:
                resources = sorted(
                    [ResourceType.TIMBER, ResourceType.STONE, ResourceType.MEAT, ResourceType.GRAIN, ResourceType.IRON],
                    key=lambda resource: game.players[player_id].resources[resource],
                )[:2]
                game.play_development_card(player_id, card, resources=resources)
                events.append("played Year of Plenty")
            elif card == DevelopmentCardType.MONOPOLY:
                candidate_resources = [ResourceType.TIMBER, ResourceType.STONE, ResourceType.MEAT, ResourceType.GRAIN, ResourceType.IRON]
                best_resource = max(
                    candidate_resources,
                    key=lambda resource: sum(
                        other.resources[resource]
                        for pid, other in game.players.items()
                        if pid != player_id
                    ),
                )
                game.play_development_card(player_id, card, resource=best_resource)
                events.append("played Monopoly")
        except ValueError:
            return

    def _take_one_build_action(self, game: Game, player_id: int, events: list[str]) -> bool:
        player = game.players[player_id]

        if player.settlements and player.can_afford(game.BUILD_COSTS["city"]):
            for vertex_id in sorted(player.settlements):
                try:
                    game.upgrade_to_city(player_id, vertex_id)
                    events.append(f"upgraded city at {vertex_id}")
                    return True
                except ValueError:
                    continue

        if player.can_afford(game.BUILD_COSTS["settlement"]):
            for vertex_id in game.board.vertices:
                if game.board.can_place_settlement(vertex_id, player_id, require_connected_road=True):
                    try:
                        game.place_settlement(player_id, vertex_id)
                        events.append(f"built settlement at {vertex_id}")
                        return True
                    except ValueError:
                        pass

        if player.can_afford(game.BUILD_COSTS["road"]):
            for edge_id in game.board.edges:
                if game.board.can_place_road(edge_id, player_id):
                    try:
                        game.place_road(player_id, edge_id)
                        events.append(f"built road at {edge_id}")
                        return True
                    except ValueError:
                        pass

        if player.can_afford(game.BUILD_COSTS["development_card"]):
            try:
                card = game.buy_development_card(player_id)
                events.append(f"bought dev card {card.value}")
                return True
            except ValueError:
                pass

        return False
