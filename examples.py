from sqlalchemy.ext.asyncio import create_async_engine
from discord.ui import Button, View
from discord import ButtonStyle, Interaction

async def removecase(self, ctx, number: int):
    pass

    button = Button(style=ButtonStyle.green, label="Так")
    view = View(disable_on_timeout=True)
    view.add_item(button)

    async def yes(inter: Interaction):
        nonlocal case, member
        pass

    button.callback = yes

    case = 123
    member = await self.client.get_or_fetch_user(case[1])

    pass

def syncrun():
    global engine
    engine = create_async_engine("sqlite+aiosqlite:///database.db")

with open("data.txt", "r") as f:
    data = f.read()


with open("data.txt", "w") as f:
    f.write("example")


with open("data.bin", "wb") as f:
    f.write(b"\x00\x01\x02")


class Player:
    @property
    def hp(self):
        return self._hp
    

class Example:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)


class A:
    pass

class B:
    pass

class C(A, B):
    pass


def gen():
    for i in range(3):
        yield i


def outer(x):
    def inner():
        return x
    
    return inner


import unittest

class TestMath(unittest.TestCase):
    def test_sum(self):
        self.assertEqual(2 + 2, 4)

unittest.main()


