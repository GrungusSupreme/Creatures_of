from __future__ import annotations

from typing import Any

from .bot import GreedyBot
from .enums import ResourceType
from .game import Game
from .setup import standard_initial_setup_auto


def setup_initial_placements(game: Game) -> None:
    standard_initial_setup_auto(game)


def simulate_turns(game: Game, max_turns: int = 100, bot: GreedyBot | None = None) -> list[dict[str, Any]]:
    bot = bot or GreedyBot()
    history: list[dict[str, Any]] = []

    for _ in range(max_turns):
        if game.game_over:
            break

        active_player_id = game.current_player.player_id
        turn_result = bot.take_turn(game, active_player_id)
        history.append(turn_result)

    return history


def run_bot_game(
    player_names: list[str],
    max_turns: int = 200,
    seed: int | None = None,
    starting_resource_boost: bool = True,
) -> tuple[Game, list[dict[str, Any]]]:
    game = Game(player_names=player_names, seed=seed)
    setup_initial_placements(game)

    if starting_resource_boost:
        for player in game.players.values():
            for resource in [
                ResourceType.TIMBER,
                ResourceType.STONE,
                ResourceType.MEAT,
                ResourceType.GRAIN,
                ResourceType.IRON,
            ]:
                player.add_resource(resource, 2)
                game.bank_resources[resource] -= 2

    history = simulate_turns(game, max_turns=max_turns)
    return game, history
