"""
Effects System for Fantasy Squad Tactics

This module handles all temporary and conditional effects on units:
- Passive ability effects (like Sword & Board damage reduction)
- Buffs from other units (like Spotter range bonus)
- Temporary status effects (like poison, stun, etc.)
- Visual indicators for affected units
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass
from enum import Enum


class EffectType(Enum):
    """Types of effects that can be applied to units"""
    DAMAGE_REDUCTION = "damage_reduction"
    RANGE_BONUS = "range_bonus"
    MOVEMENT_BONUS = "movement_bonus"
    ATTACK_BONUS = "attack_bonus"
    DAMAGE_OVER_TIME = "damage_over_time"
    MOVEMENT_RESTRICTION = "movement_restriction"
    ATTACK_RESTRICTION = "attack_restriction"
    FIRST_STRIKE = "first_strike"
    REGENERATION = "regeneration"
    SHIELD = "shield"


class EffectDuration(Enum):
    """How long effects last"""
    PERMANENT = "permanent"          # Until manually removed
    UNTIL_NEXT_TURN = "until_next_turn"  # Removed at start of unit's next turn
    UNTIL_END_OF_TURN = "until_end_of_turn"  # Removed at end of current turn
    CONDITIONAL = "conditional"      # Removed when condition is no longer met
    TIMED = "timed"                 # Lasts for X turns


@dataclass
class Effect:
    """Represents a single effect on a unit"""
    effect_type: EffectType
    name: str
    description: str
    value: Any  # The effect's magnitude (damage reduction amount, range bonus, etc.)
    duration: EffectDuration
    turns_remaining: int = 0  # For timed effects
    source_unit_id: Optional[str] = None  # Which unit caused this effect
    condition: Optional[str] = None  # For conditional effects

    def __post_init__(self):
        if self.duration == EffectDuration.TIMED and self.turns_remaining <= 0:
            raise ValueError("Timed effects must have turns_remaining > 0")


class EffectsSystem:
    """Manages all effects on all units"""

    def __init__(self):
        self.unit_effects: Dict[str, List[Effect]] = {}  # unit_id -> list of effects

    def add_effect(self, unit_id: str, effect: Effect) -> None:
        """Add an effect to a unit"""
        if unit_id not in self.unit_effects:
            self.unit_effects[unit_id] = []

        # Check if this effect already exists (avoid duplicates)
        existing = self.get_effect(unit_id, effect.name)
        if existing:
            # Update existing effect (refresh duration or stack value)
            if effect.duration == EffectDuration.TIMED:
                existing.turns_remaining = max(existing.turns_remaining, effect.turns_remaining)
            else:
                existing.value = effect.value  # Refresh the effect
        else:
            self.unit_effects[unit_id].append(effect)

    def remove_effect(self, unit_id: str, effect_name: str) -> bool:
        """Remove a specific effect from a unit. Returns True if removed."""
        if unit_id in self.unit_effects:
            for i, effect in enumerate(self.unit_effects[unit_id]):
                if effect.name == effect_name:
                    del self.unit_effects[unit_id][i]
                    return True
        return False

    def get_effect(self, unit_id: str, effect_name: str) -> Optional[Effect]:
        """Get a specific effect on a unit"""
        if unit_id in self.unit_effects:
            for effect in self.unit_effects[unit_id]:
                if effect.name == effect_name:
                    return effect
        return None

    def get_all_effects(self, unit_id: str) -> List[Effect]:
        """Get all effects on a unit"""
        return self.unit_effects.get(unit_id, [])

    def has_any_effects(self, unit_id: str) -> bool:
        """Check if a unit has any effects (for visual indicator)"""
        return len(self.get_all_effects(unit_id)) > 0

    def clear_unit_effects(self, unit_id: str) -> None:
        """Remove all effects from a unit"""
        if unit_id in self.unit_effects:
            self.unit_effects[unit_id] = []

    def process_turn_start(self, unit_id: str, current_turn: int) -> List[str]:
        """Process effects at the start of a unit's turn. Returns list of messages."""
        messages = []
        if unit_id not in self.unit_effects:
            return messages

        effects_to_remove = []

        for effect in self.unit_effects[unit_id]:
            # Handle regeneration effects
            if effect.effect_type == EffectType.REGENERATION:
                # This would need integration with the main game to actually heal
                messages.append(f"Unit regenerates {effect.value} HP")

            # Handle damage over time
            elif effect.effect_type == EffectType.DAMAGE_OVER_TIME:
                messages.append(f"Unit takes {effect.value} damage from {effect.name}")

            # Countdown timed effects
            if effect.duration == EffectDuration.TIMED:
                effect.turns_remaining -= 1
                if effect.turns_remaining <= 0:
                    effects_to_remove.append(effect.name)

            # Remove until_next_turn effects
            elif effect.duration == EffectDuration.UNTIL_NEXT_TURN:
                effects_to_remove.append(effect.name)

        # Remove expired effects
        for effect_name in effects_to_remove:
            self.remove_effect(unit_id, effect_name)
            messages.append(f"{effect_name} effect expired")

        return messages

    def process_turn_end(self, unit_id: str, current_turn: int) -> List[str]:
        """Process effects at the end of a unit's turn. Returns list of messages."""
        messages = []
        if unit_id not in self.unit_effects:
            return messages

        effects_to_remove = []

        for effect in self.unit_effects[unit_id]:
            if effect.duration == EffectDuration.UNTIL_END_OF_TURN:
                effects_to_remove.append(effect.name)

        # Remove expired effects
        for effect_name in effects_to_remove:
            self.remove_effect(unit_id, effect_name)
            messages.append(f"{effect_name} effect expired")

        return messages

    def check_conditional_effects(self, unit_id: str, unit, game_state: Dict) -> None:
        """Check and update conditional effects based on unit state"""
        if unit_id not in self.unit_effects:
            return

        effects_to_remove = []
        effects_to_add = []

        # Check for Sword & Board effect
        if "Sword & Board" in unit.special:
            sword_board_effect = self.get_effect(unit_id, "Sword & Board Defense")

            # Unit hasn't moved this turn
            if unit.moves_remaining == unit.move:
                if not sword_board_effect:
                    # Add the effect
                    effect = Effect(
                        effect_type=EffectType.DAMAGE_REDUCTION,
                        name="Sword & Board Defense",
                        description="Negates the first point of damage taken next turn",
                        value=1,
                        duration=EffectDuration.CONDITIONAL,
                        condition="hasnt_moved"
                    )
                    effects_to_add.append(effect)
            else:
                # Unit has moved, remove the effect
                if sword_board_effect:
                    effects_to_remove.append("Sword & Board Defense")

        # Check for Trusty Steed effect
        if "Trusty Steed" in unit.special:
            steed_effect = self.get_effect(unit_id, "Trusty Steed Bonus")

            # Unit hasn't attacked this turn
            if not unit.has_attacked:
                if not steed_effect:
                    effect = Effect(
                        effect_type=EffectType.MOVEMENT_BONUS,
                        name="Trusty Steed Bonus",
                        description="+1 movement this turn",
                        value=1,
                        duration=EffectDuration.CONDITIONAL,
                        condition="hasnt_attacked"
                    )
                    effects_to_add.append(effect)
            else:
                # Unit has attacked, remove the effect
                if steed_effect:
                    effects_to_remove.append("Trusty Steed Bonus")

        # Apply changes
        for effect in effects_to_add:
            self.add_effect(unit_id, effect)

        for effect_name in effects_to_remove:
            self.remove_effect(unit_id, effect_name)

    def check_aura_effects(self, unit_positions: Dict, ability_system) -> None:
        """Check and update aura effects (like Spotter) based on unit positions"""
        # Clear all aura effects first
        for unit_id in self.unit_effects:
            effects_to_remove = []
            for effect in self.unit_effects[unit_id]:
                if effect.source_unit_id:  # This is an aura effect from another unit
                    effects_to_remove.append(effect.name)

            for effect_name in effects_to_remove:
                self.remove_effect(unit_id, effect_name)

        # Reapply aura effects
        for spotter_id, spotter_unit in unit_positions.items():
            if "Spotter" in spotter_unit.special:
                # Find all friendly units within range 4
                for target_id, target_unit in unit_positions.items():
                    if (target_unit.faction == spotter_unit.faction and
                        target_unit != spotter_unit):

                        distance = max(abs(spotter_unit.position[0] - target_unit.position[0]),
                                     abs(spotter_unit.position[1] - target_unit.position[1]))

                        if distance <= 4:
                            effect = Effect(
                                effect_type=EffectType.RANGE_BONUS,
                                name="Spotter Bonus",
                                description="+1 effective range from Spotter",
                                value=1,
                                duration=EffectDuration.CONDITIONAL,
                                source_unit_id=spotter_id,
                                condition="within_spotter_range"
                            )
                            self.add_effect(target_id, effect)

    def get_total_effect_value(self, unit_id: str, effect_type: EffectType) -> int:
        """Get the total value of all effects of a specific type on a unit"""
        total = 0
        for effect in self.get_all_effects(unit_id):
            if effect.effect_type == effect_type:
                total += effect.value
        return total

    def get_effect_summary(self, unit_id: str) -> List[str]:
        """Get a human-readable summary of all effects on a unit"""
        effects = self.get_all_effects(unit_id)
        if not effects:
            return ["No active effects"]

        summary = []
        for effect in effects:
            duration_text = ""
            if effect.duration == EffectDuration.TIMED:
                duration_text = f" ({effect.turns_remaining} turns)"
            elif effect.duration == EffectDuration.UNTIL_NEXT_TURN:
                duration_text = " (until next turn)"
            elif effect.duration == EffectDuration.UNTIL_END_OF_TURN:
                duration_text = " (until end of turn)"

            summary.append(f"{effect.name}: {effect.description}{duration_text}")

        return summary


# Helper functions for integration with main game

def apply_effects_to_damage(effects_system: EffectsSystem, unit_id: str, incoming_damage: int) -> int:
    """Apply damage reduction effects to incoming damage"""
    reduction = effects_system.get_total_effect_value(unit_id, EffectType.DAMAGE_REDUCTION)
    final_damage = max(1, incoming_damage - reduction)

    # Remove one-time damage reduction effects (like Sword & Board)
    sword_board_effect = effects_system.get_effect(unit_id, "Sword & Board Defense")
    if sword_board_effect and reduction > 0:
        effects_system.remove_effect(unit_id, "Sword & Board Defense")

    return final_damage


def apply_effects_to_range(effects_system: EffectsSystem, unit_id: str, base_range: int) -> int:
    """Apply range bonus effects to a unit's range"""
    bonus = effects_system.get_total_effect_value(unit_id, EffectType.RANGE_BONUS)
    return base_range + bonus


def apply_effects_to_movement(effects_system: EffectsSystem, unit_id: str, base_movement: int) -> int:
    """Apply movement bonus effects to a unit's movement"""
    bonus = effects_system.get_total_effect_value(unit_id, EffectType.MOVEMENT_BONUS)
    return base_movement + bonus


def apply_effects_to_attack(effects_system: EffectsSystem, unit_id: str, base_attack: int) -> int:
    """Apply attack bonus effects to a unit's attack"""
    bonus = effects_system.get_total_effect_value(unit_id, EffectType.ATTACK_BONUS)
    return base_attack + bonus


def can_unit_attack(unit, effects_system) -> bool:
    """Check if a unit can attack, considering effects like Trusty Steed"""
    if unit.has_attacked:
        return False

    # Special case for Trusty Steed: if unit has the effect, they can't attack
    if "Trusty Steed" in unit.special:
        steed_effect = effects_system.get_effect(unit.unit_id, "Trusty Steed Bonus")
        if steed_effect:  # Unit is using Trusty Steed bonus, so can't attack
            return False

    return True