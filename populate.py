import json
import random
import numpy as np
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

