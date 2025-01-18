import pygame
from game_classes import GamePiece
from populate import generate_game_map, build_random_armies, place_units_on_map
selected_tile = None

MOVEMENT_COSTS = {"Plains": 1, "Forest": 2, "Mountain": 3, "Lake": float('inf'), "River": 3, "Farm": 1, "Village": 1, "City": 2}

def move_unit(unit_id, new_position, unit_positions, terrain_map, movement_costs):
    row, col = new_position
    if row < 0 or row >= terrain_map.shape[0] or col < 0 or col >= terrain_map.shape[1]:
        raise ValueError("Position out of bounds")

    terrain = terrain_map[row, col]
    cost = movement_costs.get(terrain, float('inf'))

    if terrain in {"Lake"}:
        raise ValueError("Terrain not passable")

    unit = unit_positions[unit_id]
    if cost > unit.moves_remaining:
        raise ValueError("Not enough movement points")

    unit.position = new_position
    unit.terrain = terrain
    unit_positions[unit_id] = unit

def calculate_legal_moves(unit, terrain_map, movement_costs, unit_positions):
    height, width = terrain_map.shape
    legal_moves = {}
    to_visit = [(unit.position, unit.moves_remaining)]  # (current position, remaining movement)
    occupied_positions = {u.position for u in unit_positions.values() if u != unit}

    while to_visit:
        current_pos, remaining_move = to_visit.pop()
        move_cost = unit.moves_remaining - remaining_move

        # Exclude the unit's current position
        if current_pos != unit.position and (current_pos not in legal_moves or move_cost < legal_moves[current_pos]):
            legal_moves[current_pos] = move_cost

        row, col = current_pos
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            new_row, new_col = row + dr, col + dc
            new_pos = (new_row, new_col)

            if (
                0 <= new_row < height
                and 0 <= new_col < width
                and new_pos not in occupied_positions
            ):
                terrain = terrain_map[new_row, new_col]
                cost = movement_costs.get(terrain, float('inf'))

                if cost <= remaining_move:
                    to_visit.append((new_pos, remaining_move - cost))

    return legal_moves


def calculate_legal_attacks(unit, terrain_map, unit_positions):

    height, width = terrain_map.shape
    legal_attacks = set()
    row, col = unit.position

    for dr in range(-unit.range, unit.range + 1):
        for dc in range(-unit.range, unit.range + 1):
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < height and 0 <= new_col < width and (dr != 0 or dc != 0):
                target_pos = (new_row, new_col)
                for target in unit_positions.values():
                    if target.position == target_pos and target.faction != unit.faction:
                        legal_attacks.add(target_pos)

    return legal_attacks

def render_combined_map(terrain_map, unit_positions):
    combined_map = terrain_map.copy()

    for unit in unit_positions.values():
        row, col = unit.position
        combined_map[row, col] = unit.unit_id

    for row in combined_map:
        print(" ".join(row))

def display_game_with_pygame(game_map, unit_positions, faction_file, map_height, map_width, terrain_weights,
                             army_points):
    pygame.init()
    cell_size = 80  # Adjusted for tile size
    width = game_map.shape[1] * cell_size
    height = game_map.shape[0] * cell_size + 200  # Extra space for UI

    try:
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Fantasy Squad Tactics")

        # Load graphical tiles
        terrain_tiles = {
            'Plains': pygame.image.load('graphics/Plains.png').convert_alpha(),
            'Forest': pygame.image.load('graphics/Forest.png').convert_alpha(),
            'Mountain': pygame.image.load('graphics/Mountain.png').convert_alpha(),
            'Lake': pygame.image.load('graphics/Lake.png').convert_alpha(),
            'River': pygame.image.load('graphics/River.png').convert_alpha(),
            'Farm': pygame.image.load('graphics/Farm.png').convert_alpha(),
            'Village': pygame.image.load('graphics/Village.png').convert_alpha(),
            'City': pygame.image.load('graphics/City.png').convert_alpha()
        }

        font = pygame.font.Font('IMFellEnglishSC-Regular.ttf', 24)
        current_turn = 1
        running = True

        selected_unit = None
        legal_moves = {}
        legal_attacks = set()
        mode = "move"  # New mode state

        def reset_game():
            nonlocal game_map, unit_positions
            armies = build_random_armies(faction_file, army_points=army_points)
            army1 = armies["faction1"]["army"]
            army2 = armies["faction2"]["army"]

            game_map_data = generate_game_map(
                height=map_height,
                width=map_width,
                terrain_weights=terrain_weights
            )
            game_map = game_map_data

            unit_positions = place_units_on_map(
                terrain_map=game_map,
                army1=army1,
                army2=army2,
                orient="north-south"
            )

        def end_turn():
            nonlocal current_turn, selected_unit, legal_moves, legal_attacks
            current_turn = 2 if current_turn == 1 else 1
            selected_unit = None
            legal_moves = {}
            legal_attacks = set()
            for unit in unit_positions.values():
                if (current_turn == 1 and "A1" in unit.unit_id) or (current_turn == 2 and "A2" in unit.unit_id):
                    unit.moves_remaining = unit.move

        def draw_map():
            for row in range(game_map.shape[0]):
                for col in range(game_map.shape[1]):
                    terrain = game_map[row, col]
                    tile = terrain_tiles.get(terrain, None)
                    if tile:
                        # Apply a background fill behind the map tiles
                        background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                        background.fill((0, 175, 0, 128))  # #739735 with 50% alpha
                        screen.blit(background, (col * cell_size, row * cell_size))
                        screen.blit(tile, (col * cell_size, row * cell_size))

                    if (row, col) in legal_moves:
                        pygame.draw.rect(
                            screen, (255, 255, 0),
                            (col * cell_size +2 , row * cell_size +2, cell_size -4, cell_size -4),
                            width=2  # Border width for yellow box
                        )
                        # Draw the movement cost in the top-left corner
                        move_cost_text = font.render(str(legal_moves[(row, col)]), True, (0, 0, 0))
                        screen.blit(move_cost_text, (col * cell_size + 5, row * cell_size + 5))

                    if (row, col) in legal_attacks:
                        pygame.draw.rect(
                            screen, (255, 0, 0),
                            (col * cell_size, row * cell_size, cell_size, cell_size),
                            width=3  # Border width for red box
                        )

            for piece in unit_positions.values():
                row, col = piece.position
                faction = piece.faction.replace(" ", "_")  # Replace spaces with underscores for folder paths
                tile_path = f"graphics/{faction}/{piece.unit_class.lower()}.png"

                try:
                    tile = pygame.image.load(tile_path).convert_alpha()
                    # Apply a background fill behind the unit tiles
                    background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    if piece == selected_unit:
                        pygame.draw.circle(
                            background,
                            (0, 255, 0),
                            (cell_size // 2, cell_size // 2),
                            cell_size // 2,
                            5
                        )
                    screen.blit(background, (col * cell_size, row * cell_size))
                    screen.blit(tile, (col * cell_size, row * cell_size))
                except FileNotFoundError:
                    print(f"Missing graphic for {piece.unit_class} in faction {faction}: {tile_path}")

        import os

        def draw_ui():
            # Background for UI
            pygame.draw.rect(screen, (50, 50, 50), (0, game_map.shape[0] * cell_size + 75, width, 100))

            # Player turn
            large_font = pygame.font.Font('IMFellEnglishSC-Regular.ttf', 35)
            turn_text = large_font.render(f"Player {current_turn}'s Turn", True, (200, 200, 200))
            screen.blit(turn_text, (width // 2 - turn_text.get_width() // 2, game_map.shape[0] * cell_size + 10))

            # Selected unit panel
            panel_x = 20
            panel_y = game_map.shape[0] * cell_size + 65
            panel_width = 300
            panel_height = 200
            pygame.draw.rect(screen, (80, 80, 80), (panel_x, panel_y, panel_width, panel_height))
            pygame.draw.rect(screen, (200, 200, 200), (panel_x, panel_y, panel_width, panel_height), 2)

            if selected_unit:
                unit_name_text = font.render(selected_unit.name, True, (255, 255, 255))
                unit_stats_text = font.render(f"HP: {selected_unit.hp}  Range: {selected_unit.range}", True,
                                              (255, 255, 255))

                # Display unit icon if available
                faction = selected_unit.faction.replace(" ", "_")
                unit_icon_path = f"graphics/{faction}/{selected_unit.unit_class.lower()}.png"

                try:
                    if os.path.exists(unit_icon_path):
                        unit_icon = pygame.image.load(unit_icon_path).convert_alpha()
                    else:
                        raise FileNotFoundError(f"Missing graphic: {unit_icon_path}")
                except FileNotFoundError:
                    print(
                        f"Missing graphic for {selected_unit.unit_class} in faction {selected_unit.faction}. Using placeholder.")
                    unit_icon = pygame.image.load("graphics/placeholder.png").convert_alpha()

                icon_size = (50, 50)
                unit_icon = pygame.transform.scale(unit_icon, icon_size)
                screen.blit(unit_icon, (panel_x + 10, panel_y + 15))

                # Display text next to icon
                screen.blit(unit_name_text, (panel_x + 70, panel_y + 10))
                screen.blit(unit_stats_text, (panel_x + 70, panel_y + 40))
            else:
                no_unit_text = font.render("No unit selected", True, (255, 255, 255))
                screen.blit(no_unit_text, (panel_x + 10, panel_y + 10))

            # Buttons
            button_width = 100
            button_height = 100
            button_y = game_map.shape[0] * cell_size + 75

            # Define buttons
            end_button = pygame.Rect(width - 240, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0), end_button)
            end_text = font.render("End Turn", True, (255, 255, 255))
            screen.blit(end_text, (width - 230, game_map.shape[0] * cell_size + 80))

            reset_button = pygame.Rect(width - 120, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (0, 0, 200), reset_button)
            reset_text = font.render("Reset", True, (255, 255, 255))
            screen.blit(reset_text, (width - 110, game_map.shape[0] * cell_size + 80))

            move_button = pygame.Rect(width - 460, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (31, 150, 80) if mode == "move" else (50, 50, 50), move_button)
            move_text = font.render("Move", True, (255, 255, 255))
            screen.blit(move_text, (width - 450, game_map.shape[0] * cell_size + 80))

            attack_button = pygame.Rect(width - 360, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0) if mode == "attack" else (50, 50, 50), attack_button)
            attack_text = font.render("Attack", True, (255, 255, 255))
            screen.blit(attack_text, (width - 350, game_map.shape[0] * cell_size + 80))

            return end_button, reset_button, move_button, attack_button

        def handle_click(pos):
            nonlocal selected_unit, legal_moves, legal_attacks, mode
            col, row = pos[0] // cell_size, pos[1] // cell_size
            clicked_pos = (row, col)

            if selected_unit and mode == "move" and clicked_pos in legal_moves:
                try:
                    move_unit(selected_unit.unit_id, clicked_pos, unit_positions, game_map, MOVEMENT_COSTS)
                    selected_unit.moves_remaining -= legal_moves[clicked_pos]  # Deduct movement cost
                    legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                except ValueError as e:
                    print(f"Move error: {e}")
                return

            if selected_unit and mode == "attack":
                if clicked_pos in legal_attacks:
                    print(f"Attacking position: {clicked_pos}")
                    # Implement attack logic here
                elif not legal_attacks:
                    display_no_targets_message()
                    mode = "move"
                    legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                return

            for unit_id, unit in unit_positions.items():
                if unit.position == clicked_pos and (
                        (current_turn == 1 and "A1" in unit.unit_id) or (current_turn == 2 and "A2" in unit.unit_id)):
                    selected_unit = unit
                    if mode == "move":
                        legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                        legal_attacks = set()
                    elif mode == "attack":
                        legal_attacks = calculate_legal_attacks(selected_unit, game_map, unit_positions)
                        legal_moves = {}
                        if not legal_attacks:
                            display_no_targets_message()
                            mode = "move"
                            legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                    return

            selected_unit = None # Deselect if clicking elsewhere
            legal_moves = {}
            legal_attacks = set()

        def display_no_targets_message():
            message_text = font.render("No targets in range", True, (255, 0, 0))
            text_rect = message_text.get_rect(center=(width // 2, height // 2 - 50))
            screen.blit(message_text, text_rect)
            pygame.display.update()
            pygame.time.delay(1000)

        def display_select_unit_message():
            message_text = font.render("Select unit first", True, (255, 0, 0))
            text_rect = message_text.get_rect(center=(width // 2, height // 2 - 50))
            screen.blit(message_text, text_rect)
            pygame.display.update()
            pygame.time.delay(1000)
            if selected_unit:
                legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)

        def display_hover_info(pos):
            col, row = pos[0] // cell_size, pos[1] // cell_size
            hover_pos = (row, col)

            for unit in unit_positions.values():
                if unit.position == hover_pos:
                    unit_info = font.render(
                        f"{unit.name} (HP: {unit.hp})",
                        True, (255, 255, 255)
                    )
                    screen.blit(unit_info, (pos[0] + 10, pos[1] + 10))
                    return

        while running:          # Main game loop
            screen.fill((0, 0, 0))
            draw_map()
            end_button, reset_button, move_button, attack_button = draw_ui()

            mouse_pos = pygame.mouse.get_pos()
            display_hover_info(mouse_pos)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if end_button.collidepoint(event.pos):
                        end_turn()
                    elif reset_button.collidepoint(event.pos):
                        reset_game()
                    elif move_button.collidepoint(event.pos):
                        mode = "move"
                        legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS,
                                                            unit_positions) if selected_unit else {}
                        legal_attacks = set()
                    elif attack_button.collidepoint(event.pos):
                        if selected_unit:
                            mode = "attack"
                            legal_attacks = calculate_legal_attacks(selected_unit, game_map,
                                                                    unit_positions) if selected_unit else set()
                            legal_moves = {}
                            if not legal_attacks:
                                display_no_targets_message()
                                mode = "move"
                                legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                        else:
                            display_select_unit_message()
                            mode = "move"
                            if selected_unit:
                                legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions)
                    else:
                        handle_click(event.pos)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pygame.quit()


if __name__ == "__main__":  # Example Usage
    faction_file = "factions.json"

    terrain_weights = {
        "Plains": 0.4,
        "Forest": 0.2,
        "Mountain": 0.1,
        "Lake": 0.01,
        "River": 0.01,
        "Farm": 0.05,
        "Village": 0.005,
        "City": 0.005,
    }

    map_height = 10
    map_width = 10

    armies = build_random_armies(faction_file, army_points=20)
    army1 = armies["faction1"]["army"]
    army2 = armies["faction2"]["army"]

    terrain_map = generate_game_map(map_height, map_width, terrain_weights)

    unit_positions = place_units_on_map(terrain_map, army1, army2)
    print("Initial Map:")
    render_combined_map(terrain_map, unit_positions)

    display_game_with_pygame(
        game_map=terrain_map,
        unit_positions=unit_positions,
        faction_file=faction_file,
        map_height=map_height,
        map_width=map_width,
        terrain_weights=terrain_weights,
        army_points=20
    )
