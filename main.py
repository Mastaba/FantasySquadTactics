import pygame
from game_classes import GamePiece
from populate import generate_game_map, build_random_armies, place_units_on_map
from special_abilities import SpecialAbilitySystem, get_unit_effective_range, apply_damage_reductions, \
    get_movement_modifications
from effects_system import EffectsSystem, apply_effects_to_damage, apply_effects_to_range, apply_effects_to_movement, \
    apply_effects_to_attack, can_unit_attack
import math

selected_tile = None

MOVEMENT_COSTS = {"Plains": 1, "Forest": 2, "Mountain": 3, "Lake": float('inf'), "River": 3, "Farm": 1, "Village": 1,
                  "City": 2}


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


def attack_unit(attacker_id, target_position, unit_positions, terrain_map, ability_system):
    """
    Performs an attack from attacker to target at target_position.
    Returns a dictionary with attack results for UI feedback.
    """
    attacker = unit_positions[attacker_id]

    # Check if unit has already attacked this turn
    if attacker.has_attacked:
        raise ValueError("Unit has already attacked this turn")

    # Find the target unit at the given position
    target = None
    target_id = None
    for uid, unit in unit_positions.items():
        if unit.position == target_position:
            target = unit
            target_id = uid
            break

    if not target:
        raise ValueError("No target found at specified position")

    if target.faction == attacker.faction:
        raise ValueError("Cannot attack friendly units")

    # Calculate base damage
    base_damage = attacker.atk

    # Apply terrain modifiers
    attacker_terrain = terrain_map[attacker.position[0], attacker.position[1]]
    target_terrain = terrain_map[target.position[0], target.position[1]]

    # Mountain bonus: +1 damage when attacking from mountain
    damage_bonus = 0
    if attacker_terrain == "Mountain" and target_terrain != "Mountain":
        damage_bonus += 1

    # Apply damage reductions using ability system
    preliminary_damage = base_damage + damage_bonus
    final_damage = apply_damage_reductions(target, preliminary_damage, terrain_map, ability_system)

    # Apply damage
    target.hp -= final_damage

    # Mark attacker as having attacked
    attacker.has_attacked = True

    # Calculate if this is a ranged attack (distance > 1)
    distance = max(abs(attacker.position[0] - target.position[0]),
                   abs(attacker.position[1] - target.position[1]))
    is_ranged = distance > 1

    # Prepare result info
    result = {
        "attacker": attacker.name,
        "target": target.name,
        "damage": final_damage,
        "target_remaining_hp": target.hp,
        "target_defeated": target.hp <= 0,
        "terrain_bonus": damage_bonus,
        "terrain_reduction": preliminary_damage - final_damage,
        "is_ranged": is_ranged,
        "attacker_pos": attacker.position,
        "target_pos": target.position
    }

    # Remove defeated unit
    if target.hp <= 0:
        del unit_positions[target_id]

    # Check for triggered abilities (like Double Tap)
    ability_name = attacker.special.split(" - ")[0] if " - " in attacker.special else attacker.special
    if ability_name == "Double tap" and target.hp <= 0:
        result["triggered_ability"] = "Double tap available"

    return result


def calculate_legal_moves(unit, terrain_map, movement_costs, unit_positions, ability_system):
    height, width = terrain_map.shape
    legal_moves = {}

    # Get movement modifications from abilities
    move_bonus, special_movement = get_movement_modifications(unit, terrain_map, unit_positions, ability_system)
    effective_moves = unit.moves_remaining + move_bonus

    to_visit = [(unit.position, effective_moves)]
    occupied_positions = {u.position for u in unit_positions.values() if u != unit}

    while to_visit:
        current_pos, remaining_move = to_visit.pop()
        move_cost = effective_moves - remaining_move

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

                # Check for special movement abilities
                if "flight" in special_movement:
                    if terrain == "Lake":
                        continue  # Can fly over but not end turn here
                    cost = 1  # All terrain costs 1 for flying units

                if cost <= remaining_move:
                    to_visit.append((new_pos, remaining_move - cost))

    return legal_moves


def calculate_effective_range(unit, terrain_map, unit_positions, ability_system):
    """Calculate the effective range of a unit including all bonuses."""
    return get_unit_effective_range(unit, terrain_map, unit_positions, ability_system)


def calculate_legal_attacks(unit, terrain_map, unit_positions, ability_system):
    # Can't attack if already attacked this turn
    if unit.has_attacked:
        return set()

    height, width = terrain_map.shape
    legal_attacks = set()
    row, col = unit.position

    effective_range = calculate_effective_range(unit, terrain_map, unit_positions, ability_system)

    for dr in range(-effective_range, effective_range + 1):
        for dc in range(-effective_range, effective_range + 1):
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < height and 0 <= new_col < width and (dr != 0 or dc != 0):
                distance = max(abs(dr), abs(dc))

                if distance <= effective_range:
                    target_pos = (new_row, new_col)
                    for target in unit_positions.values():
                        if target.position == target_pos and target.faction != unit.faction:
                            legal_attacks.add(target_pos)

    return legal_attacks


def calculate_legal_ability_targets(unit, ability_name, terrain_map, unit_positions, ability_system):
    """Calculate valid targets for a special ability"""
    ability = ability_system.get_ability_info(ability_name)
    if not ability:
        return set()

    legal_targets = set()
    ability_range = ability.get("range", 0)

    if ability_range == 0:
        return {unit.position}  # Self-targeted or area effect

    height, width = terrain_map.shape
    row, col = unit.position

    for dr in range(-ability_range, ability_range + 1):
        for dc in range(-ability_range, ability_range + 1):
            new_row, new_col = row + dr, col + dc
            if 0 <= new_row < height and 0 <= new_col < width:
                distance = max(abs(dr), abs(dc))
                if distance <= ability_range:
                    target_pos = (new_row, new_col)

                    # Different abilities target different things
                    if ability_name in ["Lure"]:  # Area effect abilities
                        legal_targets.add(target_pos)
                    elif ability_name in ["Grab"]:  # Enemy-targeting abilities
                        for target in unit_positions.values():
                            if target.position == target_pos and target.faction != unit.faction:
                                legal_targets.add(target_pos)
                    elif ability_name in ["For the King!", "Strategic Savant"]:  # Ally-targeting abilities
                        for target in unit_positions.values():
                            if target.position == target_pos and target.faction == unit.faction and target != unit:
                                legal_targets.add(target_pos)

    return legal_targets


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
    cell_size = 80
    width = game_map.shape[1] * cell_size
    height = game_map.shape[0] * cell_size + 300  # Increased height even more for ability description

    # Initialize ability system and effects system
    ability_system = SpecialAbilitySystem()
    effects_system = EffectsSystem()

    try:
        screen = pygame.display.set_mode((width, height))
        pygame.display.set_caption("Fantasy Squad Tactics @==|========>")  # CHANGED TITLE TO VERIFY UPDATE

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

        # Load UI graphics
        try:
            legal_moves_icon = pygame.image.load('graphics/legal-moves.png').convert_alpha()
        except FileNotFoundError:
            legal_moves_icon = None  # Fallback to yellow square if image not found

        try:
            selected_unit_icon = pygame.image.load('graphics/selected-unit.png').convert_alpha()
        except FileNotFoundError:
            selected_unit_icon = None  # Fallback to green circle if image not found

        try:
            blessed_icon = pygame.image.load('graphics/blessed.png').convert_alpha()
        except FileNotFoundError:
            blessed_icon = None  # Fallback to yellow dot if image not found

        font = pygame.font.Font('IMFellEnglishSC-Regular.ttf', 24)
        small_font = pygame.font.Font('IMFellEnglishSC-Regular.ttf', 18)
        current_turn = 1
        running = True

        selected_unit = None
        legal_moves = {}
        legal_attacks = set()
        legal_ability_targets = set()
        mode = "move"

        # Combat feedback variables
        last_attack_result = None
        last_ability_result = None
        attack_message_timer = 0

        # Animation variables
        projectile_animations = []

        def reset_game():
            nonlocal game_map, unit_positions, selected_unit, legal_moves, legal_attacks, legal_ability_targets, last_attack_result, last_ability_result, projectile_animations
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

            # Remove the test effect code
            effects_system.unit_effects = {}  # Clear all effects
            for unit_id, unit in unit_positions.items():
                effects_system.check_conditional_effects(unit_id, unit, {})
            effects_system.check_aura_effects(unit_positions, ability_system)

            selected_unit = None
            legal_moves = {}
            legal_attacks = set()
            legal_ability_targets = set()
            last_attack_result = None
            last_ability_result = None
            projectile_animations = []

        def end_turn():
            nonlocal current_turn, selected_unit, legal_moves, legal_attacks, legal_ability_targets, last_attack_result, last_ability_result, projectile_animations

            # Process end-of-turn effects for current player's units
            for unit_id, unit in unit_positions.items():
                if (current_turn == 1 and "A1" in unit_id) or (current_turn == 2 and "A2" in unit_id):
                    effects_system.process_turn_end(unit_id, current_turn)

            current_turn = 2 if current_turn == 1 else 1
            selected_unit = None
            legal_moves = {}
            legal_attacks = set()
            legal_ability_targets = set()
            last_attack_result = None
            last_ability_result = None
            projectile_animations = []

            # Reset movement and attack status for new current player's units
            for unit_id, unit in unit_positions.items():
                if (current_turn == 1 and "A1" in unit_id) or (current_turn == 2 and "A2" in unit_id):
                    unit.moves_remaining = unit.move
                    unit.has_attacked = False

                    # Process start-of-turn effects
                    effects_system.process_turn_start(unit_id, current_turn)

                # Apply healing for units on farms
                if unit.terrain == "Farm":
                    max_hp = get_max_hp_for_unit(unit)
                    if unit.hp < max_hp:
                        unit.hp = min(unit.hp + 1, max_hp)

            # Update all conditional and aura effects
            for unit_id, unit in unit_positions.items():
                effects_system.check_conditional_effects(unit_id, unit, {})
            effects_system.check_aura_effects(unit_positions, ability_system)

        def get_max_hp_for_unit(unit):
            """Get the original max HP for a unit by looking up its stats."""
            max_hp_by_class = {
                "Scout": 7, "Ranger": 10, "Melee": 15, "Heavy": 22, "Artillery": 12, "Leader": 24
            }
            return max_hp_by_class.get(unit.unit_class, unit.hp)

        def draw_map():
            for row in range(game_map.shape[0]):
                for col in range(game_map.shape[1]):
                    terrain = game_map[row, col]
                    tile = terrain_tiles.get(terrain, None)
                    if tile:
                        background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                        background.fill((0, 175, 0, 128))
                        screen.blit(background, (col * cell_size, row * cell_size))
                        screen.blit(tile, (col * cell_size, row * cell_size))

                    if (row, col) in legal_moves:
                        if legal_moves_icon:
                            # Use the legal-moves.png graphic
                            screen.blit(legal_moves_icon, (col * cell_size, row * cell_size))
                        else:
                            # Fallback to yellow square if image not found
                            pygame.draw.rect(
                                screen, (255, 255, 0),
                                (col * cell_size + 2, row * cell_size + 2, cell_size - 4, cell_size - 4),
                                width=2
                            )

                        # Still show move cost number
                        move_cost_text = small_font.render(str(legal_moves[(row, col)]), True, (0, 0, 0))
                        screen.blit(move_cost_text, (col * cell_size + 5, row * cell_size + 5))

                    if (row, col) in legal_attacks:
                        pygame.draw.rect(
                            screen, (255, 0, 0),
                            (col * cell_size, row * cell_size, cell_size, cell_size),
                            width=3
                        )

                    if (row, col) in legal_ability_targets:
                        pygame.draw.rect(
                            screen, (128, 0, 255),
                            (col * cell_size, row * cell_size, cell_size, cell_size),
                            width=3
                        )

            for piece in unit_positions.values():
                row, col = piece.position
                faction = piece.faction.replace(" ", "_")
                tile_path = f"graphics/{faction}/{piece.unit_class.lower()}.png"

                try:
                    tile = pygame.image.load(tile_path).convert_alpha()
                    background = pygame.Surface((cell_size, cell_size), pygame.SRCALPHA)
                    if piece == selected_unit:
                        if selected_unit_icon:
                            # Use the selected-unit.png graphic
                            screen.blit(selected_unit_icon, (col * cell_size, row * cell_size))
                        else:
                            # Fallback to green circle if image not found
                            pygame.draw.circle(
                                background,
                                (0, 255, 0),
                                (cell_size // 2, cell_size // 2),
                                cell_size // 2,
                                5
                            )
                            screen.blit(background, (col * cell_size, row * cell_size))
                    else:
                        screen.blit(background, (col * cell_size, row * cell_size))
                    screen.blit(tile, (col * cell_size, row * cell_size))

                    # Draw HP indicator
                    hp_text = small_font.render(str(piece.hp), True, (255, 255, 255))
                    hp_bg = pygame.Surface((hp_text.get_width() + 4, hp_text.get_height() + 2))
                    hp_bg.fill((0, 0, 0))
                    hp_bg.set_alpha(128)
                    screen.blit(hp_bg, (col * cell_size + cell_size - hp_text.get_width() - 6, row * cell_size + 2))
                    screen.blit(hp_text, (col * cell_size + cell_size - hp_text.get_width() - 4, row * cell_size + 3))

                    # Draw attack status indicator (bottom-left corner) - only for current player's units
                    if ((current_turn == 1 and "A1" in piece.unit_id) or (current_turn == 2 and "A2" in piece.unit_id)):
                        try:
                            if piece.has_attacked:
                                attack_icon = pygame.image.load("graphics/attack-done.png").convert_alpha()
                            else:
                                attack_icon = pygame.image.load("graphics/attack-available.png").convert_alpha()
                            screen.blit(attack_icon, (col * cell_size + 2, row * cell_size + cell_size - 17))
                        except FileNotFoundError:
                            # Fallback to colored squares if images not found
                            attack_indicator = pygame.Surface((15, 15))
                            if piece.has_attacked:
                                attack_indicator.fill((255, 0, 0))  # Red for used attack
                            else:
                                attack_indicator.fill((0, 255, 0))  # Green for available attack
                            attack_indicator.set_alpha(180)
                            screen.blit(attack_indicator, (col * cell_size + 2, row * cell_size + cell_size - 17))

                    # Draw move status indicator (bottom-right corner) - only for current player's units
                    if ((current_turn == 1 and "A1" in piece.unit_id) or (current_turn == 2 and "A2" in piece.unit_id)):
                        try:
                            if piece.moves_remaining <= 0:
                                move_icon = pygame.image.load("graphics/move-done.png").convert_alpha()
                            else:
                                move_icon = pygame.image.load("graphics/move-available.png").convert_alpha()
                            screen.blit(move_icon, (col * cell_size + cell_size - 17, row * cell_size + cell_size - 17))
                        except FileNotFoundError:
                            # Fallback to colored squares if images not found
                            move_indicator = pygame.Surface((15, 15))
                            if piece.moves_remaining <= 0:
                                move_indicator.fill((255, 0, 0))  # Red for no moves left
                            else:
                                move_indicator.fill((0, 255, 0))  # Green for moves available
                            move_indicator.set_alpha(180)
                            screen.blit(move_indicator,
                                        (col * cell_size + cell_size - 17, row * cell_size + cell_size - 17))

                    # Draw effects indicator - blessed.png overlay if unit has any effects
                    if effects_system.has_any_effects(piece.unit_id):
                        if blessed_icon:
                            screen.blit(blessed_icon, (col * cell_size, row * cell_size))
                        else:
                            # Fallback to yellow dot if image not found
                            pygame.draw.circle(screen, (255, 255, 0),
                                               (col * cell_size + cell_size - 8, row * cell_size + 8), 6)
                            pygame.draw.circle(screen, (0, 0, 0),
                                               (col * cell_size + cell_size - 8, row * cell_size + 8), 6, 1)

                except FileNotFoundError:
                    pass

            # Draw projectile animations
            for projectile in projectile_animations[:]:
                projectile['progress'] += projectile['speed']

                if projectile['progress'] >= 1.0:
                    projectile_animations.remove(projectile)
                else:
                    start_x = projectile['start'][1] * cell_size + cell_size // 2
                    start_y = projectile['start'][0] * cell_size + cell_size // 2
                    end_x = projectile['end'][1] * cell_size + cell_size // 2
                    end_y = projectile['end'][0] * cell_size + cell_size // 2

                    current_x = start_x + (end_x - start_x) * projectile['progress']
                    current_y = start_y + (end_y - start_y) * projectile['progress']

                    pygame.draw.circle(screen, projectile['color'], (int(current_x), int(current_y)), 6)
                    pygame.draw.circle(screen, (255, 255, 255), (int(current_x), int(current_y)), 6, 2)

        def draw_ui():
            pygame.draw.rect(screen, (50, 50, 50), (0, game_map.shape[0] * cell_size + 75, width, 125))

            large_font = pygame.font.Font('IMFellEnglishSC-Regular.ttf', 35)
            turn_text = large_font.render(f"Player {current_turn}'s Turn", True, (200, 200, 200))
            screen.blit(turn_text, (width // 2 - turn_text.get_width() // 2, game_map.shape[0] * cell_size + 10))

            panel_x = 20
            panel_y = game_map.shape[0] * cell_size + 65
            panel_width = 300
            panel_height = 130
            pygame.draw.rect(screen, (80, 80, 80), (panel_x, panel_y, panel_width, panel_height))
            pygame.draw.rect(screen, (200, 200, 200), (panel_x, panel_y, panel_width, panel_height), 2)

            if selected_unit:
                unit_name_text = font.render(selected_unit.name, True, (255, 255, 255))
                unit_stats_text = font.render(
                    f"HP: {selected_unit.hp}  Range: {calculate_effective_range(selected_unit, game_map, unit_positions, ability_system)}",
                    True,
                    (255, 255, 255))
                unit_move_text = font.render(f"Moves: {selected_unit.moves_remaining}/{selected_unit.move}", True,
                                             (255, 255, 255))
                unit_attack_text = font.render(f"Attacked: {'Yes' if selected_unit.has_attacked else 'No'}", True,
                                               (255, 0, 0) if selected_unit.has_attacked else (0, 255, 0))

                # Show available abilities with better messaging
                available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                    unit_positions)
                ability_name = selected_unit.special.split(" - ")[
                    0] if " - " in selected_unit.special else selected_unit.special

                if available_abilities:
                    ability_text = f"Ability: {ability_name}"
                else:
                    # Check if unit has an ability but can't use it right now
                    ability_info = ability_system.get_ability_info(ability_name)
                    if ability_info and ability_system.is_active_ability(ability_name):
                        ability_text = f"Ability: {ability_name} (not currently usable)"
                    else:
                        ability_text = f"Ability: {ability_name} (passive)"

                unit_ability_text = small_font.render(ability_text, True, (255, 255, 255))

                faction = selected_unit.faction.replace(" ", "_")
                unit_icon_path = f"graphics/{faction}/{selected_unit.unit_class.lower()}.png"

                try:
                    unit_icon = pygame.image.load(unit_icon_path).convert_alpha()
                except FileNotFoundError:
                    unit_icon = pygame.image.load("graphics/placeholder.png").convert_alpha()

                icon_size = (50, 50)
                unit_icon = pygame.transform.scale(unit_icon, icon_size)
                screen.blit(unit_icon, (panel_x + 10, panel_y + 15))

                screen.blit(unit_name_text, (panel_x + 70, panel_y + 10))
                screen.blit(unit_stats_text, (panel_x + 70, panel_y + 35))
                screen.blit(unit_move_text, (panel_x + 70, panel_y + 60))
                screen.blit(unit_attack_text, (panel_x + 70, panel_y + 85))
                screen.blit(unit_ability_text, (panel_x + 70, panel_y + 110))
            else:
                no_unit_text = font.render("No unit selected", True, (255, 255, 255))
                screen.blit(no_unit_text, (panel_x + 10, panel_y + 10))

            # Check if selected unit can move, attack, or use abilities
            can_move = selected_unit and selected_unit.moves_remaining > 0
            can_attack = selected_unit and can_unit_attack(selected_unit, effects_system)
            available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                unit_positions) if selected_unit else []
            can_use_ability = len(available_abilities) > 0

            # Buttons
            end_button = pygame.Rect(width - 240, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (200, 0, 0), end_button)
            end_text = font.render("End Turn", True, (255, 255, 255))
            screen.blit(end_text, (width - 230, game_map.shape[0] * cell_size + 80))

            reset_button = pygame.Rect(width - 120, game_map.shape[0] * cell_size + 65, 100, 50)
            pygame.draw.rect(screen, (0, 0, 200), reset_button)
            reset_text = font.render("Reset", True, (255, 255, 255))
            screen.blit(reset_text, (width - 110, game_map.shape[0] * cell_size + 80))

            # Move button with opacity based on availability
            move_button = pygame.Rect(width - 560, game_map.shape[0] * cell_size + 65, 100, 50)
            move_color = (31, 150, 80) if mode == "move" else (50, 50, 50)

            move_button_surface = pygame.Surface((100, 50))
            move_button_surface.fill(move_color)

            if not can_move and selected_unit:
                move_button_surface.set_alpha(64)

            screen.blit(move_button_surface, (width - 560, game_map.shape[0] * cell_size + 65))
            pygame.draw.rect(screen, (200, 200, 200), move_button, 2)

            move_text = font.render("Move", True, (255, 255, 255))
            move_text_surface = move_text.copy()

            if not can_move and selected_unit:
                move_text_surface.set_alpha(64)

            screen.blit(move_text_surface, (width - 550, game_map.shape[0] * cell_size + 80))

            # Attack button with opacity based on availability
            attack_button = pygame.Rect(width - 460, game_map.shape[0] * cell_size + 65, 100, 50)
            attack_color = (200, 0, 0) if mode == "attack" else (50, 50, 50)

            attack_button_surface = pygame.Surface((100, 50))
            attack_button_surface.fill(attack_color)

            if not can_attack and selected_unit:
                attack_button_surface.set_alpha(64)

            screen.blit(attack_button_surface, (width - 460, game_map.shape[0] * cell_size + 65))
            pygame.draw.rect(screen, (200, 200, 200), attack_button, 2)

            attack_text = font.render("Attack", True, (255, 255, 255))
            attack_text_surface = attack_text.copy()

            if not can_attack and selected_unit:
                attack_text_surface.set_alpha(64)

            screen.blit(attack_text_surface, (width - 450, game_map.shape[0] * cell_size + 80))

            # Ability button with opacity based on availability
            ability_button = pygame.Rect(width - 360, game_map.shape[0] * cell_size + 65, 100, 50)
            ability_color = (128, 0, 255) if mode == "ability" else (50, 50, 50)

            ability_button_surface = pygame.Surface((100, 50))
            ability_button_surface.fill(ability_color)

            if not can_use_ability and selected_unit:
                ability_button_surface.set_alpha(64)

            screen.blit(ability_button_surface, (width - 360, game_map.shape[0] * cell_size + 65))
            pygame.draw.rect(screen, (200, 200, 200), ability_button, 2)

            ability_text = font.render("Ability", True, (255, 255, 255))
            ability_text_surface = ability_text.copy()

            if not can_use_ability and selected_unit:
                ability_text_surface.set_alpha(64)

            screen.blit(ability_text_surface, (width - 350, game_map.shape[0] * cell_size + 80))

            # Display results if available
            message_y = game_map.shape[0] * cell_size + 45
            if last_attack_result and attack_message_timer > 0:
                result_text = f"{last_attack_result['attacker']} attacks {last_attack_result['target']} for {last_attack_result['damage']} damage!"
                if last_attack_result['target_defeated']:
                    result_text += f" {last_attack_result['target']} defeated!"

                result_surface = small_font.render(result_text, True, (255, 255, 0))
                result_rect = result_surface.get_rect(center=(width // 2, message_y))

                bg_rect = result_rect.inflate(10, 5)
                pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(screen, (255, 255, 0), bg_rect, 2)

                screen.blit(result_surface, result_rect)

            elif last_ability_result and attack_message_timer > 0:
                result_text = last_ability_result.get("message", "Ability used!")

                result_surface = small_font.render(result_text, True, (128, 0, 255))
                result_rect = result_surface.get_rect(center=(width // 2, message_y))

                bg_rect = result_rect.inflate(10, 5)
                pygame.draw.rect(screen, (0, 0, 0), bg_rect)
                pygame.draw.rect(screen, (128, 0, 255), bg_rect, 2)

                screen.blit(result_surface, result_rect)

            return end_button, reset_button, move_button, attack_button, ability_button, can_move, can_attack, can_use_ability

        def handle_click(pos):
            nonlocal selected_unit, legal_moves, legal_attacks, legal_ability_targets, mode, last_attack_result, last_ability_result, attack_message_timer, projectile_animations
            col, row = pos[0] // cell_size, pos[1] // cell_size
            clicked_pos = (row, col)

            # Handle ability usage first (but only if clicking on a valid ability target)
            if selected_unit and mode == "ability" and clicked_pos in legal_ability_targets:
                try:
                    available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                        unit_positions)
                    if available_abilities:
                        ability_name = available_abilities[0]["name"]
                        target_pos = clicked_pos if clicked_pos != selected_unit.position else None

                        last_ability_result = ability_system.execute_active_ability(
                            selected_unit, ability_name, target_pos, game_map, unit_positions
                        )
                        attack_message_timer = 180
                        print(f"Ability result: {last_ability_result}")

                        # Refresh legal targets after ability use
                        available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                            unit_positions)
                        if available_abilities:
                            legal_ability_targets = calculate_legal_ability_targets(
                                selected_unit, available_abilities[0]["name"], game_map, unit_positions, ability_system
                            )
                        else:
                            legal_ability_targets = set()

                except Exception as e:
                    print(f"Ability error: {e}")
                return

            # Check if clicking on a friendly unit (unit selection has priority over other actions)
            for unit_id, unit in unit_positions.items():
                if unit.position == clicked_pos and (
                        (current_turn == 1 and "A1" in unit.unit_id) or (current_turn == 2 and "A2" in unit.unit_id)):
                    selected_unit = unit
                    # Switch to move mode when selecting a new unit
                    mode = "move"
                    legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions,
                                                        ability_system)
                    legal_attacks = set()
                    legal_ability_targets = set()
                    return

            # Handle movement
            if selected_unit and mode == "move" and clicked_pos in legal_moves:
                try:
                    move_unit(selected_unit.unit_id, clicked_pos, unit_positions, game_map, MOVEMENT_COSTS)
                    selected_unit.moves_remaining -= legal_moves[clicked_pos]

                    # Update conditional effects after movement
                    effects_system.check_conditional_effects(selected_unit.unit_id, selected_unit, {})

                    legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions,
                                                        ability_system)
                except ValueError as e:
                    pass
                return

            # Handle attacks
            if selected_unit and mode == "attack":
                if clicked_pos in legal_attacks:
                    try:
                        last_attack_result = attack_unit(selected_unit.unit_id, clicked_pos, unit_positions, game_map,
                                                         ability_system)
                        attack_message_timer = 180

                        # Create projectile animation for ranged attacks
                        if last_attack_result['is_ranged']:
                            projectile_color = (255, 255, 0)  # Default yellow
                            if selected_unit.unit_class == "Ranger":
                                projectile_color = (139, 69, 19)  # Brown for arrows
                            elif selected_unit.unit_class == "Artillery":
                                projectile_color = (255, 100, 0)  # Orange for siege weapons

                            projectile_animations.append({
                                'start': last_attack_result['attacker_pos'],
                                'end': last_attack_result['target_pos'],
                                'progress': 0.0,
                                'speed': 0.15,
                                'color': projectile_color
                            })

                        legal_attacks = calculate_legal_attacks(selected_unit, game_map, unit_positions, ability_system)

                    except ValueError as e:
                        pass
                return

            # Handle ability usage
            if selected_unit and mode == "ability":
                if clicked_pos in legal_ability_targets:
                    try:
                        available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                            unit_positions)
                        if available_abilities:
                            ability_name = available_abilities[0]["name"]
                            target_pos = clicked_pos if clicked_pos != selected_unit.position else None

                            last_ability_result = ability_system.execute_active_ability(
                                selected_unit, ability_name, target_pos, game_map, unit_positions
                            )
                            attack_message_timer = 180

                            # Refresh legal targets after ability use
                            available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                                unit_positions)
                            if available_abilities:
                                legal_ability_targets = calculate_legal_ability_targets(
                                    selected_unit, available_abilities[0]["name"], game_map, unit_positions,
                                    ability_system
                                )
                            else:
                                legal_ability_targets = set()

                    except Exception as e:
                        pass
                return

            # Deselect if clicking elsewhere
            selected_unit = None
            legal_moves = {}
            legal_attacks = set()
            legal_ability_targets = set()

        def display_hover_info(pos):
            col, row = pos[0] // cell_size, pos[1] // cell_size
            hover_pos = (row, col)

            # Check for mode-specific hover tooltips first
            if selected_unit:
                if mode == "move" and hover_pos in legal_moves:
                    # Show move tooltip
                    move_cost = legal_moves[hover_pos]
                    tooltip_text = f"Click to move (Cost: {move_cost})"
                    tooltip_surface = small_font.render(tooltip_text, True, (255, 255, 255))

                    # Position tooltip
                    tooltip_x = min(pos[0] + 15, width - tooltip_surface.get_width() - 10)
                    tooltip_y = max(pos[1] - 30, 10)

                    # Draw tooltip background
                    tooltip_bg = pygame.Surface((tooltip_surface.get_width() + 10, tooltip_surface.get_height() + 6))
                    tooltip_bg.fill((40, 40, 40))
                    tooltip_bg.set_alpha(240)
                    screen.blit(tooltip_bg, (tooltip_x - 5, tooltip_y - 3))

                    # Draw tooltip border and text
                    pygame.draw.rect(screen, (255, 255, 0), (
                    tooltip_x - 5, tooltip_y - 3, tooltip_surface.get_width() + 10, tooltip_surface.get_height() + 6),
                                     1)
                    screen.blit(tooltip_surface, (tooltip_x, tooltip_y))
                    return

                elif mode == "attack" and hover_pos in legal_attacks:
                    # Show attack tooltip with target unit info
                    target_unit = None
                    for unit in unit_positions.values():
                        if unit.position == hover_pos:
                            target_unit = unit
                            break

                    tooltip_lines = ["Click to attack"]
                    if target_unit:
                        effective_range = calculate_effective_range(target_unit, game_map, unit_positions,
                                                                    ability_system)
                        tooltip_lines.append(f"{target_unit.name} (HP: {target_unit.hp}, Range: {effective_range})")

                        # Add effects if target has any
                        if effects_system.has_any_effects(target_unit.unit_id):
                            effect_summary = effects_system.get_effect_summary(target_unit.unit_id)
                            tooltip_lines.append("Effects:")
                            tooltip_lines.extend([f"  {effect}" for effect in effect_summary])

                    # Calculate tooltip size
                    line_height = 18
                    tooltip_width = max(small_font.size(line)[0] for line in tooltip_lines) + 20
                    tooltip_height = len(tooltip_lines) * line_height + 10

                    # Position tooltip
                    tooltip_x = min(pos[0] + 15, width - tooltip_width - 10)
                    tooltip_y = max(pos[1] - tooltip_height - 15, 10)

                    # Draw tooltip background
                    tooltip_bg = pygame.Surface((tooltip_width, tooltip_height))
                    tooltip_bg.fill((40, 40, 40))
                    tooltip_bg.set_alpha(240)
                    screen.blit(tooltip_bg, (tooltip_x, tooltip_y))

                    # Draw tooltip border
                    pygame.draw.rect(screen, (255, 0, 0), (tooltip_x, tooltip_y, tooltip_width, tooltip_height), 2)

                    # Draw tooltip text
                    for i, line in enumerate(tooltip_lines):
                        text_surface = small_font.render(line, True, (255, 255, 255))
                        screen.blit(text_surface, (tooltip_x + 10, tooltip_y + 5 + i * line_height))
                    return

                elif mode == "ability" and hover_pos in legal_ability_targets:
                    # Show ability tooltip
                    available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                        unit_positions)
                    if available_abilities:
                        ability_name = available_abilities[0]["name"]
                        tooltip_text = f"Click to use {ability_name}"
                    else:
                        tooltip_text = "Click to use ability"

                    tooltip_surface = small_font.render(tooltip_text, True, (255, 255, 255))

                    # Position tooltip
                    tooltip_x = min(pos[0] + 15, width - tooltip_surface.get_width() - 10)
                    tooltip_y = max(pos[1] - 30, 10)

                    # Draw tooltip background
                    tooltip_bg = pygame.Surface((tooltip_surface.get_width() + 10, tooltip_surface.get_height() + 6))
                    tooltip_bg.fill((40, 40, 40))
                    tooltip_bg.set_alpha(240)
                    screen.blit(tooltip_bg, (tooltip_x - 5, tooltip_y - 3))

                    # Draw tooltip border and text
                    pygame.draw.rect(screen, (128, 0, 255), (
                    tooltip_x - 5, tooltip_y - 3, tooltip_surface.get_width() + 10, tooltip_surface.get_height() + 6),
                                     1)
                    screen.blit(tooltip_surface, (tooltip_x, tooltip_y))
                    return

            # Check for unit hover (only if not hovering over action targets)
            for unit in unit_positions.values():
                if unit.position == hover_pos:
                    # Show unit info with effects merged in
                    effective_range = calculate_effective_range(unit, game_map, unit_positions, ability_system)
                    tooltip_lines = [f"{unit.name} (HP: {unit.hp}, Range: {effective_range})"]

                    # Add effects if unit has any
                    if effects_system.has_any_effects(unit.unit_id):
                        effect_summary = effects_system.get_effect_summary(unit.unit_id)
                        tooltip_lines.append("Effects:")
                        tooltip_lines.extend([f"  {effect}" for effect in effect_summary])

                    # Calculate tooltip size
                    line_height = 18
                    tooltip_width = max(small_font.size(line)[0] for line in tooltip_lines) + 20
                    tooltip_height = len(tooltip_lines) * line_height + 10

                    # Position tooltip
                    tooltip_x = min(pos[0] + 15, width - tooltip_width - 10)
                    tooltip_y = max(pos[1] - tooltip_height - 15, 10)

                    # Draw tooltip background
                    tooltip_bg = pygame.Surface((tooltip_width, tooltip_height))
                    tooltip_bg.fill((40, 40, 40))
                    tooltip_bg.set_alpha(240)
                    screen.blit(tooltip_bg, (tooltip_x, tooltip_y))

                    # Draw tooltip border (white for regular unit info)
                    pygame.draw.rect(screen, (200, 200, 200), (tooltip_x, tooltip_y, tooltip_width, tooltip_height), 2)

                    # Draw tooltip text
                    for i, line in enumerate(tooltip_lines):
                        text_surface = small_font.render(line, True, (255, 255, 255))
                        screen.blit(text_surface, (tooltip_x + 10, tooltip_y + 5 + i * line_height))
                    return

        # Main game loop
        while running:
            screen.fill((0, 0, 0))
            draw_map()
            end_button, reset_button, move_button, attack_button, ability_button, can_move, can_attack, can_use_ability = draw_ui()

            # ABILITY DESCRIPTION - DIRECTLY IN MAIN LOOP SINCE draw_ui() ISN'T WORKING
            if selected_unit:
                print(f"Drawing description for {selected_unit.name}")

                # Always show ability description, regardless of availability
                ability_name = selected_unit.special.split(" - ")[
                    0] if " - " in selected_unit.special else selected_unit.special

                # Get the full description from the ability system or use the original special text
                ability_info = ability_system.get_ability_info(ability_name)
                if ability_info:
                    ability_description = f"{ability_name}: {ability_info.get('description', selected_unit.special)}"
                else:
                    ability_description = selected_unit.special

                print(f"Description: {ability_description}")

                # Draw ability description background
                desc_lines = []
                words = ability_description.split()
                current_line = ""
                max_width = width - 40  # Leave some margin

                for word in words:
                    test_line = current_line + (" " if current_line else "") + word
                    test_surface = small_font.render(test_line, True, (255, 255, 255))
                    if test_surface.get_width() <= max_width:
                        current_line = test_line
                    else:
                        if current_line:
                            desc_lines.append(current_line)
                        current_line = word

                if current_line:
                    desc_lines.append(current_line)

                print(f"Description lines: {desc_lines}")

                # Calculate description height and position
                desc_height = max(60, len(desc_lines) * 22 + 15)
                ability_desc_y = game_map.shape[0] * cell_size + 200  # Position below UI

                # Draw background for description
                pygame.draw.rect(screen, (80, 80, 120), (20, ability_desc_y, width - 40, desc_height))
                pygame.draw.rect(screen, (255, 255, 255), (20, ability_desc_y, width - 40, desc_height), 2)

                # Draw description text
                for i, line in enumerate(desc_lines):
                    line_surface = small_font.render(line, True, (255, 255, 255))
                    text_y = ability_desc_y + 8 + i * 22
                    screen.blit(line_surface, (25, text_y))
                    print(f"Drawing line {i}: '{line}' at y={text_y}")

            mouse_pos = pygame.mouse.get_pos()
            display_hover_info(mouse_pos)

            # Update timers and animations
            if attack_message_timer > 0:
                attack_message_timer -= 1

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
                        # Only allow mode change if unit is selected and can move
                        if selected_unit and can_move:
                            mode = "move"
                            legal_moves = calculate_legal_moves(selected_unit, game_map, MOVEMENT_COSTS, unit_positions,
                                                                ability_system)
                            legal_attacks = set()
                            legal_ability_targets = set()
                    elif attack_button.collidepoint(event.pos):
                        # Only allow mode change if unit is selected and can attack
                        if selected_unit and can_attack:
                            mode = "attack"
                            legal_attacks = calculate_legal_attacks(selected_unit, game_map, unit_positions,
                                                                    ability_system)
                            legal_moves = {}
                            legal_ability_targets = set()
                    elif ability_button.collidepoint(event.pos):
                        # Only allow mode change if unit is selected and can use ability
                        if selected_unit and can_use_ability:
                            mode = "ability"
                            available_abilities = ability_system.get_available_active_abilities(selected_unit, game_map,
                                                                                                unit_positions)
                            if available_abilities:
                                ability_name = available_abilities[0]["name"]
                                legal_ability_targets = calculate_legal_ability_targets(
                                    selected_unit, ability_name, game_map, unit_positions, ability_system
                                )
                            legal_moves = {}
                            legal_attacks = set()
                    else:
                        handle_click(event.pos)

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pygame.quit()


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

    display_game_with_pygame(
        game_map=terrain_map,
        unit_positions=unit_positions,
        faction_file=faction_file,
        map_height=map_height,
        map_width=map_width,
        terrain_weights=terrain_weights,
        army_points=20
    )