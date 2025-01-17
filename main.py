import json
import random
import numpy as np
import pygame
from game_classes import GamePiece
from populate import generate_game_map, build_random_armies, place_units_on_map

selected_tile = None

MOVEMENT_COSTS = {
    "Plains": 1,
    "Forest": 2,
    "Mountain": 3,
    "Lake": float('inf'),
    "River": 3,
    "Farm": 1,
    "Village": 1,
    "City": 2
}

def move_unit(unit_id, new_position, unit_positions, terrain_map, movement_costs):
    row, col = new_position
    if row < 0 or row >= terrain_map.shape[0] or col < 0 or col >= terrain_map.shape[1]:
        raise ValueError("Position out of bounds")

    terrain = terrain_map[row, col]
    cost = movement_costs.get(terrain, float('inf'))

    if terrain in {"Mountain", "Lake"}:
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

        # Update only if this path has a lower cost
        if current_pos not in legal_moves or move_cost < legal_moves[current_pos]:
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

    # Screen dimensions
    cell_size = 80  # Adjusted for tile size
    width = game_map.shape[1] * cell_size
    height = game_map.shape[0] * cell_size + 100  # Extra space for UI

    try:
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Turn-Based Strategy Game")

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

        font = pygame.font.SysFont(None, 24)
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
                        background.fill((0, 255, 0, 128))  # #739735 with 50% alpha
                        screen.blit(background, (col * cell_size, row * cell_size))
                        screen.blit(tile, (col * cell_size, row * cell_size))

                    if (row, col) in legal_moves:
                        pygame.draw.rect(
                            screen, (255, 255, 0),
                            (col * cell_size, row * cell_size, cell_size, cell_size),
                            width=3  # Border width for yellow box
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
                    screen.blit(background, (col * cell_size, row * cell_size))
                    screen.blit(tile, (col * cell_size, row * cell_size))
                except FileNotFoundError:
                    print(f"Missing graphic for {piece.unit_class} in faction {faction}: {tile_path}")

        def draw_ui():
            pygame.draw.rect(screen, (50, 50, 50), (0, game_map.shape[0] * cell_size, width, 100))
            turn_text = font.render(f"Player {current_turn}'s Turn", True, (255, 255, 255))
            screen.blit(turn_text, (20, game_map.shape[0] * cell_size + 20))

            if selected_unit:
                unit_info = font.render(
                    f"{selected_unit.name} (HP: {selected_unit.hp}, Moves: {selected_unit.moves_remaining}, Terrain: {selected_unit.terrain})",
                    True, (255, 255, 255)
                )
                screen.blit(unit_info, (20, game_map.shape[0] * cell_size + 50))

            end_button = pygame.Rect(width - 240, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0), end_button)
            end_text = font.render("End Turn", True, (255, 255, 255))
            screen.blit(end_text, (width - 230, game_map.shape[0] * cell_size + 35))

            reset_button = pygame.Rect(width - 120, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (0, 0, 200), reset_button)
            reset_text = font.render("Reset", True, (255, 255, 255))
            screen.blit(reset_text, (width - 110, game_map.shape[0] * cell_size + 35))

            move_button = pygame.Rect(width - 360, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (0, 200, 0) if mode == "move" else (100, 100, 100), move_button)
            move_text = font.render("Move", True, (255, 255, 255))
            screen.blit(move_text, (width - 350, game_map.shape[0] * cell_size + 35))

            attack_button = pygame.Rect(width - 480, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0) if mode == "attack" else (100, 100, 100), attack_button)
            attack_text = font.render("Attack", True, (255, 255, 255))
            screen.blit(attack_text, (width - 470, game_map.shape[0] * cell_size + 35))

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

            if selected_unit and mode == "attack" and clicked_pos in legal_attacks:
                print(f"Attacking position: {clicked_pos}")
                # Implement attack logic here
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
                    return

            # Deselect if clicking elsewhere
            selected_unit = None
            legal_moves = {}
            legal_attacks = set()

        # Main game loop
        while running:
            screen.fill((0, 0, 0))
            draw_map()
            end_button, reset_button, move_button, attack_button = draw_ui()
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
                        mode = "attack"
                        legal_attacks = calculate_legal_attacks(selected_unit, game_map,
                                                                unit_positions) if selected_unit else set()
                        legal_moves = {}
                    else:
                        handle_click(event.pos)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pygame.quit()


# Example Usage
if __name__ == "__main__":
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

    print("\nMoving Scout1 to (1, 1):")
    move_unit("A1_0", (1, 1), unit_positions, terrain_map, movement_costs=MOVEMENT_COSTS)
    render_combined_map(terrain_map, unit_positions)
    print(unit_positions)

    display_game_with_pygame(
        game_map=terrain_map,
        unit_positions=unit_positions,
        faction_file=faction_file,
        map_height=map_height,
        map_width=map_width,
        terrain_weights=terrain_weights,
        army_points=20
    )
