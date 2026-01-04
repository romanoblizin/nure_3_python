from __future__ import annotations

from enum import Enum
from dataclasses import dataclass


class BlockId(Enum):
    COAL = "coal"
    IRON = "iron"
    GOLD = "gold"
    COPPER = "copper"
    LAPIS = "lapis"
    REDSTONE = "redstone"
    DIAMOND = "diamond"
    EMERALD = "emerald"

    STONE = "stone"
    GRAVEL = "gravel"
    DIORITE = "diorite"
    ANDESITE = "andesite"
    GRANITE = "granite"
    
    LAVA = "lava"
    LAVATOP = "lavatop"
    LAVABOTTOM = "lavabottom"
    LAVALEFT = "lavaleft"
    LAVARIGHT = "lavaright"
    LAVATOPLEFT = "lavatopleft"
    LAVATOPRIGHT = "lavatopright"
    LAVABOTTOMLEFT = "lavabottomleft"
    LAVABOTTOMRIGHT = "lavabottomright"

    ANVIL = "anvil"
    COBBLESTONE = "cobblestone"
    BEDROCK = "bedrock"
    DIRT = "dirt"
    AIR = "air"

    CAT = "cat"
    CATLAVA = "catlava"
    CATGRAVEL = "catgravel"
    CATANVIL = "catanvil"


class Biome(Enum):
    NORMAL = "normal"
    MOUNTAIN = "mountain"


class PickaxeId(Enum):
    WOODEN = "wooden"
    STONE = "stone"
    GOLDEN = "golden"
    IRON = "iron"
    DIAMOND = "diamond"
    NETHERITE = "netherite"
    GOD = "god"


class Direction(Enum):
    UP = "up"
    DOWN = "down"
    RIGHT = "right"


class MineRunState(Enum):
    SHOP = "shop"
    MINING = "mining"
    DEAD = "dead"
    SAVED = "saved"
    ABORTED = "aborted"


BLOCK_EMOJI: dict[BlockId, str] = {
    BlockId.COAL: "<:coal:982338497497170000>",
    BlockId.IRON: "<:iron:982338497715261470>",
    BlockId.GOLD: "<:gold:982338497664942131>",
    BlockId.COPPER: "<:copper:982338497451020378>",
    BlockId.LAPIS: "<:lapis:982338497874628669>",
    BlockId.REDSTONE: "<:redstone:982338497723641956>",
    BlockId.DIAMOND: "<:diamond:982338497547497472>",
    BlockId.EMERALD: "<:emerald:982338497652326430>",
    
    BlockId.STONE: "<:stone:982338497669124158>",
    BlockId.GRAVEL: "<:gravel:982338497652346940>",
    BlockId.DIORITE: "<:diorite:982338497677508628>",
    BlockId.ANDESITE: "<:andesite:982338496943501366>",
    BlockId.GRANITE: "<:granite:982338497568469022>",

    BlockId.LAVA: "<:lava:982338497803337758>",
    BlockId.LAVATOP: "<:lavaup:982559345483055214>",
    BlockId.LAVABOTTOM: "<:lavadown:982559340739301396>",
    BlockId.LAVALEFT: "<:lavaleft:982559341934690344>",
    BlockId.LAVARIGHT: "<:lavaright:1440781023800721418>",
    BlockId.LAVATOPLEFT: "<:lavaleftup:982559344413540352>",
    BlockId.LAVATOPRIGHT: "<:lavatopright:1440781007316844574>",
    BlockId.LAVABOTTOMLEFT: "<:lavaleftdown:982559343163629608>",
    BlockId.LAVABOTTOMRIGHT: "<:lavabottomright:1440780926778085406>",

    BlockId.ANVIL: "<:anvil:982364954713808986>",
    BlockId.COBBLESTONE: "<:cobblestone:982381518393585664>",
    BlockId.BEDROCK: "<:bedrock:982340502395437087>",
    BlockId.DIRT: "<:dirt:982338497794945074>",
    BlockId.AIR: "<:air:982350102851117077>",

    BlockId.CAT: "<:cat:982380641523994634>",
    BlockId.CATLAVA: "<:catlava:983782030787616879>",
    BlockId.CATGRAVEL: "<:catgravel:983544332973907988>",
    BlockId.CATANVIL: "<:catanvil:983545524747636786>",
}

BLOCK_DB_FIELD: dict[BlockId, str] = {
    BlockId.DIAMOND: "diamonds",
    BlockId.EMERALD: "emeralds",
    BlockId.STONE: "stone",
    BlockId.GOLD: "gold",
    BlockId.IRON: "iron",
    BlockId.LAPIS: "lapis",
    BlockId.REDSTONE: "redstone",
    BlockId.COPPER: "copper",
    BlockId.COAL: "coal",
    BlockId.GRAVEL: "gravel",
    BlockId.DIORITE: "diorite",
    BlockId.ANDESITE: "andesite",
    BlockId.GRANITE: "granite",
    BlockId.ANVIL: "anvils",
}

BLOCK_STR: dict[BlockId, str] = {
    BlockId.DIAMOND: "діамант",
    BlockId.EMERALD: "смарагд",
    BlockId.STONE: "каміння",
    BlockId.GOLD: "золото",
    BlockId.IRON: "залізо",
    BlockId.LAPIS: "лазурит",
    BlockId.REDSTONE: "редстоун",
    BlockId.COPPER: "мідь",
    BlockId.COAL: "вугілля",
    BlockId.GRAVEL: "гравій",
    BlockId.DIORITE: "діорит",
    BlockId.ANDESITE: "андезит",
    BlockId.GRANITE: "граніт",
    BlockId.ANVIL: "ковадло",
}

RESOURCE_BLOCKS: list[BlockId] = list(BLOCK_DB_FIELD.keys())

LAVA_BLOCKS: frozenset[BlockId] = {
    BlockId.LAVA,
    BlockId.LAVATOP,
    BlockId.LAVABOTTOM,
    BlockId.LAVALEFT,
    BlockId.LAVARIGHT,
    BlockId.LAVATOPLEFT,
    BlockId.LAVATOPRIGHT,
    BlockId.LAVABOTTOMLEFT,
    BlockId.LAVABOTTOMRIGHT,
}

@dataclass
class PickaxeSpec:
    title: str
    emoji: str
    durability: int
    cost: dict

PICKAXE_SPEC: dict[PickaxeId, PickaxeSpec] = {
    PickaxeId.WOODEN: PickaxeSpec("дерев'яна", "🪵", 32, {}),
    PickaxeId.STONE: PickaxeSpec("кам’яна", "🗿", 64, { BlockId.STONE: 8 }),
    PickaxeId.GOLDEN: PickaxeSpec("золота", "🥇", 48, { BlockId.GOLD: 3 }),
    PickaxeId.IRON: PickaxeSpec("залізна", "🦾", 128, { BlockId.IRON: 3 }),
    PickaxeId.DIAMOND: PickaxeSpec("діамантова", "💎", 256, { BlockId.DIAMOND: 3 }),
    PickaxeId.NETHERITE: PickaxeSpec("незеритова", "⚙️", 512, {
        BlockId.GOLD: 4,
        BlockId.IRON: 4,
        BlockId.DIAMOND: 4,
    }),
    PickaxeId.GOD: PickaxeSpec("божественна", "🌈", 999, {}),
}