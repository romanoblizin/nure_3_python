from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .constants import BlockId, RESOURCE_BLOCKS, BLOCK_DB_FIELD
from .database import MinePlayer, MineEconomyRate, get_global_totals


BASE_VALUE: dict[BlockId, float] = {
    BlockId.STONE: 0.02,
    BlockId.GRAVEL: 0.03,
    BlockId.DIORITE: 0.01,
    BlockId.ANDESITE: 0.01,
    BlockId.GRANITE: 0.01,

    BlockId.COAL: 0.10,
    BlockId.COPPER: 0.12,

    BlockId.IRON: 0.40,
    BlockId.GOLD: 0.60,

    BlockId.LAPIS: 0.20,
    BlockId.REDSTONE: 0.20,

    BlockId.ANVIL: 0.50,

    BlockId.DIAMOND: 1.00,
    BlockId.EMERALD: 1.30,
}

MIN_RATE: float = 0.01
MAX_RATE: float = 10.0 
ALPHA: float = 0.5


async def compute_current_mid_rates(
    session: AsyncSession,
    *,
    alpha: float = ALPHA,
    min_rate: float = MIN_RATE,
    max_rate: float = MAX_RATE,
) -> dict[BlockId, float]:
    global_totals = await get_global_totals(session)
    rates: dict[BlockId, float] = {}

    diamonds_total = max(global_totals.get(BlockId.DIAMOND, 0), 1)

    for bid in RESOURCE_BLOCKS:
        base = BASE_VALUE.get(bid, 0.01)

        if bid is BlockId.DIAMOND:
            mid = 1.0
        else:
            resource_total = max(global_totals.get(bid, 0), 1)
            ratio = diamonds_total / resource_total
            raw = base * (ratio ** alpha)
            mid = max(raw, min(min_rate, max_rate))

        rates[bid] = mid

    return rates


async def get_mid_rates_for_date(
    session: AsyncSession,
    date: datetime.date,
) -> dict[BlockId, float]:
    stmt = select(MineEconomyRate).where(MineEconomyRate.date == date)
    res = await session.execute(stmt)
    rows = list(res.scalars())

    if not rows:
        return {}

    rates: dict[BlockId, float] = {}
    for row in rows:
        rates[row.resource] = float(row.rate)

    return rates


async def get_or_create_today_mid_rates(
    session: AsyncSession,
    *,
    alpha: float = ALPHA,
) -> dict[BlockId, float]:
    today = datetime.date.today()

    stmt = select(MineEconomyRate).where(MineEconomyRate.date == today)
    res = await session.execute(stmt)
    rows = list(res.scalars())

    if rows:
        rates: dict[BlockId, float] = {row.resource: float(row.rate) for row in rows}
        rates.setdefault(BlockId.DIAMOND, 1.0)
        return rates

    mid_rates = await compute_current_mid_rates(session, alpha=alpha)

    for bid, rate in mid_rates.items():
        row = MineEconomyRate(
            date=today,
            resource=bid,
            rate=rate,
        )
        session.add(row)

    return mid_rates


def get_spread_for_trade_value(diamonds: float) -> float:
    if diamonds >= 64:
        return 0.05
    if diamonds >= 32:
        return 0.10
    if diamonds >= 16:
        return 0.15
    return 0.20


def compute_sell_rate_for_trade(
    mid_rate: float,
    trade_value_in_diamonds: float,
) -> float:
    spread = get_spread_for_trade_value(trade_value_in_diamonds)
    sell_rate = mid_rate * (1.0 - spread / 2.0)
    return sell_rate


def compute_buy_rate_for_trade(
    mid_rate: float,
    trade_value_in_diamonds: float,
) -> float:
    spread = get_spread_for_trade_value(trade_value_in_diamonds)
    buy_rate = mid_rate * (1.0 + spread / 2.0)
    return buy_rate


def sell_resource(
    amount: int,
    mid_rate: float,
) -> int:
    if amount <= 0 or mid_rate <= 0.0:
        return 0

    trade_value = amount * mid_rate
    sell_rate = compute_sell_rate_for_trade(mid_rate, trade_value)
    diamonds = int(amount * sell_rate)
    return diamonds


def buy_resource(
    diamonds: int,
    mid_rate: float,
) -> int:
    if diamonds <= 0 or mid_rate <= 0.0:
        return 0

    trade_value = float(diamonds)
    buy_rate = compute_buy_rate_for_trade(mid_rate, trade_value)
    amount = int(diamonds / buy_rate)
    return amount


def get_player_resources(player: MinePlayer) -> dict[BlockId, int]:
    result: dict[BlockId, int] = {}
    for bid, column_name in BLOCK_DB_FIELD.items():
        amount = getattr(player, column_name, 0)
        result[bid] = int(amount or 0)
    return result


def compute_player_potential_diamonds(
    player: MinePlayer,
    mid_rates: dict[BlockId, float],
) -> int:
    resources = get_player_resources(player)
    total_diamonds = 0.0

    for bid, amount in resources.items():
        if amount <= 0:
            continue

        if bid is BlockId.DIAMOND:
            total_diamonds += amount
            continue

        rate = mid_rates.get(bid)
        if rate is None or rate <= 0.0:
            continue

        trade_value = amount * rate
        sell_rate = compute_sell_rate_for_trade(rate, trade_value)
        total_diamonds += amount * sell_rate

    return int(total_diamonds)