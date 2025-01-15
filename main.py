import json
import random
import numpy as np
import pygame


class GamePiece:
    def __init__(self, unit_id, unit_class, name, hp, move, range, atk, special, position, terrain, faction):
        self.unit_id = unit_id
        self.unit_class = unit_class
        self.name = name
        self.hp = hp
        self.move = move
        self.range = range
        self.atk = atk
        self.special = special
        self.position = position  # Tuple (row, col)
        self.terrain = terrain  # Type of terrain the unit is on
        self.faction = faction  # Faction name

    def __repr__(self):
        return f"{self.name} (HP: {self.hp}, Pos: {self.position}, Terrain: {self.terrain})"


def generate_game_map(height, width, terrain_weights):
    terrain_types = list(terrain_weights.keys())
    terrain_probs = [terrain_weights[t] for t in terrain_types]
    terrain_probs = np.array(terrain_probs) / sum(terrain_probs)

    return np.random.choice(terrain_types, size=(height, width), p=terrain_probs)


def build_army(faction, points):
    army = []
    remaining_points = points

    unit_costs = {
        "Scout": 2,
        "Ranger": 2,
        "Melee": 3,
        "Heavy": 5,
        "Artillery": 6,
        "Leader": 10
    }

    valid_units = [
        unit for unit in faction["units"]
        if unit["unit_class"] in unit_costs
    ]

    if not valid_units:
        raise ValueError(f"No valid units found for faction: {faction['name']}")

    while remaining_points > 0 and valid_units:
        unit = random.choice(valid_units)
        cost = unit_costs[unit["unit_class"]]

        if cost <= remaining_points:
            army.append({
                "name": unit["name"],
                "unit_class": unit["unit_class"],
                "cost": cost,
                "hp": unit["hp"],
                "move": unit["move"],
                "range": unit["range"],
                "atk": unit["atk"],
                "special": unit["special"],
                "faction": faction["name"]
            })
            remaining_points -= cost
        else:
            valid_units = [
                u for u in valid_units
                if unit_costs[u["unit_class"]] <= remaining_points
            ]

    return army


def build_random_armies(file_path, army_points=20):
    with open(file_path, 'r') as file:
        data = json.load(file)

    factions = data["factions"]

    # Select two random factions
    faction1, faction2 = random.sample(factions, 2)

    # Build armies for both factions
    army1 = build_army(faction1, army_points)
    army2 = build_army(faction2, army_points)

    return {
        "faction1": {
            "name": faction1["name"],
            "army": army1
        },
        "faction2": {
            "name": faction2["name"],
            "army": army2
        }
    }


def place_units_on_map(terrain_map, army1, army2, orient="north-south"):
    height, width = terrain_map.shape
    unit_positions = {}

    def assign_positions(army, start_positions, army_id):
        for idx, unit in enumerate(army):
            position = start_positions[idx]
            row, col = position
            terrain = terrain_map[row, col]
            unit_id = f"A{army_id}_{idx}"
            unit_positions[unit_id] = GamePiece(
                unit_id=unit_id,
                unit_class=unit["unit_class"],
                name=unit["name"],
                hp=unit["hp"],
                move=unit["move"],
                range=unit["range"],
                atk=unit["atk"],
                special=unit["special"],
                position=position,
                terrain=terrain,
                faction=unit["faction"]
            )

    if orient == "north-south":
        center_start = width // 2 - len(army1) // 2
        army1_positions = [(0, center_start + i) for i in range(len(army1))]
        center_start = width // 2 - len(army2) // 2
        army2_positions = [(height - 1, center_start + i) for i in range(len(army2))]
    elif orient == "east-west":
        center_start = height // 2 - len(army1) // 2
        army1_positions = [(center_start + i, 0) for i in range(len(army1))]
        center_start = height // 2 - len(army2) // 2
        army2_positions = [(center_start + i, width - 1) for i in range(len(army2))]
    else:
        raise ValueError("Invalid orientation. Use 'north-south' or 'east-west'.")

    assign_positions(army1, army1_positions, 1)
    assign_positions(army2, army2_positions, 2)

    return unit_positions


def move_unit(unit_id, new_position, unit_positions, terrain_map):
    row, col = new_position
    if row < 0 or row >= terrain_map.shape[0] or col < 0 or col >= terrain_map.shape[1]:
        raise ValueError("Position out of bounds")

    terrain = terrain_map[row, col]
    if terrain in {"Mountain", "Lake"}:
        raise ValueError("Terrain not passable")

    unit = unit_positions[unit_id]
    unit.position = new_position
    unit.terrain = terrain
    unit_positions[unit_id] = unit


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

            for piece in unit_positions.values():
                row, col = piece.position
                faction = piece.faction.replace(" ", "_")  # Replace spaces with underscores for folder paths
                tile_path = f"graphics/{faction}/{piece.unit_class.lower()}.png"

                try:
                    tile = pygame.image.load(tile_path).convert_alpha()
                    # Apply a background fill behind the unit tiles
                    background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    background.fill((0, 255, 0, 128))  # #739735 with 50% alpha
                    screen.blit(background, (col * cell_size, row * cell_size))
                    screen.blit(tile, (col * cell_size, row * cell_size))
                except FileNotFoundError:
                    print(f"Missing graphic for {piece.unit_class} in faction {faction}: {tile_path}")

        def draw_ui():
            pygame.draw.rect(screen, (50, 50, 50), (0, game_map.shape[0] * cell_size, width, 100))
            turn_text = font.render(f"Player {current_turn}'s Turn", True, (255, 255, 255))
            screen.blit(turn_text, (20, game_map.shape[0] * cell_size + 20))

            next_button = pygame.Rect(width - 240, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0), next_button)
            next_text = font.render("Next Turn", True, (255, 255, 255))
            screen.blit(next_text, (width - 230, game_map.shape[0] * cell_size + 35))

            reset_button = pygame.Rect(width - 120, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (0, 0, 200), reset_button)
            reset_text = font.render("Reset", True, (255, 255, 255))
            screen.blit(reset_text, (width - 110, game_map.shape[0] * cell_size + 35))

            return next_button, reset_button

        # Main game loop
        while running:
            screen.fill((0, 0, 0))
            draw_map()
            next_button, reset_button = draw_ui()
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
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
        "Lake": 0.1,
        "Farm": 0.05,
        "Village": 0.1,
        "City": 0.05
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
    move_unit("A1_0", (1, 1), unit_positions, terrain_map)
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
