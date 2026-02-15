from pathlib import Path

from catan_core import DevelopmentCardType, Game, ResourceType, run_bot_game, standard_initial_setup_auto


def pick_valid_initial_settlement_vertex(game: Game, player_id: int) -> int:
	for vertex_id in game.board.vertices:
		if game.board.get_ports_for_vertex(vertex_id) and game.board.can_place_settlement(vertex_id, player_id, require_connected_road=False):
			return vertex_id
	for vertex_id in game.board.vertices:
		if game.board.can_place_settlement(vertex_id, player_id, require_connected_road=False):
			return vertex_id
	raise RuntimeError("No valid settlement vertex available")


def pick_road_from_vertex(game: Game, player_id: int, vertex_id: int) -> int:
	for edge_id in game.board.vertices[vertex_id].adjacent_edges:
		if game.board.can_place_road(edge_id, player_id):
			return edge_id
	raise RuntimeError("No valid road edge available")


def pick_road_from_player_network(game: Game, player_id: int) -> int:
	for edge_id in game.board.edges:
		if game.board.can_place_road(edge_id, player_id):
			return edge_id
	raise RuntimeError("No valid road edge available for player network")


def pick_settlement_connected_to_player(game: Game, player_id: int) -> int:
	for vertex_id in game.board.vertices:
		if game.board.can_place_settlement(vertex_id, player_id, require_connected_road=True):
			return vertex_id
	raise RuntimeError("No valid connected settlement vertex available")


def print_player_state(game: Game) -> None:
	for player in game.players.values():
		resources = {resource.value: count for resource, count in player.resources.items() if count > 0}
		dev_cards = [card.value for card in player.development_cards]
		print(
			f"{player.name}: VP={player.victory_points}, "
			f"Settlements={len(player.settlements)}, Cities={len(player.cities)}, "
			f"Roads={len(player.roads)}, Resources={resources}, DevCards={dev_cards}"
		)
	print(
		f"LongestRoadHolder={game.longest_road_holder}, "
		f"LargestArmyHolder={game.largest_army_holder}, RobberHex={game.robber_hex_id}, "
		f"GameOver={game.game_over}, Winner={game.winner.name if game.winner else None}"
	)


def main() -> None:
	game = Game(player_names=["Alice", "Bob", "Cara"], seed=42)
	coastal_edges = sorted(edge.edge_id for edge in game.board.edges.values() if len(edge.touching_hexes) == 1)
	custom_ports = [
		{"edge_id": coastal_edges[0], "rate": 2, "resource": ResourceType.TIMBER.value},
		{"edge_id": coastal_edges[len(coastal_edges) // 2], "rate": 3, "resource": None},
	]
	game.board.configure_ports(custom_ports)
	print(f"Custom ports configured: {custom_ports}")

	setup_events = standard_initial_setup_auto(game)

	print("Initial placements complete.")
	print(f"Initial setup events: {setup_events}")
	print_player_state(game)

	active_player_id = game.current_player.player_id
	d1, d2, total, payouts = game.roll_for_turn(active_player_id)
	print(f"\nRolled {d1} + {d2} = {total}")
	print("Payouts:")
	for player_id, payout in payouts.items():
		if payout:
			readable = {resource.value: amount for resource, amount in payout.items()}
			print(f"  {game.players[player_id].name}: {readable}")

	first_player = game.players[active_player_id]
	port_rates = game.get_player_port_rates(active_player_id)
	readable_rates = {
		(resource.value if isinstance(resource, ResourceType) else "Generic"): rate
		for resource, rate in port_rates.items()
	}
	print(f"{first_player.name} port rates: {readable_rates}")
	first_player.add_resource(ResourceType.TIMBER, 4)
	game.trade_with_bank(active_player_id, give=ResourceType.TIMBER, receive=ResourceType.GRAIN)
	best_rate = game.get_best_trade_rate(active_player_id, ResourceType.TIMBER)
	print(f"\n{first_player.name} traded Timber for 1 Grain with bank at rate {best_rate}:1.")

	game.finish_trade_phase(active_player_id)

	first_player.add_resource(ResourceType.TIMBER, 2)
	first_player.add_resource(ResourceType.STONE, 2)
	first_player.add_resource(ResourceType.MEAT, 2)
	first_player.add_resource(ResourceType.GRAIN, 2)
	first_player.add_resource(ResourceType.IRON, 1)

	road_edge = pick_road_from_player_network(game, active_player_id)
	game.place_road(active_player_id, road_edge)
	print(f"{first_player.name} built a road on edge {road_edge} (cost enforced).")

	try:
		settlement_vertex = pick_settlement_connected_to_player(game, active_player_id)
		game.place_settlement(active_player_id, settlement_vertex)
		print(f"{first_player.name} built a settlement on vertex {settlement_vertex} (cost enforced).")
	except RuntimeError:
		base_vertex = next(iter(first_player.settlements))
		first_player.add_resource(ResourceType.GRAIN, 2)
		first_player.add_resource(ResourceType.IRON, 3)
		game.upgrade_to_city(active_player_id, base_vertex)
		print(f"{first_player.name} upgraded settlement {base_vertex} to a city (cost enforced).")

	card = game.buy_development_card(active_player_id)
	print(f"{first_player.name} bought a development card: {card.value}")

	if card != DevelopmentCardType.VICTORY_POINT:
		try:
			game.play_development_card(active_player_id, card)
		except ValueError as exc:
			print(f"Expected rule check when trying to play newly bought dev card: {exc}")

	game.end_turn(active_player_id)
	print(f"Turn ended. Next player is {game.current_player.name}, phase={game.turn_phase}.")

	bob_id = game.current_player.player_id
	bob = game.current_player
	bob.add_resource(ResourceType.TIMBER, 8)
	bob.add_resource(ResourceType.STONE, 2)

	game.turn_phase = game.PHASE_ROBBER
	game.pending_discards = {bob_id: game.players[bob_id].resources.total() // 2}
	discarded = game.auto_discard_for_seven(bob_id)
	print(f"\nSimulated roll of 7: {bob.name} discarded {len(discarded)} cards.")

	target_hex_id = next(
		hex_id
		for hex_id, hex_tile in game.board.hexes.items()
		if any(game.board.vertices[v_id].building_owner == 0 for v_id in hex_tile.vertex_ids)
		and hex_id != game.robber_hex_id
	)
	robber_options = game.get_robber_move_options(bob_id)
	print(f"Robber move options sample (first 3 hexes): {dict(list(robber_options.items())[:3])}")
	robber_result = game.resolve_robber_after_seven(bob_id, target_hex_id, victim_player_id=0)
	print(f"Robber moved and stole: {robber_result}")

	game.turn_phase = game.PHASE_BUILD
	bob.development_cards.append(DevelopmentCardType.KNIGHT)
	knight_target_hex = next(hex_id for hex_id in game.board.hexes if hex_id != game.robber_hex_id)
	knight_result = game.play_development_card(bob_id, DevelopmentCardType.KNIGHT, target_hex_id=knight_target_hex)
	print(f"Knight played: {knight_result}")

	print("\nFinal player state:")
	print_player_state(game)

	save_path = Path("game_state.json")
	game.save_json(save_path)
	restored = Game.load_json(save_path)
	print(f"\nSaved game to {save_path.resolve()}")
	print(
		"Loaded snapshot -> "
		f"Turn={restored.turn_number}, Phase={restored.turn_phase}, "
		f"CurrentPlayer={restored.current_player.name}, Winner={restored.winner.name if restored.winner else None}"
	)

	bot_game, history = run_bot_game(player_names=["BotA", "BotB", "BotC"], max_turns=40, seed=7)
	print(
		"\nBot simulation complete -> "
		f"Turns={len(history)}, GameOver={bot_game.game_over}, "
		f"Winner={bot_game.winner.name if bot_game.winner else None}"
	)
	for player in bot_game.players.values():
		print(f"  {player.name}: VP={player.victory_points}, Roads={len(player.roads)}, Cities={len(player.cities)}")

	# Optional basic visual board view (requires pygame):
	# from catan_core.render_pygame import run_basic_board_view
	# run_basic_board_view(restored)


if __name__ == "__main__":
	main()

