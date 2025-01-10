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
        return f"{self.name} (HP: {self.hp}, Pos: {self.position}, Terrain: {self.terrain}, Faction: {self.faction})"

    def get_details(self):
        return {
            "ID": self.unit_id,
            "Class": self.unit_class,
            "Name": self.name,
            "HP": self.hp,
            "Move": self.move,
            "Range": self.range,
            "Attack": self.atk,
            "Special": self.special,
            "Position": self.position,
            "Terrain": self.terrain,
            "Faction": self.faction
        }

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


def generate_game_map_adjusted(height, width, terrain_weights, player_start="north-south"):
    terrain_types = list(terrain_weights.keys())
    terrain_probs = [terrain_weights[t] for t in terrain_types]
    terrain_probs = np.array(terrain_probs) / sum(terrain_probs)

    map_grid = np.random.choice(terrain_types, size=(height, width), p=terrain_probs)
    return {
        "map": map_grid,
        "player_start": player_start
    }


def place_armies_on_map(game_map, army1, army2, orient):
    height, width = game_map.shape
    active_game_pieces = []

    def place_army(army, start_positions, army_id):
        for idx, unit in enumerate(army):
            position = start_positions[idx]
            row, col = position
            terrain = game_map[row, col]  # Get the terrain type at this position
            game_map[row, col] = f"A{army_id}_{idx}"  # Mark the map with the unit's ID
            active_game_pieces.append(GamePiece(
                unit_id=f"A{army_id}_{idx}",
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
            ))

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
        raise ValueError("Invalid orient value. Use 'north-south' or 'east-west'.")

    place_army(army1, army1_positions, 1)
    place_army(army2, army2_positions, 2)

    return {
        "map": game_map,
        "active_game_pieces": active_game_pieces
    }


def display_game_with_pygame(game_map, active_game_pieces):
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

        def draw_map():
            for row in range(game_map.shape[0]):
                for col in range(game_map.shape[1]):
                    terrain = game_map[row, col]
                    tile = terrain_tiles.get(terrain, None)
                    if tile:
                        # Apply green background with 50% alpha
                        background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                        background.fill((0, 255, 0, 128))  # Green with 50% alpha
                        screen.blit(background, (col * cell_size, row * cell_size))
                        screen.blit(tile, (col * cell_size, row * cell_size))

            for piece in active_game_pieces:
                row, col = piece.position
                faction = piece.faction.replace(" ", "_")  # Replace spaces with underscores for folder paths
                tile_path = f"graphics/{faction}/{piece.unit_class.lower()}.png"

                try:
                    tile = pygame.image.load(tile_path).convert_alpha()
                    # Apply green background with 50% alpha
                    background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    background.fill((0, 255, 0, 128))  # Green with 50% alpha
                    screen.blit(background, (col * cell_size, row * cell_size))
                    screen.blit(tile, (col * cell_size, row * cell_size))
                except FileNotFoundError:
                    print(f"Missing graphic for {piece.unit_class} in faction {faction}: {tile_path}")

        def draw_ui():
            pygame.draw.rect(screen, (50, 50, 50), (0, game_map.shape[0] * cell_size, width, 100))
            turn_text = font.render(f"Player {current_turn}'s Turn", True, (255, 255, 255))
            screen.blit(turn_text, (20, game_map.shape[0] * cell_size + 20))
            next_button = pygame.Rect(width - 120, game_map.shape[0] * cell_size + 20, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0), next_button)
            button_text = font.render("Next Turn", True, (255, 255, 255))
            screen.blit(button_text, (width - 110, game_map.shape[0] * cell_size + 35))
            return next_button

        while running:
            screen.fill((0, 0, 0))
            draw_map()
            next_button = draw_ui()
            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if next_button.collidepoint(event.pos):
                        current_turn = 2 if current_turn == 1 else 1

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    # Set file path for faction data (update with your actual file path)
    faction_file = "factions.json"

    # Set terrain weights and map dimensions
    terrain_weights = {
        "Plains": 0.4,
        "Forest": 0.2,
        "Mountain": 0.1,
        "Lake": 0.1,
        "River": 0.1,
        "Farm": 0.05,
        "Village": 0.03,
        "City": 0.02
    }
    map_height = 10
    map_width = 10

    try:
        # Build armies
        armies = build_random_armies(faction_file, army_points=20)
        army1 = armies["faction1"]["army"]
        army2 = armies["faction2"]["army"]

        # Generate the game map
        game_map_data = generate_game_map_adjusted(
            height=map_height,
            width=map_width,
            terrain_weights=terrain_weights
        )
        game_map = game_map_data["map"]

        # Place armies on the map
        game_data = place_armies_on_map(
            game_map=game_map,
            army1=army1,
            army2=army2,
            orient=game_map_data["player_start"]
        )

        # Launch the game
        display_game_with_pygame(
            game_map=game_data["map"],
            active_game_pieces=game_data["active_game_pieces"]
        )
    except Exception as e:
        print(f"An error occurred during initialization: {e}")
