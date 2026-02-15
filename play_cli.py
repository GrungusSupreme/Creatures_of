from __future__ import annotations

from pathlib import Path

from catan_core import (
    DevelopmentCardType,
    Game,
    GreedyBot,
    ResourceType,
    standard_initial_setup_auto,
)


_RESOURCE_MAP = {
    "timber": ResourceType.TIMBER,
    "stone": ResourceType.STONE,
    "meat": ResourceType.MEAT,
    "grain": ResourceType.GRAIN,
    "iron": ResourceType.IRON,
}


def safe_input(prompt: str) -> str | None:
    try:
        return input(prompt)
    except EOFError:
        return None


def parse_resource(raw: str) -> ResourceType:
    key = raw.strip().lower()
    if key not in _RESOURCE_MAP:
        valid = ", ".join(sorted(_RESOURCE_MAP.keys()))
        raise ValueError(f"Unknown resource '{raw}'. Valid: {valid}")
    return _RESOURCE_MAP[key]


def format_resources(game: Game, player_id: int) -> str:
    player = game.players[player_id]
    parts = [f"{resource.value}:{player.resources[resource]}" for resource in _RESOURCE_MAP.values()]
    return " ".join(parts)


def game_summary(game: Game) -> str:
    players = " | ".join(
        f"{player.name}(VP={player.victory_points}, S={len(player.settlements)}, C={len(player.cities)}, R={len(player.roads)})"
        for player in game.players.values()
    )
    return (
        f"Turn {game.turn_number} | Phase {game.turn_phase} | Current {game.current_player.name} | "
        f"Robber Hex {game.robber_hex_id} | {players}"
    )


def ensure_setup(game: Game) -> None:
    if any(player.settlements or player.cities or player.roads for player in game.players.values()):
        return

    events = standard_initial_setup_auto(game)
    print("Initial setup complete.")
    for event in events:
        print(
            f"- P{event['player_id']} settlement={event['settlement_vertex']} road={event['road_edge']} "
            f"start={event['starting_resources']}"
        )


def handle_robber_phase(game: Game, player_id: int) -> None:
    for discard_player_id in list(game.pending_discards):
        discarded = game.auto_discard_for_seven(discard_player_id)
        if discarded:
            print(f"Player {game.players[discard_player_id].name} auto-discarded {len(discarded)} cards.")

    options = game.get_robber_move_options(player_id)
    target_hexes = [hex_id for hex_id in options.keys()]
    print(f"Robber targets: {target_hexes}")
    choice_raw = safe_input("Target hex id (blank = auto best): ")
    if choice_raw is None:
        return
    choice = choice_raw.strip()

    if choice:
        target_hex_id = int(choice)
    else:
        target_hex_id = max(options, key=lambda hex_id: len(options[hex_id]))

    victims = options.get(target_hex_id, [])
    victim_player_id = None
    if victims:
        print("Victims:", [(vid, game.players[vid].name) for vid in victims])
        victim_raw_in = safe_input("Victim player id (blank = first): ")
        if victim_raw_in is None:
            return
        victim_raw = victim_raw_in.strip()
        victim_player_id = int(victim_raw) if victim_raw else victims[0]

    result = game.resolve_robber_after_seven(player_id, target_hex_id, victim_player_id=victim_player_id)
    print("Robber resolved:", result)


def print_help_for_phase(game: Game) -> None:
    common = "status | save <file> | autoplay <turns> | help"
    if game.turn_phase == game.PHASE_ROLL:
        print(f"Commands: roll | {common}")
    elif game.turn_phase == game.PHASE_TRADE:
        print(f"Commands: trade <give> <receive> [rate] | done | {common}")
    elif game.turn_phase == game.PHASE_BUILD:
        print(
            "Commands: road <edge_id> | settlement <vertex_id> | city <vertex_id> | "
            "dev buy | dev play <index> | end | " + common
        )
    elif game.turn_phase == game.PHASE_ROBBER:
        print(f"Commands: robber | {common}")


def list_dev_cards(game: Game, player_id: int) -> None:
    cards = game.players[player_id].development_cards
    if not cards:
        print("No development cards.")
        return
    for index, card in enumerate(cards):
        print(f"[{index}] {card.value}")


def play_dev_card_interactive(game: Game, player_id: int, index: int) -> None:
    cards = game.players[player_id].development_cards
    if index < 0 or index >= len(cards):
        raise ValueError("Invalid dev card index")

    card = cards[index]
    if card == DevelopmentCardType.KNIGHT:
        options = game.get_robber_move_options(player_id)
        target_hex_id = max(options, key=lambda hex_id: len(options[hex_id]))
        victims = options[target_hex_id]
        victim_player_id = victims[0] if victims else None
        result = game.play_development_card(
            player_id,
            card,
            target_hex_id=target_hex_id,
            victim_player_id=victim_player_id,
        )
        print("Played:", result)
        return

    if card == DevelopmentCardType.ROAD_BUILDING:
        legal_edges = [edge_id for edge_id in game.board.edges if game.board.can_place_road(edge_id, player_id)]
        if len(legal_edges) < 2:
            raise ValueError("Not enough legal road placements for Road Building")
        result = game.play_development_card(player_id, card, edge_ids=legal_edges[:2])
        print("Played:", result)
        return

    if card == DevelopmentCardType.YEAR_OF_PLENTY:
        r1_raw = safe_input("First resource: ")
        r2_raw = safe_input("Second resource: ")
        if r1_raw is None or r2_raw is None:
            raise ValueError("Input ended while selecting resources")
        r1 = parse_resource(r1_raw)
        r2 = parse_resource(r2_raw)
        result = game.play_development_card(player_id, card, resources=[r1, r2])
        print("Played:", result)
        return

    if card == DevelopmentCardType.MONOPOLY:
        resource_raw = safe_input("Resource to monopolize: ")
        if resource_raw is None:
            raise ValueError("Input ended while selecting monopoly resource")
        resource = parse_resource(resource_raw)
        result = game.play_development_card(player_id, card, resource=resource)
        print("Played:", result)
        return

    raise ValueError("Unsupported card type for active play")


def autoplay_turns(game: Game, turns: int) -> None:
    bot = GreedyBot(name="AutoPilot")
    for _ in range(max(0, turns)):
        if game.game_over:
            return
        player_id = game.current_player.player_id
        result = bot.take_turn(game, player_id)
        print(f"Auto turn for {game.players[player_id].name}: {', '.join(result['events'])}")


def run_game_loop(game: Game) -> None:
    ensure_setup(game)

    while True:
        if game.game_over:
            print(f"Game over. Winner: {game.winner.name if game.winner else 'Unknown'}")
            return

        player_id = game.current_player.player_id
        print("\n" + game_summary(game))
        print(f"Current player resources: {format_resources(game, player_id)}")
        print_help_for_phase(game)

        raw_input = safe_input("> ")
        if raw_input is None:
            print("Input stream closed. Returning to main menu.")
            return
        raw = raw_input.strip()
        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        try:
            if cmd == "help":
                print_help_for_phase(game)
                continue

            if cmd == "status":
                print(game_summary(game))
                list_dev_cards(game, player_id)
                continue

            if cmd == "save":
                if len(parts) < 2:
                    raise ValueError("Usage: save <file>")
                path = Path(parts[1])
                game.save_json(path)
                print(f"Saved to {path.resolve()}")
                continue

            if cmd == "autoplay":
                turns = int(parts[1]) if len(parts) > 1 else 1
                autoplay_turns(game, turns)
                continue

            if game.turn_phase == game.PHASE_ROLL:
                if cmd != "roll":
                    raise ValueError("Only 'roll' is valid in roll phase")
                d1, d2, total, payouts = game.roll_for_turn(player_id)
                print(f"Rolled {d1}+{d2}={total}")
                if any(payouts.values()):
                    for pid, payout in payouts.items():
                        if payout:
                            printable = {resource.value: amount for resource, amount in payout.items()}
                            print(f"  {game.players[pid].name}: {printable}")
                if game.turn_phase == game.PHASE_ROBBER:
                    print("Robber phase triggered (rolled 7). Use 'robber'.")
                continue

            if game.turn_phase == game.PHASE_ROBBER:
                if cmd != "robber":
                    raise ValueError("Use 'robber' to resolve this phase")
                handle_robber_phase(game, player_id)
                continue

            if game.turn_phase == game.PHASE_TRADE:
                if cmd == "done":
                    game.finish_trade_phase(player_id)
                    continue
                if cmd != "trade":
                    raise ValueError("Use 'trade <give> <receive> [rate]' or 'done'")
                if len(parts) < 3:
                    raise ValueError("Usage: trade <give> <receive> [rate]")
                give = parse_resource(parts[1])
                receive = parse_resource(parts[2])
                rate = int(parts[3]) if len(parts) > 3 else None
                game.trade_with_bank(player_id, give, receive, rate=rate)
                used_rate = game.get_best_trade_rate(player_id, give) if rate is None else rate
                print(f"Trade complete at {used_rate}:1")
                continue

            if game.turn_phase == game.PHASE_BUILD:
                if cmd == "end":
                    game.end_turn(player_id)
                    continue

                if cmd == "road":
                    edge_id = int(parts[1])
                    game.place_road(player_id, edge_id)
                    print(f"Built road on edge {edge_id}")
                    continue

                if cmd == "settlement":
                    vertex_id = int(parts[1])
                    game.place_settlement(player_id, vertex_id)
                    print(f"Built settlement on vertex {vertex_id}")
                    continue

                if cmd == "city":
                    vertex_id = int(parts[1])
                    game.upgrade_to_city(player_id, vertex_id)
                    print(f"Upgraded city on vertex {vertex_id}")
                    continue

                if cmd == "dev":
                    if len(parts) < 2:
                        raise ValueError("Usage: dev buy | dev play <index>")
                    sub = parts[1].lower()
                    if sub == "buy":
                        card = game.buy_development_card(player_id)
                        print(f"Bought development card: {card.value}")
                        continue
                    if sub == "play":
                        if len(parts) < 3:
                            list_dev_cards(game, player_id)
                            raise ValueError("Usage: dev play <index>")
                        index = int(parts[2])
                        play_dev_card_interactive(game, player_id, index)
                        continue
                    raise ValueError("Usage: dev buy | dev play <index>")

                raise ValueError("Invalid build-phase command")

        except Exception as exc:
            print(f"Error: {exc}")


def create_new_game() -> Game:
    raw_names_in = safe_input("Player names (comma separated): ")
    if raw_names_in is None:
        raise ValueError("Input stream closed")
    raw_names = raw_names_in.strip()
    names = [name.strip() for name in raw_names.split(",") if name.strip()]
    if len(names) < 2:
        raise ValueError("Need at least 2 players")

    seed_raw_in = safe_input("Seed (blank for random): ")
    if seed_raw_in is None:
        raise ValueError("Input stream closed")
    seed_raw = seed_raw_in.strip()
    seed = int(seed_raw) if seed_raw else None
    return Game(player_names=names, seed=seed)


def main() -> None:
    print("Creatures of Catan - CLI")
    while True:
        print("\nMenu: new | load <file> | quit")
        raw_in = safe_input("> ")
        if raw_in is None:
            return
        raw = raw_in.strip()
        if not raw:
            continue

        parts = raw.split()
        cmd = parts[0].lower()

        try:
            if cmd == "quit":
                return
            if cmd == "new":
                game = create_new_game()
                run_game_loop(game)
                continue
            if cmd == "load":
                if len(parts) < 2:
                    raise ValueError("Usage: load <file>")
                game = Game.load_json(parts[1])
                run_game_loop(game)
                continue
            print("Unknown command.")
        except Exception as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
