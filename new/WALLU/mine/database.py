from __future__ import annotations

import datetime

from sqlalchemy import Integer, Float, Date, Enum as SAEnum, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncSession

from .constants import BlockId, BLOCK_DB_FIELD, PICKAXE_SPEC
from .models import MineSession, PickaxeId


class Base(DeclarativeBase):
    pass


class MinePlayer(Base):
    __tablename__ = "mine_players"

    uid: Mapped[int] = mapped_column(Integer, primary_key=True)

    deaths: Mapped[int] = mapped_column(Integer, default=0)

    diamonds: Mapped[int] = mapped_column(Integer, default=0)
    emeralds: Mapped[int] = mapped_column(Integer, default=0)
    stone: Mapped[int] = mapped_column(Integer, default=0)
    gold: Mapped[int] = mapped_column(Integer, default=0)
    iron: Mapped[int] = mapped_column(Integer, default=0)
    lapis: Mapped[int] = mapped_column(Integer, default=0)
    redstone: Mapped[int] = mapped_column(Integer, default=0)
    copper: Mapped[int] = mapped_column(Integer, default=0)
    coal: Mapped[int] = mapped_column(Integer, default=0)

    gravel: Mapped[int] = mapped_column(Integer, default=0)
    diorite: Mapped[int] = mapped_column(Integer, default=0)
    andesite: Mapped[int] = mapped_column(Integer, default=0)
    granite: Mapped[int] = mapped_column(Integer, default=0)

    anvils: Mapped[int] = mapped_column(Integer, default=0)
    totems: Mapped[int] = mapped_column(Integer, default=0)

    total_blocks_mined: Mapped[int] = mapped_column(Integer, default=0)


class MineEconomyRate(Base):
    __tablename__ = "mine_rates"

    date: Mapped[datetime.date] = mapped_column(Date, primary_key=True)
    resource: Mapped[BlockId] = mapped_column(SAEnum(BlockId), primary_key=True)
    rate: Mapped[float] = mapped_column(Float)


async def get_or_create_player(session: AsyncSession, userId: int) -> MinePlayer:
    res = await session.execute(select(MinePlayer).where(MinePlayer.uid == userId))
    player = res.scalar_one_or_none()

    if player is None:
        player = MinePlayer(uid=userId)
        session.add(player)

    return player


async def get_all_players(session: AsyncSession) -> list[MinePlayer]:
    res = await session.execute(select(MinePlayer))
    return list(res.scalars())


async def get_global_totals(session: AsyncSession) -> dict[BlockId, int]:
    totals: dict[BlockId, int] = {}

    for bid, column_name in BLOCK_DB_FIELD.items():
        col = getattr(MinePlayer, column_name)
        res = await session.execute(select(func.sum(col)))
        totals[bid] = int(res.scalar() or 0)

    return totals


async def start_mine(player: MinePlayer, pickaxe: PickaxeId, apples: int, anvils_spend: int):
    player.anvils -= anvils_spend
    player.totems += anvils_spend
    player.gold -= apples * 2

    pickaxe_cost = PICKAXE_SPEC[pickaxe].cost
    for bid, need in pickaxe_cost.items():
        setattr(player, bid.value, getattr(player, bid.value)-need)


async def apply_results(
    player: MinePlayer,
    session: MineSession,
    *,
    dead: bool,
):
    player.total_blocks_mined += session.blocks_mined

    if dead:
        player.deaths += 1
    else:
        for bid, amount in session.gained_blocks.items():
            if amount == 0:
                continue

            column_name = BLOCK_DB_FIELD.get(bid)
            if column_name is None:
                continue

            current = getattr(player, column_name)
            setattr(player, column_name, int(current) + int(amount) * (4 if session.xray else 1))