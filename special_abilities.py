"""
Special Abilities System for Fantasy Squad Tactics

This module handles all unit special abilities, categorized by type:
- Passive abilities (automatic effects)
- Active abilities (player-triggered, in place of attack/move)
- Triggered abilities (activate under specific conditions)
- Combat modifiers (affect attack/defense calculations)
"""

import random
from typing import Dict, List, Tuple, Set, Optional, Any


class SpecialAbilitySystem:
    """Manages all special abilities in the game"""

    def __init__(self):
        self.passive_abilities = {}
        self.active_abilities = {}
        self.triggered_abilities = {}
        self.combat_modifiers = {}
        self.ability_registry = self._build_ability_registry()

    def _build_ability_registry(self) -> Dict[str, Dict[str, Any]]:
        """Build registry of all special abilities with their properties"""
        return {
            # Kingdom of Cantrell
            "Spotter": {
                "type": "passive",
                "description": "Friendly units within range 4 have +1 effective range",
                "range": 4,
                "effect": "range_boost"
            },
            "Double tap": {
                "type": "triggered",
                "description": "On successful hit, may make extra 1 damage attack vs another unit in range",
                "trigger": "successful_attack",
                "effect": "bonus_attack"
            },
            "Sword & Board": {
                "type": "conditional_passive",
                "description": "If unit doesn't move, negates first damage point next turn",
                "condition": "no_movement",
                "effect": "damage_reduction"
            },
            "Trusty Steed": {
                "type": "conditional_passive",
                "description": "If unit doesn't attack, +1 move this turn",
                "condition": "no_attack",
                "effect": "movement_boost"
            },
            "All She's Got": {
                "type": "active",
                "description": "+1 range this turn, but can't move/attack next turn",
                "cost": "skip_next_turn",
                "effect": "range_boost_with_penalty"
            },
            "For the King!": {
                "type": "active",
                "description": "Grant friendly unit extra move + melee attack bonus",
                "range": 4,
                "effect": "ally_boost"
            },
            "Strategic Savant": {
                "type": "active",
                "description": "Grant extra attack to friendly unit, bonus move if target defeated",
                "range": 4,
                "effect": "tactical_strike"
            },
            "Vigilance": {
                "type": "active",
                "description": "Grant First Strike to nearby allies",
                "range": 2,
                "effect": "first_strike_aura"
            },

            # Fae Armies
            "Lure": {
                "type": "active",
                "description": "Force enemies within 5 squares to move 2 squares toward satyr",
                "range": 5,
                "effect": "forced_movement"
            },
            "Mobile Strike": {
                "type": "active",
                "description": "Attack then move 2 extra tiles",
                "effect": "attack_and_move"
            },
            "Flying": {
                "type": "passive",
                "description": "Can fly over water, move through any terrain for 1 point",
                "effect": "flight"
            },
            "Trample": {
                "type": "active",
                "description": "Move through enemy dealing damage, end on open tile",
                "effect": "trample_attack"
            },
            "Grab": {
                "type": "active",
                "description": "Pull enemy from 2 tiles away, deal 2 damage",
                "range": 2,
                "effect": "pull_attack"
            },

            # Orc, Goblin, Ogre, and Troll Hordes
            "Warcry": {
                "type": "active",
                "description": "Grant all friendly units within 3 squares +1 ATK and +1 effective range for one turn",
                "range": 3,
                "effect": "area_buff"
            },
            "Smash": {
                "type": "active",
                "description": "Deal 2 damage to all adjacent enemy units",
                "range": 1,
                "effect": "area_attack"
            },

            # Add more abilities as needed...
            # This is a framework that can be expanded
        }

    def get_ability_info(self, ability_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific ability"""
        return self.ability_registry.get(ability_name)

    def is_passive_ability(self, ability_name: str) -> bool:
        """Check if ability is passive (always active)"""
        ability = self.get_ability_info(ability_name)
        return ability and ability.get("type") == "passive"

    def is_active_ability(self, ability_name: str) -> bool:
        """Check if ability can be actively triggered by player"""
        ability = self.get_ability_info(ability_name)
        return ability and ability.get("type") == "active"

    def can_use_ability(self, unit, ability_name: str, game_state: Dict) -> bool:
        """Check if unit can currently use their special ability"""
        ability = self.get_ability_info(ability_name)
        if not ability:
            return False

        ability_type = ability.get("type")

        # Active abilities require the unit hasn't attacked (unless specified otherwise)
        if ability_type == "active":
            return not unit.has_attacked

        # Conditional passives check their specific conditions
        if ability_type == "conditional_passive":
            condition = ability.get("condition")
            if condition == "no_movement":
                return unit.moves_remaining == unit.move  # Hasn't moved
            elif condition == "no_attack":
                return not unit.has_attacked

        return True

    def apply_passive_effects(self, unit, terrain_map, unit_positions) -> Dict[str, Any]:
        """Apply all passive effects for a unit and return modifications"""
        modifications = {
            "range_bonus": 0,
            "move_bonus": 0,
            "damage_reduction": 0,
            "special_movement": []
        }

        ability_name = unit.special.split(" - ")[0] if " - " in unit.special else unit.special
        ability = self.get_ability_info(ability_name)

        if not ability:
            return modifications

        # Handle specific passive abilities
        if ability_name == "Flying":
            modifications["special_movement"].append("flight")

        elif ability_name == "Trusty Steed" and not unit.has_attacked:
            modifications["move_bonus"] = 1

        elif ability_name == "Sword & Board" and unit.moves_remaining == unit.move:
            modifications["damage_reduction"] = 1

        return modifications

    def get_range_modifications(self, unit, terrain_map, unit_positions) -> int:
        """Calculate range modifications from abilities and other units"""
        range_bonus = 0

        # Check for Spotter ability from nearby units
        for other_unit in unit_positions.values():
            if (other_unit.faction == unit.faction and
                other_unit != unit and
                "Spotter" in other_unit.special):

                distance = max(abs(unit.position[0] - other_unit.position[0]),
                             abs(unit.position[1] - other_unit.position[1]))
                if distance <= 4:
                    range_bonus += 1

        return range_bonus

    def get_available_active_abilities(self, unit, terrain_map, unit_positions) -> List[Dict[str, Any]]:
        """Get list of active abilities this unit can currently use"""
        available = []

        ability_name = unit.special.split(" - ")[0] if " - " in unit.special else unit.special
        ability = self.get_ability_info(ability_name)

        if ability and self.is_active_ability(ability_name):
            if self.can_use_ability(unit, ability_name, {}):
                available.append({
                    "name": ability_name,
                    "description": ability["description"],
                    "range": ability.get("range", 0),
                    "effect": ability["effect"]
                })

        return available

    def execute_active_ability(self, unit, ability_name: str, target_pos: Optional[Tuple[int, int]],
                             terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute an active ability and return results"""
        ability = self.get_ability_info(ability_name)
        if not ability or not self.can_use_ability(unit, ability_name, {}):
            return {"success": False, "message": "Cannot use ability"}

        # Mark that ability was used (most abilities count as attacking)
        if ability_name not in ["Trusty Steed"]:  # Some abilities don't prevent attacking
            unit.has_attacked = True

        result = {"success": True, "effects": []}

        # Execute specific abilities
        if ability_name == "Lure":
            result.update(self._execute_lure(unit, terrain_map, unit_positions))

        elif ability_name == "Mobile Strike":
            result.update(self._execute_mobile_strike(unit, target_pos, terrain_map, unit_positions))

        elif ability_name == "Trample":
            result.update(self._execute_trample(unit, target_pos, terrain_map, unit_positions))

        elif ability_name == "Grab":
            result.update(self._execute_grab(unit, target_pos, terrain_map, unit_positions))

        elif ability_name == "Warcry":
            result.update(self._execute_warcry(unit, terrain_map, unit_positions))

        elif ability_name == "Smash":
            result.update(self._execute_smash(unit, terrain_map, unit_positions))

        # Add more ability executions as needed

        return result

    def _execute_lure(self, unit, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Satyr's Lure ability"""
        affected_units = []

        for target in unit_positions.values():
            if target.faction != unit.faction:
                distance = max(abs(unit.position[0] - target.position[0]),
                             abs(unit.position[1] - target.position[1]))
                if distance <= 5:
                    # Calculate direction to move toward satyr
                    dx = 1 if unit.position[1] > target.position[1] else -1 if unit.position[1] < target.position[1] else 0
                    dy = 1 if unit.position[0] > target.position[0] else -1 if unit.position[0] < target.position[0] else 0

                    # Move 2 squares toward satyr (simplified - would need pathfinding for full implementation)
                    new_pos = (target.position[0] + dy, target.position[1] + dx)

                    # Validate new position
                    if (0 <= new_pos[0] < terrain_map.shape[0] and
                        0 <= new_pos[1] < terrain_map.shape[1] and
                        not any(u.position == new_pos for u in unit_positions.values())):

                        target.position = new_pos
                        target.terrain = terrain_map[new_pos[0], new_pos[1]]
                        affected_units.append(target.name)

        return {
            "message": f"Lured {len(affected_units)} enemy units toward {unit.name}",
            "affected_units": affected_units
        }

    def _execute_mobile_strike(self, unit, target_pos, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Wild Elf's Mobile Strike"""
        # This would need integration with attack system
        return {
            "message": f"{unit.name} performs mobile strike",
            "extra_movement": 2
        }

    def _execute_trample(self, unit, target_pos, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Centaur's Trample ability"""
        # Implementation would need pathfinding and damage calculation
        return {
            "message": f"{unit.name} tramples through enemies",
            "damage_dealt": []
        }

    def _execute_grab(self, unit, target_pos, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Forest Lord's Grab ability"""
        # Find target at position
        target = None
        for u in unit_positions.values():
            if u.position == target_pos and u.faction != unit.faction:
                target = u
                break

        if not target:
            return {"success": False, "message": "No valid target"}

        # Pull target to adjacent square and deal damage
        target.hp -= 2
        # Position target adjacent to Forest Lord (simplified)
        adjacent_pos = (unit.position[0] + 1, unit.position[1])  # This needs proper calculation
        target.position = adjacent_pos
        target.terrain = terrain_map[adjacent_pos[0], adjacent_pos[1]]

        return {
            "message": f"{unit.name} grabs {target.name} for 2 damage",
            "damage_dealt": 2,
            "target_moved": True
        }

    def _execute_warcry(self, unit, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Gorak's Warcry ability"""
        affected_units = []

        for ally in unit_positions.values():
            if ally.faction == unit.faction and ally != unit:
                distance = max(abs(unit.position[0] - ally.position[0]),
                             abs(unit.position[1] - ally.position[1]))
                if distance <= 3:
                    # This would need integration with effects system to apply buffs
                    affected_units.append(ally.name)

        return {
            "message": f"{unit.name} rallies {len(affected_units)} allies with a mighty warcry!",
            "affected_units": affected_units,
            "buff_applied": "attack_and_range_bonus"
        }

    def _execute_smash(self, unit, terrain_map, unit_positions) -> Dict[str, Any]:
        """Execute Ogre Brute's Smash ability"""
        damaged_units = []

        # Get all adjacent positions
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:  # Skip the unit's own position
                    continue

                adjacent_pos = (unit.position[0] + dr, unit.position[1] + dc)

                # Find enemy units at adjacent positions
                for target in unit_positions.values():
                    if (target.position == adjacent_pos and
                        target.faction != unit.faction):

                        target.hp -= 2
                        damaged_units.append({
                            "name": target.name,
                            "damage": 2,
                            "remaining_hp": target.hp
                        })

                        # Remove defeated units
                        if target.hp <= 0:
                            # This would need integration with main game to properly remove units
                            pass

        return {
            "message": f"{unit.name} smashes nearby enemies for 2 damage each!",
            "damaged_units": damaged_units,
            "total_enemies_hit": len(damaged_units)
        }


# Helper functions for integration with main game
def get_unit_effective_range(unit, terrain_map, unit_positions, ability_system):
    """Calculate unit's effective range including all bonuses"""
    base_range = unit.range

    # Terrain bonus (Mountain)
    if terrain_map[unit.position[0], unit.position[1]] == "Mountain":
        base_range += 1

    # Ability bonuses
    range_bonus = ability_system.get_range_modifications(unit, terrain_map, unit_positions)

    return base_range + range_bonus


def apply_damage_reductions(unit, incoming_damage, terrain_map, ability_system):
    """Apply all damage reductions including abilities"""
    final_damage = incoming_damage

    # Terrain reduction (Forest)
    if terrain_map[unit.position[0], unit.position[1]] == "Forest":
        final_damage -= 1

    # Ability reductions
    modifications = ability_system.apply_passive_effects(unit, terrain_map, {})
    final_damage -= modifications["damage_reduction"]

    return max(1, final_damage)  # Minimum 1 damage


def get_movement_modifications(unit, terrain_map, unit_positions, ability_system):
    """Get movement modifications from abilities"""
    modifications = ability_system.apply_passive_effects(unit, terrain_map, unit_positions)
    return modifications["move_bonus"], modifications["special_movement"]