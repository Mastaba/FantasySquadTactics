from PIL import Image
import json
import os

def split_tileset(tileset_path, json_path, output_dir):
    # Load the JSON data
    with open(json_path, 'r') as json_file:
        data = json.load(json_file)

    # Open the tileset image
    tileset = Image.open(tileset_path)

    # Terrain names
    terrain_names = [
        'Plains', 'Forest', 'Mountain', 'Lake',
        'River', 'Farm', 'Village', 'City'
    ]

    # Tile dimensions
    tile_width = 80
    tile_height = 80

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Extract terrain tiles
    for i, terrain in enumerate(terrain_names):
        row = i // 4
        col = i % 4
        tile = tileset.crop((
            col * tile_width, row * tile_height,
            (col + 1) * tile_width, (row + 1) * tile_height
        ))
        tile.save(os.path.join(output_dir, f"{terrain}.png"))

    # Extract faction tiles
    faction_start_row = 2  # Factions start after the first two rows
    faction_tile_count = 6  # Number of tiles per faction

    for faction in data['factions']:
        faction_name = faction['name']
        faction_dir_name = '_'.join(faction_name.split())
        faction_dir = os.path.join(output_dir, faction_dir_name)
        os.makedirs(faction_dir, exist_ok=True)

        for i, unit_class in enumerate(['Scout', 'Ranger', 'Melee', 'Heavy', 'Artillery', 'Leader']):
            row = faction_start_row + i // 4
            col = i % 4
            tile = tileset.crop((
                col * tile_width, row * tile_height,
                (col + 1) * tile_width, (row + 1) * tile_height
            ))
            tile.save(os.path.join(faction_dir, f"{unit_class.lower()}.png"))

        faction_start_row += faction_tile_count // 4

# Example usage
split_tileset(
    tileset_path="graphics/tileset.png",
    json_path="factions.json",
    output_dir="graphics"
)
