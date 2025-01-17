import json
import random
import numpy as np
from game_classes import GamePiece

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

