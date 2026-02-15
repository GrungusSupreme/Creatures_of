from __future__ import annotations

from catan_core import Game
from catan_core.render_pygame import run_playable_gui


def main() -> None:
    game = Game(player_names=["Alice", "Bob", "Cara"], seed=42)
    run_playable_gui(game)


if __name__ == "__main__":
    main()
