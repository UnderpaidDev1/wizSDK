import asyncio
from .pixels import DeviceContext, match_image
from .card import Card

# TODO
# Find enemy
# Find friend


class Battle(DeviceContext):
    def __init__(self, client, name=None):
        super().__init__(client.window_handle)
        self.round_count = 1
        self.client = client
        self.logging = self.client.logging
        self.is_idle = self.client.is_idle
        self.name = name

        self.is_over = False
        self.in_progress = False

        # rectangles defined as (x, y, width, height)
        self._spell_area = (245, 290, 370, 70)
        self._enemy_area = (68, 26, 650, 35)

    def log(self, message):
        if self.logging:
            s = ""
            if self.name != None:
                s += f"\033[94m[{self.name}]\033[0m "
            s += message
            print(s)

    def print_round(self):
        self.log(f"----------- Battle round {self.round_count} -----------")

    def is_turn(self) -> bool:
        """
        Returns if it's our turn to play
        by matching pixels in the `flee` button
        """
        flee_yellow = self.pixel_matches_color((550, 400), (255, 255, 0), tolerance=10)
        flee_brown = self.pixel_matches_color((578, 394), (124, 68, 0), tolerance=20)
        return flee_yellow and flee_brown

    async def start(self) -> None:
        while not self.is_turn():
            await asyncio.sleep(1)

        self.is_over = False
        self.in_progress = True
        self.log("Battle is starting")
        self.print_round()

    async def next_turn(self) -> None:
        """
        Sleeps until next round or fight has ended
        Sets `is_over` to True if the fight has ended
        Increase the `round_count` otherwise
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

    def get_enemy_pos(self):
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

