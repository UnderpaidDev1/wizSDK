# Native imports
import sys
from contextlib import suppress

# Third-party imports
import asyncio
from wizwalker import HookNotActive

# Custom imports
from .pixels import DeviceContext, match_image
from .card import Card
from .utils import packaged_img


class Battle(DeviceContext):
    """
    Battle class
    
    Example:
        .. code-block:: py
        
            # register the client
            p1 = Client.register(name="Bot")
            # Get a battle object from the client
            battle = p1.get_battle("Test")
            # Loop
            while await battle.loop():
                if battle.round_count == 1:
                    # pass on the first round
                    p1.pass_turn()
                else:
                    # Cast enchanted tempest
                    temp = await p1.find_spell("tempest")
                    epic = await p1.find_spell("epic")

                    if temp and epic:
                        e_temp = await epic.enchant(temp)
                        await e_temp.cast()
                    else:
                        await p1.pass_turn()
    """

    def __init__(self, client, name=None, default_image_folder=""):
        super().__init__(client.window_handle)
        self.client = client
        self._default_image_folder = default_image_folder

        self.logging = self.client.logging
        self.is_idle = self.client.is_idle
        self.name = name

        self._round_count = 1
        self._going_first = False
        self.enemy_first = False

        self.is_over = False

        self.in_progress = False

        # rectangles defined as (x, y, width, height)
        self._spell_area = (245, 290, 370, 70)
        self._enemy_area = (68, 26, 650, 50)
        self._ally_area = (140, 580, 650, 50)

    @property
    def round_count(self) -> int:
        """
        Current round of the fight. Starts at 1
        """
        return self._round_count

    @property
    def going_first(self) -> bool:
        """
        True if your team is going first, False if enemies are going first. Value is set once at the beginning of the fight.
        """
        return self._going_first

    async def loop(self):
        """
        Handles the looping logic for a battle. The loops exists when the battle ends.
        
        Examples:
            .. code-block:: py
                
                while await battle.loop():
                    print(battle.round_count)
                    print(battle.enemy_first)
                    print(battle.get_enemy_count())
        """

        if not self.in_progress and not self.is_over:
            await self._start()
            return True
        else:
            await self._next_turn()
            return not self.is_over

    def log(self, message):
        if self.logging:
            s = ""
            if self.name != None:
                s += f"[{self.name}] "
            s += message
            print(s)
            sys.stdout.flush()

    def print_round(self):
        self.log(f"----------- Battle round {self._round_count} -----------")

    def _is_turn(self) -> bool:
        """
        Returns if it's our turn to play
        by matching pixels in the `flee` button
        """
        flee_yellow = self.pixel_matches_color((550, 400), (255, 255, 0), tolerance=30)
        flee_brown = self.pixel_matches_color((578, 394), (124, 68, 0), tolerance=30)
        return flee_yellow and flee_brown

    async def _start(self) -> None:
        """
        Waits for the first round then signals to the class that the battle has started.
        used in the `loop()` method
        """
        while not self._is_turn():
            await asyncio.sleep(1)

        self.is_over = False
        self.in_progress = True

        self.enemy_first = self._is_enemy_first()
        self._going_first = not self.enemy_first

        who_is = "Enemy is" if self.enemy_first else "You are"

        self.log(">> Battle is starting")
        self.log("======================================")
        self.log(f"{who_is} going first")

        self.print_round()

    async def _next_turn(self) -> None:
        """
        Sleeps until next round or fight has ended
        Sets `is_over` to True if the fight has ended
        Increase the `_round_count` otherwise
        Used in the `loop()` method
        """
        while self._is_turn():
            await asyncio.sleep(1)

        while not self._is_turn() and not self.is_idle():
            await asyncio.sleep(1)

        if self.is_idle():
            self.log("Battle has finished")

            with suppress(HookNotActive):
                await self.client.get_mana()
                await self.client.get_health()

            await asyncio.sleep(0.5)
            self.is_over = True
            self.in_progress = False
        else:
            self._round_count += 1
            self.print_round()

    def get_enemy_positions(self):
        """
        Gets the indices of the enemies present
        
        Examples:
            .. code-block:: py
            
                # Register
                player = client.register(name="test")
                # Get the battle
                battle = player.get_battle()
                while await battle.loop():
                    enemies = battle.get_enemy_positions() # -> [0, 1]
                    print(len(enemies)) # -> 2
                    # Get the position of the first enemy in battle
                    first_enemy = enemies[0] # -> 0
                    # Get spell
                    firecat = await player.find_spell('firecat') # -> Card
                    if firecat:
                        # Cast at enemy position
                        await firecat.cast(target=first_enemy)
        """
        Y = 75
        COLOR = (207, 186, 135)
        enemies = []
        for i in range(4):
            X = (174 * (i)) + 203
            if self.pixel_matches_color((X, Y), COLOR, tolerance=30):
                enemies.append(i)

        return enemies

    def get_enemy_count(self):
        """
        Returns the number enemies in the fight
        """
        return len(self.get_enemy_positions())

    def find_enemy(self, enemy_image):
        """ 
        Attemps to find the position of an enemy that matches the image provided 
        returns 0, 1, 2, 3 if found otherwise returns False
        """
        found = self.locate_on_screen(
            enemy_image, region=self._enemy_area, threshold=0.2
        )

        if found:
            return round((found[0] - 60) / 170)

        return False

    def find_ally(self, ally_image):
        """ 
        Attemps to find the position of an ally the matches the image provided 
        returns 4, 5, 6, 7 if found otherwise returns False
        """

        found = self.locate_on_screen(ally_image, region=self._ally_area, threshold=0.2)

        if found:
            return 7 - round((found[0] - 100) / 170)

        return False

    def _is_enemy_first(self):
        turn_arrow_region = (230, 240, 80, 60)
        return bool(
            self.client.locate_on_screen(
                "enemy-first.png",
                region=turn_arrow_region,
                threshold=0.2,
                folder=packaged_img(),
            )
        )

