from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .constants import BlockId, Biome, PickaxeId, MineRunState


@dataclass
class Block:
    block_id: BlockId
    seen: bool = False


@dataclass
class Board:
    width: int
    height: int
    cells: list[list[Block]]

    @property
    def center(self) -> tuple[int, int]:
        return self.height // 2, self.width // 2


@dataclass
class MoveResult:
    board: Board
    gained_block: Optional[BlockId]
    hp: int
    totems: int
    is_dead: bool = None
    death_reason: Optional[BlockId] = None


@dataclass
class MineSession:
    user_id: int

    biome: Biome
    height: int
    xray: bool

    hp: int
    totems: int
    apples: int

    pickaxe: PickaxeId
    durability_left: int
    blocks_mined: int = 0
    gained_blocks: dict[BlockId, int] = field(default_factory=dict)

    state: MineRunState = MineRunState.MINING

    world: dict[tuple[int, int], Block] = field(default_factory=dict)