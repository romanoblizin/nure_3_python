from __future__ import annotations

import random

import discord
from discord.ext import commands, bridge

from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select

from functions import checkperms, engine, getembed
from config import ownerlist

from WALLU.mine.config import MineConfig
from WALLU.mine.constants import (
    BlockId,
    BLOCK_EMOJI,
    Biome,
    Direction,
    MineRunState,
    PickaxeId,
    PICKAXE_SPEC,
    BLOCK_STR,
    RESOURCE_BLOCKS,
    BLOCK_DB_FIELD
)
from WALLU.mine.models import MineSession, Board
from WALLU.mine.generation import (
    generate_board,
    render_board,
    move as generation_move,
    render_nearby_blocks,
    save_animation
)
from WALLU.mine.database import get_or_create_player, apply_results, start_mine, MinePlayer
from WALLU.mine.economy import (
    get_or_create_today_mid_rates,
    compute_player_potential_diamonds,
    sell_resource,
    buy_resource
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

def get_resources_str(resources: dict[BlockId, int]) -> str:
    parts = []

    for bid, amount in resources.items():
        if amount != 0:
            parts.append(f"{amount} {BLOCK_STR[bid]}")

    return ", ".join(parts)


class MineShopView(discord.ui.View):
    def __init__(self, cog: Minecraft, user_id: int, player):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.player = player

        self.cost = ""
        
        self.totems = int(getattr(self.player, "totems", 0))
        self.anvils_spend = 0
        self.apples = 0
        self.pickaxe = PickaxeId.WOODEN
        self.xray = False

        self.refresh_view()

    async def check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Ви не можете користуватися цим магазином!",
                ephemeral=True
            )
            return False
        return True
    
    def rebuild_select(self):
        self.select_pickaxe.options.clear()
    
        for pickaxe in PickaxeId:
            if pickaxe == PickaxeId.GOD and self.user_id not in ownerlist: continue

            label = f"{PICKAXE_SPEC[pickaxe].title.capitalize()} кірка"
            self.select_pickaxe.add_option(
                label=label,
                value=pickaxe.value,
                description=
                    get_resources_str(PICKAXE_SPEC[pickaxe].cost)
                    or ("iq > 300" if pickaxe == PickaxeId.GOD else "=)"),
                emoji=PICKAXE_SPEC[pickaxe].emoji,
                default=(pickaxe == self.pickaxe),
            )

    def refresh_view(self):
        self.rebuild_select()
    
        self.btn_totem.label = f"Тотем безсмертя ({self.totems})"
        self.btn_apple.label = f"Золоте яблуко ({self.apples})"    

        available: dict[BlockId, int] = {}
        for bid, column in BLOCK_DB_FIELD.items():
            available[bid] = int(getattr(self.player, column, 0))

        available[BlockId.GOLD] -= self.apples * 2
        available[BlockId.ANVIL] -= self.anvils_spend

        pickaxe_cost = PICKAXE_SPEC[self.pickaxe].cost
        for bid, need in pickaxe_cost.items():
            available[bid] -= need

        self.btn_totem.disabled = (available[BlockId.ANVIL] == 0)
        self.btn_apple.disabled = (available[BlockId.GOLD] < 2)
        self.btn_xray.style = discord.ButtonStyle.green if self.xray else discord.ButtonStyle.red

        spent: dict[BlockId, int] = {}
        for bid, column in BLOCK_DB_FIELD.items():
            spent[bid] = int(getattr(self.player, column, 0)) - available[bid]

        self.cost = get_resources_str(spent)

    async def update_message(self, interaction: discord.Interaction):
        self.refresh_view()

        await interaction.response.edit_message(
            content=f"# Зберіть інвентар:\nЗагальна вартість: {self.cost if self.cost else '---'}",
            view=self
        )


    @discord.ui.button(
        label="Тотем безсмертя (0)",
        style=discord.ButtonStyle.blurple,
        emoji="🪆",
        row=1,
    )
    async def btn_totem(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        self.totems += 1
        self.anvils_spend += 1
        await self.update_message(interaction)

    @discord.ui.button(
        label="Золоте яблуко (0)",
        style=discord.ButtonStyle.blurple,
        emoji="🍎",
        row=1,
    )
    async def btn_apple(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        self.apples += 1
        await self.update_message(interaction)

    @discord.ui.button(
        label="X-RAY",
        style=discord.ButtonStyle.red,
        emoji="🐀",
        row=1,
    )
    async def btn_xray(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        self.xray = not self.xray
        await self.update_message(interaction)

    @discord.ui.select(
        placeholder="Оберіть кірку...", min_values=1, max_values=1, row=2, options=[]
    )
    async def select_pickaxe(
        self,
        select: discord.ui.Select,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        available: dict[BlockId, int] = {}
        for bid, column in BLOCK_DB_FIELD.items():
            available[bid] = int(getattr(self.player, column, 0))

        available[BlockId.GOLD] -= self.apples * 2

        pickaxe = PickaxeId(select.values[0])

        cost = PICKAXE_SPEC[pickaxe].cost
        for bid, need in cost.items():
            if available[bid] < need:
                self.refresh_view()
                await interaction.message.edit(view=self)
                await interaction.respond(
                    "У вас недостатньо ресурсів для крафту цієї кірки!",
                    ephemeral=True
                )
                return
        
        self.pickaxe = pickaxe
        await self.update_message(interaction)

    @discord.ui.button(
        label="Спуститися у шахту",
        style=discord.ButtonStyle.green,
        row=3,
    )
    async def btn_start(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        async with SessionLocal() as cur:
            player = await get_or_create_player(cur, self.user_id)
            await start_mine(player, self.pickaxe, self.apples, self.anvils_spend)
            await cur.commit()

        session = MineSession(
            user_id=self.user_id,
            biome=Biome.MOUNTAIN if random.random() <= 0.1 else Biome.NORMAL,
            height=self.cog.cfg.max_height,
            xray=self.xray,
            hp=self.cog.cfg.max_hp,
            totems=self.totems,
            apples=self.apples,
            pickaxe=self.pickaxe,
            durability_left=PICKAXE_SPEC[self.pickaxe].durability,
        )

        self.cog.sessions[self.user_id] = session

        render_nearby_blocks(self.cog.cfg, session, session.height, self.cog.cfg.board_width // 2)

        board = generate_board(self.cog.cfg, session)
        board_text = render_board(board, xray=session.xray)
    
        view = MineSessionView(self.cog, session, self.user_id, board)
        await interaction.response.edit_message(content=board_text, view=view)

    @discord.ui.button(
        label="Закрити магазин",
        style=discord.ButtonStyle.red,
        row=3,
    )
    async def btn_close(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        await interaction.message.delete()

        
class MineSessionView(discord.ui.View):
    def __init__(self, cog: Minecraft, session: MineSession, user_id: int, board: Board):
        super().__init__(timeout=600)
        self.cog = cog
        self.session = session
        self.user_id = user_id
        self.current_board = board

        self.refresh_buttons()


    async def check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "Ця шахта не належить вам!",
                ephemeral=True
            )
            return False
        return True


    def refresh_buttons(self):
        max_durab = PICKAXE_SPEC[self.session.pickaxe].durability

        height_str = str(self.session.height)
        durab_str = f"{self.session.durability_left}/{max_durab}"
        blocks_str = str(self.session.blocks_mined)
        hp_str = f"{self.session.hp}/{self.cog.cfg.max_hp} ({self.session.totems})"
        heals_str = str(self.session.apples)

        blocks_len = len(blocks_str)
        durab_len = len(durab_str)

        blocks_pad = max(0, durab_len - blocks_len)
        self.btn_blocks.label = blocks_str + "⠀" * blocks_pad

        right_pad = max(blocks_len, durab_len)
        self.btn_right.label = "⠀" * right_pad

        durab_pad = max(0, blocks_len - durab_len) + 1
        self.btn_durability.label = durab_str + "⠀" * durab_pad

        self.btn_height.label = height_str

        self.btn_hp.label = hp_str

        self.btn_heal.label = heals_str
        self.btn_heal.disabled = self.session.apples <= 0

        self.btn_up.disabled = self.session.height >= self.cog.cfg.max_height
        self.btn_down.disabled = self.session.height <= self.cog.cfg.min_height
        if self.session.height >= 10:
            self.btn_up.label = "⠀"
            self.btn_down.label = "⠀"
        else:
            self.btn_up.label = ""
            self.btn_down.label = ""
        

    async def update_message(
        self,
        interaction: discord.Interaction,
        disabled: bool = False,
    ) -> None:
        self.refresh_buttons()

        if disabled:
            for child in self.children:
                child.disabled = True

        board_text = render_board(self.current_board, xray=self.session.xray)
        await interaction.response.edit_message(content=board_text, view=self)


    async def handle_move(
        self,
        interaction: discord.Interaction,
        direction: Direction,
    ) -> None:
        if not await self.check_author(interaction): return

        if self.session.state is not MineRunState.MINING:
            await interaction.response.send_message("Ця шахта закинута!", ephemeral=True)
            return

        cfg = self.cog.cfg
        session = self.session

        result = generation_move(cfg, session, direction)

        async with SessionLocal() as cur:
            player = await get_or_create_player(cur, session.user_id)
            player.totems = result.totems
            await cur.commit()

        session.hp = result.hp
        session.totems = result.totems

        if result.is_dead:
            session.state = MineRunState.DEAD
            self.current_board = result.board

            async with SessionLocal() as cur:
                player = await get_or_create_player(cur, session.user_id)
                await apply_results(player, session, dead=True)
                await cur.commit()

            self.cog.sessions.pop(session.user_id)
            await self.update_message(interaction, disabled=True)
            return

        if result.gained_block is not None:
            session.durability_left = session.durability_left - 1

            if result.gained_block != BlockId.COBBLESTONE:
                session.blocks_mined += 1
                session.gained_blocks[result.gained_block] = (
                    session.gained_blocks.get(result.gained_block, 0) + 1
                )

        if session.durability_left <= 0:
            session.state = MineRunState.SAVED
            self.current_board = result.board

            async with SessionLocal() as cur:
                player = await get_or_create_player(cur, session.user_id)
                await apply_results(player, session, dead=False)
                await cur.commit()

            self.cog.sessions.pop(session.user_id)
            await self.update_message(interaction, disabled=True)
            return

        self.current_board = result.board
        await self.update_message(interaction)


    @discord.ui.button(
        emoji="⬆️",
        style=discord.ButtonStyle.green,
        row=1,
    )
    async def btn_up(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await self.handle_move(interaction, Direction.UP)

    @discord.ui.button(
        emoji="🗿",
        style=discord.ButtonStyle.blurple,
        label="0",
        row=1,
        disabled=True,
    )
    async def btn_blocks(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        return

    @discord.ui.button(
        emoji="🍎",
        style=discord.ButtonStyle.gray,
        label="0",
        row=1,
        disabled=True,
    )
    async def btn_heal(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        self.session.apples -= 1 
        self.session.hp = min(self.session.hp + self.cog.cfg.apple_heal, self.cog.cfg.overheal_cap)
        await self.update_message(interaction)

    @discord.ui.button(
        emoji="↕️",
        style=discord.ButtonStyle.blurple,
        label="0",
        row=2,
        disabled=True,
    )
    async def btn_height(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        return

    @discord.ui.button(
        emoji="➡️",
        style=discord.ButtonStyle.green,
        label="",
        row=2,
    )
    async def btn_right(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await self.handle_move(interaction, Direction.RIGHT)

    @discord.ui.button(
        emoji="📦",
        style=discord.ButtonStyle.red,
        row=2,
    )
    async def btn_save(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        if not await self.check_author(interaction): return

        if self.session.state is not MineRunState.MINING:
            await interaction.response.send_message("Цю шахту вже закинуто!", ephemeral=True)
            return

        session = self.session

        async with SessionLocal() as cur:
            player = await get_or_create_player(cur, session.user_id)
            await apply_results(player, session, dead=False)
            await cur.commit()

        session.state = MineRunState.SAVED

        self.cog.sessions.pop(session.user_id)
        await self.update_message(interaction, disabled=True)
        await save_animation(interaction, self.cog.cfg, self.session)

    @discord.ui.button(
        emoji="⬇️",
        style=discord.ButtonStyle.green,
        row=3,
    )
    async def btn_down(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        await self.handle_move(interaction, Direction.DOWN)

    @discord.ui.button(
        emoji="🔨",
        style=discord.ButtonStyle.blurple,
        label="0/0",
        row=3,
        disabled=True,
    )
    async def btn_durability(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        return

    @discord.ui.button(
        emoji="❤️",
        style=discord.ButtonStyle.gray,
        label="0/0 (0)",
        row=3,
        disabled=True,
    )
    async def btn_hp(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ):
        return


class LeaderboardView(discord.ui.View):
    def __init__(self, cog: Minecraft, user_id: int, rows: list[tuple[int, int]]):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.rows = rows
        self.page = 0

        self.refresh_buttons()

    def page_slice(self) -> list[tuple[int, int]]:
        start = self.page * 10
        end = min(len(self.rows), start + 10)
        return self.rows[start:end]

    def refresh_buttons(self):
        total = len(self.rows)
        max_page = 0 if total == 0 else (total - 1) // 10

        self.btn_prev.disabled = self.page <= 0
        self.btn_next.disabled = self.page >= max_page
        shown_start = 0 if total == 0 else self.page * 10 + 1
        shown_end = 0 if total == 0 else min(total, self.page * 10 + 10)
        self.btn_page.label = f"{shown_start}-{shown_end}/{total}"

    def format_embed_description(self) -> str:
        lines = []
        for idx, (uid, value) in enumerate(self.page_slice(), start=self.page * 10 + 1):
            lines.append(f"**{idx}.** <@{uid}> — **{value}** 💎")
        return "\n".join(lines) if lines else "Пустувато..."

    async def check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id and interaction.user.id not in ownerlist:
            return False
        return True

    async def update(self, interaction: discord.Interaction):
        self.refresh_buttons()
        emb = self.format_embed_description()
        await interaction.response.edit_message(embed=emb, view=self)

    @discord.ui.button(label="⏪ Попередня", style=discord.ButtonStyle.blurple)
    async def btn_prev(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.check_author(interaction): return

        if self.page > 0:
            self.page -= 1
    
        await self.update(interaction)

    @discord.ui.button(label="0/0", style=discord.ButtonStyle.gray, disabled=True)
    async def btn_page(self, button: discord.ui.Button, interaction: discord.Interaction):
        return

    @discord.ui.button(label="Наступна ⏩", style=discord.ButtonStyle.blurple)
    async def btn_next(self, button: discord.ui.Button, interaction: discord.Interaction):
        if not await self.check_author(interaction): return

        total = len(self.rows)
        max_page = 0 if total == 0 else (total - 1) // 10
        if self.page < max_page:
            self.page += 1
    
        await self.update(interaction)


class TradeView(discord.ui.View):
    def __init__(self, cog: "Minecraft", user_id: int, player: MinePlayer, mid_rates: dict[BlockId, float]):
        super().__init__(timeout=600)
        self.cog = cog
        self.user_id = user_id
        self.player = player
        self.mid = mid_rates

        self.mode = False
        self.res: BlockId = BlockId.COAL
        self.amount: int = 1
        self.rebuild_select()

    async def check_author(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id and interaction.user.id not in ownerlist:
            await interaction.response.send_message(
                "Цей селянин з вами не торгує!",
                ephemeral=True
            )
            return False
        return True

    def rebuild_select(self):
        self.select_resource.options.clear()
        for bid in RESOURCE_BLOCKS:
            if bid == BlockId.DIAMOND: continue

            label = f"{BLOCK_STR[bid].capitalize()}"
            desc = f"{self.mid.get(bid, 0.0):.3f}💎"
            self.select_resource.add_option(
                label=label,
                value=bid.value,
                description=desc,
                emoji=BLOCK_EMOJI.get(bid, None),
                default=(bid == self.res),
            )

    def calc_preview(self) -> str:
        rate = self.mid.get(self.res, 0.0)
        if rate == 0.0:
            return "Курс недоступний."

        if self.mode:
            got = buy_resource(self.amount, rate)
            have_d = int(getattr(self.player, "diamonds", 0))
            return (
                f"В інвентарі: **{have_d}** 💎\n"
                f"Курс: **{rate:.3f}** 💎\n\n"
                f"Підсумок: **{self.amount}** 💎 -> **{got}** {BLOCK_EMOJI[self.res]}"
            )
        else:
            got = sell_resource(self.amount, rate)
            have = int(getattr(self.player, BLOCK_DB_FIELD[self.res], 0))
            return (
                f"В інвентарі: **{have}** {BLOCK_EMOJI[self.res]}\n"
                f"Курс: **{rate:.3f}** 💎\n\n"
                f"Підсумок: **{self.amount}** {BLOCK_EMOJI[self.res]} -> **{got}** 💎"
            )

    async def refresh_message(self, interaction: discord.Interaction):
        self.btn_mode.label = 'Купівля' if self.mode else 'Продаж'

        if self.mode:
            self.amount = min(
                self.amount, int(getattr(self.player, BLOCK_DB_FIELD[BlockId.DIAMOND], 0))
            )
        else:
            self.amount = min(
                self.amount, int(getattr(self.player, BLOCK_DB_FIELD[self.res], 0))
            )

        self.amount = max(1, self.amount)

        self.rebuild_select()
        embed = interaction.message.embeds[0]
        embed.description = self.calc_preview()
        await interaction.response.edit_message(embed=embed, view=self)

    async def change_amount(self, interaction: discord.Interaction, operation):
        if not await self.check_author(interaction): return
        self.amount = operation(self.amount)
        await self.refresh_message(interaction)

    @discord.ui.select(
        placeholder="Обери ресурс...", min_values=1, max_values=1, row=0, options=[]
    )
    async def select_resource(self, select: discord.ui.Select, interaction: discord.Interaction):
        if not await self.check_author(interaction): return
        self.res = BlockId(select.values[0])
        await self.refresh_message(interaction)

    @discord.ui.button(label="-1", style=discord.ButtonStyle.gray, row=1)
    async def minus1(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x-1)

    @discord.ui.button(label="-4", style=discord.ButtonStyle.gray, row=1)
    async def minus4(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x-4)

    @discord.ui.button(label="-16", style=discord.ButtonStyle.gray, row=1)
    async def minus16(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x-16)

    @discord.ui.button(label="мін.", style=discord.ButtonStyle.gray, row=1)
    async def min(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda _: 1)

    @discord.ui.button(label="+1", style=discord.ButtonStyle.gray, row=2)
    async def plus1(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x+1)

    @discord.ui.button(label="+4", style=discord.ButtonStyle.gray, row=2)
    async def plus4(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x+4)

    @discord.ui.button(label="+16", style=discord.ButtonStyle.gray, row=2)
    async def plus16(self, btn: discord.ui.Button, interaction: discord.Interaction):
        await self.change_amount(interaction, lambda x: x+16)

    @discord.ui.button(label="макс.", style=discord.ButtonStyle.gray, row=2)
    async def max(self, btn: discord.ui.Button, interaction: discord.Interaction):    
        if self.mode:
            self.amount = int(getattr(self.player, BLOCK_DB_FIELD[BlockId.DIAMOND], 0))
        else:
            self.amount = int(getattr(self.player, BLOCK_DB_FIELD[self.res], 0))

        await self.change_amount(
            interaction,
            lambda _:
                int(getattr(self.player, BLOCK_DB_FIELD[BlockId.DIAMOND], 0)) if self.mode else
                int(getattr(self.player, BLOCK_DB_FIELD[self.res], 0))
        )

    @discord.ui.button(label="Продаж", style=discord.ButtonStyle.blurple, row=3)
    async def btn_mode(self, btn: discord.ui.Button, interaction: discord.Interaction):
        if not await self.check_author(interaction): return
    
        self.mode = not self.mode
        await self.refresh_message(interaction)

    @discord.ui.button(label="Обміняти", style=discord.ButtonStyle.green, row=3, emoji="🤝")
    async def btn_commit(self, btn: discord.ui.Button, interaction: discord.Interaction):
        if not await self.check_author(interaction): return

        async with SessionLocal() as cur:
            res = await cur.execute(select(MinePlayer).where(MinePlayer.uid == self.user_id))
            player = res.scalar_one_or_none()

            mid = await get_or_create_today_mid_rates(cur)

            rate = float(mid.get(self.res, 0.0))
            if rate == 0.0:
                await interaction.response.send_message(
                    "Курс для цього ресурсу недоступний.", ephemeral=True
                )
                return

            if self.mode:
                have_d = int(player.diamonds)
                if self.amount > have_d:
                    await interaction.response.send_message("Недостатньо діамантів!", ephemeral=True)
                    return
    
                bought = buy_resource(self.amount, rate)
                player.diamonds = have_d - self.amount
                setattr(player, BLOCK_DB_FIELD[self.res], int(getattr(player, BLOCK_DB_FIELD[self.res], 0)) + int(bought))
                await cur.commit()
                msg = f"Придбано **{bought}**×{BLOCK_EMOJI[self.res]} за **{self.amount}**💎"
            else:
                have = int(getattr(player, BLOCK_DB_FIELD[self.res], 0))
                if self.amount > have:
                    await interaction.response.send_message("Недостатньо ресурсу!", ephemeral=True)
                    return
    
                diamonds_gained = sell_resource(self.amount, rate)
                setattr(player, BLOCK_DB_FIELD[self.res], have - self.amount)
                player.diamonds = int(player.diamonds) + int(diamonds_gained)
                await cur.commit()
                msg = f"Продано **{self.amount}**×{BLOCK_EMOJI[self.res]} за **{diamonds_gained}**💎"

            self.player = player
            embed = interaction.message.embeds[0]
            embed.description = self.calc_preview() + f"\n\n✅ {msg}"
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Закрити", style=discord.ButtonStyle.red, row=3, emoji="❌")
    async def btn_close(self, btn: discord.ui.Button, interaction: discord.Interaction):
        if not await self.check_author(interaction): return
        await interaction.message.delete()


class Minecraft(commands.Cog):
    def __init__(self, client: bridge.Bot):
        self.client = client
        self.cfg = MineConfig()
        self.sessions: dict[int, MineSession] = {}


    @bridge.bridge_command(name="mine", usage=">mine", description="Шахта: ресурси, діаманти, няв")
    async def mine(self, ctx: bridge.BridgeApplicationContext):
        if not await checkperms(ctx):
            return
        
        async with SessionLocal() as cur:
            player = await get_or_create_player(cur, ctx.author.id)

            session = self.sessions.get(ctx.author.id)
            if session is not None and session.state is MineRunState.MINING:
                self.sessions.pop(ctx.author.id)
                if MineRunState.MINING:
                    session.gained_blocks.clear()
                    session.state = MineRunState.ABORTED
                    await apply_results(player, session, dead=False)
    
            await cur.commit()

        view = MineShopView(self, ctx.author.id, player)
        await ctx.respond("# Зберіть інвентар:", view=view)


    @bridge.bridge_command(
        name="mine-profile",
        usage=">profile (користувач)",
        description="Сховище котика",
        aliases=['profile', 'mp']
    )
    @bridge.bridge_option(type=discord.User, name = "user", description = "Користувач")
    async def mine_profile(self, ctx: bridge.BridgeApplicationContext, user: discord.User = None):
        if not await checkperms(ctx): return
        user = user or ctx.author

        async with SessionLocal() as cur:
            res = await cur.execute(select(MinePlayer).where(MinePlayer.uid == user.id))
            player = res.scalar_one_or_none()
            if player is None:
                player = await get_or_create_player(cur, user.id)
                await cur.commit()

        data: dict[BlockId, int] = {}
        for bid, column in BLOCK_DB_FIELD.items():
            data[bid] = int(getattr(player, column, 0))

        other = (
            data.get(BlockId.ANDESITE, 0)
            + data.get(BlockId.DIORITE, 0)
            + data.get(BlockId.GRANITE, 0)
            + data.get(BlockId.GRAVEL, 0)
        )

        deaths = int(getattr(player, "deaths", 0))
        totems = int(getattr(player, "totems", 0))
        total_blocks = int(getattr(player, "total_blocks_mined", 0))

        def line(*rows: str) -> str:
            return " ".join(rows)

        def prettify(amount: int, emoji: str) -> str:
            return f"**{amount}**x{emoji}"

        def get_data(bid: BlockId) -> tuple[int, str]:
            return data.get(bid, 0), BLOCK_EMOJI[bid]        

        data = [
            line(
                prettify(total_blocks, "⛏"),
                prettify(deaths, BLOCK_EMOJI[BlockId.LAVA]),
                prettify(totems, "🪆"),
            ),
            line(
                prettify(*get_data(BlockId.STONE)),
                prettify(other, BLOCK_EMOJI[BlockId.BEDROCK]),
                prettify(*get_data(BlockId.ANVIL)),
            ),
            line(
                prettify(*get_data(BlockId.COAL)),
                prettify(*get_data(BlockId.IRON)),
                prettify(*get_data(BlockId.GOLD)),
            ),
            line(
                prettify(*get_data(BlockId.COPPER)),
                prettify(*get_data(BlockId.LAPIS)),
                prettify(*get_data(BlockId.REDSTONE)),
            ),
            line(
                prettify(*get_data(BlockId.EMERALD)),
                prettify(*get_data(BlockId.DIAMOND)),
            ),
        ]

        await getembed(
            ctx, 
            title = f"Профіль {user.display_name}",
            description = "\n".join(data)
        )


    @bridge.bridge_command(name="mineboard", usage=">mineboard", description="Лідерборд шахтарів")
    async def mineboard(self, ctx: bridge.BridgeApplicationContext):
        if not await checkperms(ctx): return

        async with SessionLocal() as cur:
            res = await cur.execute(select(MinePlayer))
            players = list(res.scalars())

            mid = await get_or_create_today_mid_rates(cur)

            rows: list[tuple[int, int]] = []
            for p in players:
                try:
                    value = compute_player_potential_diamonds(p, mid)
                except Exception:
                    value = 0
                rows.append((int(p.uid), int(value)))

        rows.sort(key=lambda t: t[1], reverse=True)

        view = LeaderboardView(self, ctx.author.id, rows)
        await getembed(
            ctx,
            title="Топ за діамантами!",
            description=view.format_embed_description(),
            view=view
        )


    @bridge.bridge_command(
        name="mine-help",
        usage=">mine-help",
        description="Котогайд",
        aliases=["minehelp", "mh"]
    )
    async def mine_help(self, ctx: bridge.BridgeApplicationContext):
        if not await checkperms(ctx): return

        txt = [
            "# Загальна інформація:",
            f"**Міцність кирок**: {
                ', '.join(f'{PICKAXE_SPEC[pid].title}: **{PICKAXE_SPEC[pid].durability}**'
                for pid in PickaxeId)
            }",
            "За вимкненого **🐀X-RAY** котик отримує у **4** рази більше ресурсів",

            "# Ігровий процес",
            "Окрім кнопок руху, відображаються: ",
            "🗿 кількість добутих блоків | "
            f"🍎золоті яблука (лікують на **{self.cfg.apple_heal}** хп)",
            "↕️ висота | 📦 примусове повернення котика додому в коробочку",
            "🔨 міцність кирки | ❤️ хп (кількість тотемів безсмертя)",
        ]

        await getembed(ctx, description="\n".join(txt))


    @bridge.bridge_command(
        name="mine-trade",
        usage=">mine-trade",
        description="Обмін ресурсів",
        aliases=["minetrade", "mt"]
    )
    async def mine_trade(self, ctx: bridge.BridgeApplicationContext):
        if not await checkperms(ctx): return
    
        async with SessionLocal() as cur:
            player = await get_or_create_player(cur, ctx.author.id)
            rates = await get_or_create_today_mid_rates(cur)
            await cur.commit()

        view = TradeView(self, ctx.author.id, player, rates)
        await getembed(ctx, description=view.calc_preview(), view=view)



def setup(client: bridge.Bot):
    client.add_cog(Minecraft(client))
    print("\033[32m+ \033[31mMinecraft\033[37m")
