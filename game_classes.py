class GamePiece:
    def __init__(self, unit_id, unit_class, name, hp, move, range, atk, special, position, terrain, faction):
        self.unit_id = unit_id
        self.unit_class = unit_class
        self.name = name
        self.hp = hp
        self.move = move
        self.moves_remaining = move  # New attribute
        self.range = range
        self.atk = atk
        self.special = special
        self.position = position  # Tuple (row, col)
        self.terrain = terrain  # Type of terrain the unit is on
        self.faction = faction  # Faction name
        self.has_attacked = False  # Track if unit has attacked this turn

    def __repr__(self):
        return f"{self.name} (HP: {self.hp}, Pos: {self.position}, Terrain: {self.terrain}, Moves Remaining: {self.moves_remaining})"