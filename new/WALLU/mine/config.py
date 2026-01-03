from dataclasses import dataclass


@dataclass
class MineConfig:
    board_width: int = 5
    board_height: int = 5

    min_height: int = 1
    max_height: int = 30

    max_hp: int = 20
    overheal_cap: int = 24
    apple_heal: int = 8

    lava_damage: int = 20
    anvil_damage: int = 12
    gravel_damage: int = 4