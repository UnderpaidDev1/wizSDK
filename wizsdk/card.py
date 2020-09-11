import asyncio
from .mouse import Mouse


mouse = Mouse()


class Card:
    def __init__(self, client, name, spell_x):
        self.client = client
        self.name = name
        self.spell_x = spell_x
        self.spell_y = 325

    def __str__(self):
        return f"{self.name} at ({self.spell_x}, {self.spell_y})"

    async def enchant(self, spell):
        """
        Enchants `spell` with self
        Returns enchanted spell
        """
        self.client.log(f"Enchanting {spell.name} with {self.name}")

        card_width = 52
        enchant_is_before = self.spell_x < spell.spell_x
        # click self
        await self.client.mouse.click(
            self.spell_x, self.spell_y, duration=0.3, delay=0.3
        )
        # click spell
        await self.client.mouse.click(
            spell.spell_x, spell.spell_y, duration=0.3, delay=0.3
        )
        # calculate new spell_x of enchanted spell

        # TODO
        # MORE TESTING NEEDED
        # THis seems to work, but I have no proof that it'll work for all senarios
        new_pos = spell.spell_x + (card_width / 2)
        if enchant_is_before:
            new_pos -= card_width

        new_name = f"{self.name}-{spell.name}"

        return Card(self.client, new_name, new_pos)

    async def cast(self, target=None):
        """
        Selects spell
        if target is specified, select target (0-3 for enemies, 4-7 for allies)
          0 1 2 3
           -----   
          7 6 5 4
        """
        self.client.log(f"Casting {self.name}")
        await self.client.mouse.click(
            self.spell_x, self.spell_y, duration=0.3, delay=0.3
        )

        if target != None:
            if target < 4:
                x = (174 * target) + 130
                y = 50
            elif target < 8:
                x = (174 * (7 - target)) + 160
                y = 590
            else:
                print(
                    f"Invalid value for target, expect int between 0 - 7, got {target}"
                )
                return False
            await self.client.mouse.click(x, y, duration=0.3, delay=0.3)

