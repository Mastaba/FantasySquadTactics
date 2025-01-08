import json
import random
import numpy as np


class GamePiece:
    def __init__(self, unit_id, unit_class, name, hp, move, range, atk, special, position, terrain):
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

    def __repr__(self):
        return f"{self.name} (HP: {self.hp}, Pos: {self.position}, Terrain: {self.terrain})"



def build_army(faction, points):
    """
    Builds a single army for a given faction.

    Parameters:
    - faction (dict): The faction data containing available units.
    - points (int): Total points allowed for the army.

    Returns:
    - list: List of units in the army.
    """
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
                "special": unit["special"]
            })
            remaining_points -= cost
        else:
            valid_units = [
                u for u in valid_units
                if unit_costs[u["unit_class"]] <= remaining_points
            ]

    return army


def build_random_armies(file_path, army_points=20):
    """
    Builds two random armies from random factions using a local JSON file.

    Parameters:
    - file_path (str): Path to the JSON file containing faction data.
    - army_points (int): Total points allowed for each army.

    Returns:
    - dict: Two armies with their respective units and total points used.
    """
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
            game_map[position] = f"A{army_id}_{idx}"  # Mark the map with the unit's ID
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
                terrain=terrain
            ))

    if orient == "north-south":
        army1_positions = [(0, col) for col in range(len(army1))]
        army2_positions = [(height - 1, col) for col in range(len(army2))]
    elif orient == "east-west":
        army1_positions = [(row, 0) for row in range(len(army1))]
        army2_positions = [(row, width - 1) for row in range(len(army2))]
    else:
        raise ValueError("Invalid orient value. Use 'north-south' or 'east-west'.")

    place_army(army1, army1_positions, 1)
    place_army(army2, army2_positions, 2)

    return {
        "map": game_map,
        "active_game_pieces": active_game_pieces
    }


def print_game_map_with_emojis(game_map, active_game_pieces):
    """
    Prints the game map to the console using emojis for terrain and game pieces.

    Parameters:
    - game_map (np.ndarray): The game map grid.
    - active_game_pieces (list of GamePiece): List of active game pieces with positions.
    """
    # Define emoji mapping
    terrain_to_emoji = {
        'Plains': '🌾',
        'Forest': '🌲',
        'Mountain': '⛰️',
        'Lake': '🌊',
        'River': '💧',
        'Farm': '🚜',
        'Village': '🏘️',
        'City': '🏙️',
    }

    # Map for game pieces
    piece_to_emoji = {
        "Scout": '🕵️',
        "Ranger": '🏹',
        "Melee": '⚔️',
        "Heavy": '🛡️',
        "Artillery": '🧨',
        "Leader": '👑'
    }

    # Create a copy of the map for visualization
    emoji_map = np.full(game_map.shape, '', dtype=object)

    # Fill the map with terrain emojis
    for row in range(game_map.shape[0]):
        for col in range(game_map.shape[1]):
            terrain = game_map[row, col]
            emoji_map[row, col] = terrain_to_emoji.get(terrain, '❓')

    # Place game pieces on the map
    for piece in active_game_pieces:
        row, col = piece.position
        emoji_map[row, col] = piece_to_emoji.get(piece.unit_class, '❓')

    # Print the map row by row
    for row in emoji_map:
        print(' '.join(row))

if __name__ == "__main__":
    terrain_weights_example = {
        'Plains': 40,
        'Forest': 30,
        'Mountain': 10,
        'Lake': 5,
        'River': 5,
        'Farm': 5,
        'Village': 3,
        'City': 2
    }

    file_path = "factions.json"
    armies = build_random_armies(file_path, army_points=20)

    game_map_data = generate_game_map_adjusted(
        height=10,
        width=10,
        terrain_weights=terrain_weights_example,
        player_start="north-south"
    )

    populated_map_data = place_armies_on_map(
        game_map_data["map"],
        armies["faction1"]["army"],
        armies["faction2"]["army"],
        game_map_data["player_start"]
    )

    # Print the map with emojis
    print_game_map_with_emojis(
        populated_map_data["map"],
        populated_map_data["active_game_pieces"]
    )

    # Print the list of active game pieces with their terrain
    print("\nActive Game Pieces with Terrain:")
    print(populated_map_data)
    for piece in populated_map_data["active_game_pieces"]:
        print(piece)
