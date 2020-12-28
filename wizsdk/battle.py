# Native imports
import sys

# Third-party imports
import asyncio
from simple_chalk import chalk

# Custom imports
from .pixels import DeviceContext, match_image
from .card import Card
from .utils import packaged_img

# TODO


class Battle(DeviceContext):
    def __init__(self, client, name=None):
        super().__init__(client.window_handle)
        self.round_count = 1
        self.client = client
        self.logging = self.client.logging
        self.is_idle = self.client.is_idle
        self.name = name

        self.going_first = False
        self.enemy_first = False

        self.is_over = False
        self.in_progress = False

        # rectangles defined as (x, y, width, height)
        self._spell_area = (245, 290, 370, 70)
        self._enemy_area = (68, 26, 650, 50)
        self._ally_area = (140, 580, 650, 50)

    async def loop(self):
        """
        Takes care of the looping logic for a battle
        """
        if not self.in_progress and not self.is_over:
            await self.start()
            return True
        else:
            await self.next_turn()
            return not self.is_over

    def log(self, message):
        if self.logging:
            s = ""
            if self.name != None:
                s += chalk.blueBright(f"[{self.name}] ")
            s += message
            print(s)
            sys.stdout.flush()

    def print_round(self):
        self.log(f"----------- Battle round {self.round_count} -----------")

    def is_turn(self) -> bool:
        """
        Returns if it's our turn to play
        by matching pixels in the `flee` button
        """
        flee_yellow = self.pixel_matches_color((550, 400), (255, 255, 0), tolerance=30)
        flee_brown = self.pixel_matches_color((578, 394), (124, 68, 0), tolerance=30)
        return flee_yellow and flee_brown

    async def start(self) -> None:
        """
        Waits for the first round then signals to the class that the battle has started.
        used in the `loop()` method
        """
        while not self.is_turn():
            await asyncio.sleep(1)

        self.is_over = False
        self.in_progress = True

        self.enemy_first = self.is_enemy_first()
        self.going_first = not self.enemy_first

        self.log("Battle is starting")
        if self.enemy_first:
            self.log("Enemy is going first")
        else:
            self.log("You are going first")

        self.print_round()

    async def next_turn(self) -> None:
        """
        Sleeps until next round or fight has ended
        Sets `is_over` to True if the fight has ended
        Increase the `round_count` otherwise
        Used in the `loop()` method
        """
        while self.is_turn():
            await asyncio.sleep(1)

        while not self.is_turn() and not self.is_idle():
            await asyncio.sleep(1)

        if self.is_idle():
            self.log("Battle has finished")
            self.is_over = True
            self.in_progress = False
        else:
            self.round_count += 1
            self.print_round()

    def get_enemy_positions(self):
        """
        Returns a list of length 4 with 0, if no enemy is present at the 
        location, or 1 if an enemy is present
        """
        Y = 75
        COLOR = (207, 186, 135)
        enemies = []
        for i in range(4):
            X = (174 * (i)) + 203
            enemy_present = 0
            if self.pixel_matches_color((X, Y), COLOR, tolerance=30):
                enemy_present = 1
            enemies.append(enemy_present)

        return enemies

    def get_enemy_count(self):
        """
        Returns the number enemies in the fight
        """
        return sum(self.get_enemy_positions())

    def find_enemy(self, enemy_image):
        """ 
        Attemps to find the position of an enemy that matches the image provided 
        returns 0, 1, 2, 3 if found otherwise returns False
        """
        enemy_area = self.get_image(region=self._enemy_area)

        found = match_image(enemy_area, enemy_image, threshold=0.2)

        if found:
            return round((found[0] - 60) / 170)

        return False

    def find_ally(self, ally_image):
        """ 
        Attemps to find the position of an ally the matches the image provided 
        returns 4, 5, 6, 7 if found otherwise returns False
        """
        ally_area = self.get_image(region=self._ally_area)

        found = match_image(ally_area, ally_image, threshold=0.2)

        if found:
            return 7 - round((found[0] - 100) / 170)

        return False

    def is_enemy_first(self):
        turn_arrow_region = (230, 240, 80, 60)
        return bool(
            self.client.locate_on_screen(
                packaged_img("enemy-first.png"), region=turn_arrow_region
            )
        )

