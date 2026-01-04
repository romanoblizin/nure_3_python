from __future__ import annotations

import random
import asyncio

import discord

from .config import MineConfig
from .constants import BlockId, Biome, Direction, BLOCK_EMOJI, LAVA_BLOCKS
from .models import Board, MineSession, MoveResult, Block


def get_block_weights_for_height(
    cfg: MineConfig,
    block_height: int,
    biome: Biome
) -> dict[BlockId, float]:
    w: dict[BlockId, float] = {}

    w[BlockId.STONE] = 20.0
    w[BlockId.COAL] = 2.0
    w[BlockId.IRON] = 1.5
    w[BlockId.GOLD] = 1.0
    w[BlockId.COPPER] = 2.0
    w[BlockId.LAPIS] = 0.8
    w[BlockId.REDSTONE] = 0.8
    w[BlockId.DIAMOND] = 0.3

    w[BlockId.GRAVEL] = 2.5
    w[BlockId.DIORITE] = 2.0
    w[BlockId.ANDESITE] = 2.0
    w[BlockId.GRANITE] = 2.0

    w[BlockId.ANVIL] = 0.05
    w[BlockId.LAVA] = 1.5
    w[BlockId.EMERALD] = 0.6 if biome is Biome.MOUNTAIN else 0.0

    depth = 1 - block_height / (cfg.max_height - cfg.min_height)

    for bid in (BlockId.DIAMOND, BlockId.GOLD, BlockId.LAPIS, BlockId.REDSTONE, BlockId.LAVA):
        w[bid] *= 0.5 + depth

    for bid in (BlockId.COAL, BlockId.IRON,BlockId.COPPER, BlockId.EMERALD):
        w[bid] *= 0.5 + (1 - depth)

    return w


def _choice_with_weights(weights: dict[BlockId, float]) -> BlockId:
    population = list(weights.keys())
    values = list(weights.values())
    return random.choices(population, weights=values, k=1)[0]



def render_nearby_blocks(cfg: MineConfig, session: MineSession, height: int, column: int):
    deltas: dict [str, tuple[int, int]] = {
        "top": (1, 0),
        "bottom": (-1, 0),
        "left": (0, -1),
        "right": (0, 1),
    }

    blocks: dict[str, Block] = {
        direction: get_or_generate_block(cfg, session, height + dh, column + dc)
            for (direction, (dh, dc)) in deltas.items()
    }

    conversions: dict[str, dict[BlockId, BlockId]] = {
        "top": {
            BlockId.LAVA: BlockId.LAVATOP,
            BlockId.LAVARIGHT: BlockId.LAVATOPRIGHT,
        },
        "bottom": {
            BlockId.LAVA: BlockId.LAVABOTTOM,
            BlockId.LAVARIGHT: BlockId.LAVABOTTOMRIGHT,
        },
        "left": {
            BlockId.LAVA: BlockId.LAVALEFT,
            BlockId.LAVABOTTOM: BlockId.LAVABOTTOMLEFT,
            BlockId.LAVATOP: BlockId.LAVATOPLEFT,
            BlockId.LAVABOTTOMRIGHT: BlockId.COBBLESTONE,
            BlockId.LAVATOPRIGHT: BlockId.COBBLESTONE,
        },
        "right": {
            BlockId.LAVA: BlockId.LAVARIGHT,
        },
    }

    for direction_, conversion in conversions.items():
        block = blocks[direction_]
        block.seen = True
        
        for block_before, block_after in conversion.items():
            if block.block_id == block_before:
                block.block_id = block_after
                break


def get_or_generate_block(
    cfg: MineConfig,
    session: MineSession,
    block_height: int,
    column: int
) -> Block:
    if (block_height < cfg.min_height):
        return Block(BlockId.BEDROCK)
    elif (block_height > cfg.max_height):
        return Block(BlockId.DIRT)

    if session.world.get((block_height, column)) is not None:
        return session.world[block_height, column]
    
    weights = get_block_weights_for_height(cfg, block_height, session.biome)
    block = Block(_choice_with_weights(weights))

    session.world[block_height, column] = block
    return block


def random_block(cfg: MineConfig, block_height: int, biome: Biome) -> BlockId:
    w = get_block_weights_for_height(cfg, block_height, biome)
    return _choice_with_weights(w)


def generate_board(
    cfg: MineConfig,
    session: MineSession,
    cat_model: BlockId = BlockId.CAT
) -> Board:
    cells = [[Block(BlockId.AIR) for _ in range(cfg.board_width)] for _ in range(cfg.board_height)]
    board = Board(
        width=cfg.board_width,
        height=cfg.board_height,
        cells=cells,
    )
    center_r, center_c = board.center

    for r in range(cfg.board_height):
        blocks_height = board.center[0] - r + session.height

        for c in range(cfg.board_width):            
            cells[r][c] = get_or_generate_block(cfg, session, blocks_height, c)

    cells[center_r][center_c] = Block(cat_model)
    return board


def render_board(board: Board, xray: bool) -> str:
    lines: list[str] = []

    for r in range(board.height):
        row_emojis = [
            BLOCK_EMOJI[
                b.block_id if (b.block_id in [
                    BlockId.BEDROCK, BlockId.DIRT,
                    BlockId.CAT, BlockId.CATANVIL, BlockId.CATGRAVEL, BlockId.CATLAVA
                ] or b.seen or xray) else BlockId.STONE
            ] for b in board.cells[r]
        ]
        lines.append("".join(row_emojis))

    return "\n".join(lines)


def move(cfg: MineConfig, session: MineSession, direction: Direction) -> MoveResult:
    if (
        direction is direction.DOWN and session.height == cfg.min_height
        or direction is direction.UP and session.height == cfg.max_height
    ):
        board = generate_board(cfg, session)
        return MoveResult(
            board=board,
            gained_block=None,
            hp=session.hp,
            totems=session.totems,
        )

    if direction is Direction.RIGHT:
        session.world[session.height, cfg.board_width // 2] = Block(BlockId.AIR, True)
        new_world: dict[tuple[int, int], Block] = {}

        for (height, col), block in session.world.items():
            new_col = col - 1
            if new_col >= 0:
                new_world[(height, new_col)] = block

        session.world = new_world
    elif direction is Direction.UP:
        session.world[session.height, cfg.board_width // 2] = Block(BlockId.COBBLESTONE, True)
        session.height += 1
    elif direction is Direction.DOWN:
        session.world[session.height, cfg.board_width // 2] = Block(BlockId.AIR, True)
        session.height -= 1

    target_block = get_or_generate_block(cfg, session, session.height, cfg.board_width//2).block_id

    hp = session.hp
    totems = session.totems
    is_dead = False
    death_reason: str | None = None
    cat_model = BlockId.CAT


    if target_block in LAVA_BLOCKS:
        cat_model = BlockId.CATLAVA

        if totems > 0:
            totems -= 1
            hp = cfg.overheal_cap
        else:
            hp = 0
            totems = 0
            is_dead = True
            death_reason = BlockId.LAVA
        
    elif target_block not in [BlockId.AIR, BlockId.COBBLESTONE]:
        target_h = session.height
        target_c = cfg.board_width // 2

        render_nearby_blocks(cfg, session, target_h, target_c)

        if direction != Direction.DOWN:
            while (cfg.max_height > target_h):
                target_h += 1
                target_top_block = get_or_generate_block(cfg, session, target_h, target_c)

                if target_top_block.block_id is BlockId.ANVIL:
                    cat_model = BlockId.CATANVIL
                    session.world[target_h, target_c] = Block(BlockId.AIR, True)
                    render_nearby_blocks(cfg, session, target_h, target_c)
                    
                    if hp > cfg.anvil_damage:
                        hp -= cfg.anvil_damage
                    elif totems > 0:
                        totems -= 1
                        hp = cfg.overheal_cap
                    else:
                        hp = 0
                        totems = 0
                        is_dead = True
                        death_reason = BlockId.ANVIL

                elif target_top_block.block_id is BlockId.GRAVEL:
                    cat_model = BlockId.CATGRAVEL
                    session.world[target_h, target_c] = Block(BlockId.AIR, True)
                    render_nearby_blocks(cfg, session, target_h, target_c)

                    if hp > cfg.gravel_damage:
                        hp -= cfg.gravel_damage
                    elif totems > 0:
                        totems -= 1
                        hp = cfg.overheal_cap
                    else:
                        hp = 0
                        totems = 0
                        is_dead = True
                        death_reason = BlockId.GRAVEL

                else:
                    break

    board = generate_board(cfg, session, cat_model)
    
    return MoveResult(
        board=board,
        gained_block=target_block if target_block != BlockId.AIR else None,
        hp=hp,
        totems=totems,
        is_dead=is_dead,
        death_reason=death_reason,
    )

async def save_animation(interaction: discord.Interaction, cfg: MineConfig, session: MineSession):
    board = generate_board(cfg, session, BlockId.CAT)

    for i in range(cfg.board_height//2):
        board.cells[(cfg.board_height//2)-1-i][cfg.board_width//2] = Block(BlockId.CAT)
        board.cells[(cfg.board_height//2)-i][cfg.board_width//2] = Block(BlockId.COBBLESTONE, True)
        await asyncio.sleep(0.25)
        await interaction.message.edit(content=render_board(board, session.xray))

    await asyncio.sleep(0.25)
    board.cells[0][cfg.board_width//2] = Block(BlockId.COBBLESTONE, True)
    await interaction.message.edit(content=render_board(board, session.xray))