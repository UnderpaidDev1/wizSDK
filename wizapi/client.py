import cv2
import time
import ctypes
from ctypes import WinDLL
import wizwalker
import asyncio
import numpy

from wizwalker.utils import XYZ
from .utils import get_all_wiz_handles, XYZYaw
from .pixels import DeviceContext, match_image
from .keyboard import Keyboard
from .mouse import Mouse


user32 = WinDLL("user32")
mouse = Mouse()

all_clients = []


async def unregister_all():
    print("Un-hooking all registered clients")
    for client in all_clients:
        await client.unregister_window()


class Client(DeviceContext, Keyboard):
    def __init__(self, handle=None):
        # Inherit all methods from Parent Classes
        super().__init__(handle)
        self.window_handle = handle
        self._spell_memory = {}

        # rectangles defined as (x, y, width, height)
        self._friends_area = (625, 65, 20, 240)
        self._spell_area = (245, 290, 370, 70)
        self._enemy_area = (68, 26, 650, 35)

        self.walker = None

    def register_window(self, nth=0, title=None, handle=None, hooks=[]):
        """
        Assigns the instance to a wizard101 window (Required before using any other API functions)
        """
        global all_clients
        all_clients.append(self)

        if handle:
            self.window_handle = handle
        else:
            handles = get_all_wiz_handles()
            handles.sort()
            # Assigns the one at index nth
            self.window_handle = handles[nth]

        self.walker = wizwalker.Client(self.window_handle)

        self.activate_hooks = self.walker.activate_hooks

        if title:
            user32.SetWindowTextW(self.window_handle, f"[{title}] Wizard101")
        return self

    async def unregister_window(self):
        """ Properly unregister hooks and more """
        user32.SetWindowTextW(self.window_handle, "Wizard101")
        await self.walker.close()
        return 1

    async def wait(self, s):
        """ Alias for asyncio.sleep() that return self for function chaining """
        await asyncio.sleep(s)
        return self

    def is_active(self):
        """ Returns true if the window is focused """
        return self.window_handle == user32.GetForegroundWindow()

    def set_active(self):
        """ Sets the window to active if it isn't already """
        if not self.is_active():
            user32.SetForegroundWindow(self.window_handle)
        return self

    async def move_mouse(self, x, y, speed=0.5):
        """ Moves to mouse to the position (x, y) relative to the window's position """
        wx, wy = self.get_rect()[:2]
        await mouse.move_to(wx + x, wy + y, duration=speed)
        return self

    async def click(self, x, y, delay=0.1, speed=0.5, button="left"):
        """ Moves the mouse to (x, y) relative to the window and presses the mouse button """
        self.set_active()
        await self.move_mouse(x, y, speed=speed)
        await self.wait(delay)

        await mouse.click(button=button)
        return self

    def is_health_low(self):
        # Matches a pixel in the lower third of the health globe
        POSITION = (23, 563)
        COLOR = (126, 41, 3)
        TOLERANCE = 15
        return not self.pixel_matches_color(POSITION, COLOR, tolerance=TOLERANCE)

    def is_mana_low(self):
        # Matches a pixel in the lower third of the mana globe
        POSITION = (79, 591)
        COLOR = (66, 13, 83)
        TOLERANCE = 15
        return not self.pixel_matches_color(POSITION, COLOR, tolerance=TOLERANCE)

    async def teleport_to(self, location):
        await self.walker.teleport(
            x=location.x, y=location.y, z=location.z, yaw=location.yaw
        )
        await self.send_key("W", 0.1)

    async def walk_to(self, location):
        await self.walker.goto(location.x, location.y)

    async def teleport_to_friend(self, match_img):
        """
        Completes a set of actions to teleport to a friend.
        The friend must have the proper symbol next to it
        symbol must match the image passed as 'match_img'

        """
        self.set_active()
        # Check if friends already opened (and close it)
        while self.pixel_matches_color((780, 364), (230, 0, 0), 40):
            await self.click(780, 364).wait(0.2)

        # Open friend menu
        await self.click(780, 50)

        # Find friend that matches friend match_img
        friend_area_img = self.get_image(region=self._friends_area)

        found = match_image(friend_area_img, match_img)

        if found is not False:
            x, y = found
            offset_x, offset_y = self._friends_area[:2]
            (
                await self.click(
                    offset_x + x + 50, offset_y + y, speed=0.2, delay=0.5
                ).click(  # Select friend
                    450, 115, speed=0.2, delay=0.5
                )  # Select port
                #  .click(415, 395, speed=.2, delay=.5)  # Select yes
            )
            return self
        else:
            print("Friend cound not be found")
            return False

    async def use_potion_if_needed(self):
        mana_low = self.is_mana_low()
        health_low = self.is_health_low()

        if mana_low:
            print("Mana is low, using potion")
        if health_low:
            print("Health is low, using potion")
        if mana_low or health_low:
            await self.click(160, 590, delay=0.2)

    async def pass_turn(self):
        await self.click(254, 398, delay=0.5)
        await self.move_mouse(200, 400)
        return self

    def is_turn_to_play(self):
        """ matches a yellow pixel in the 'flee' button """
        return self.pixel_matches_color((540, 399), (255, 255, 0), 20)

    def wait_for_next_turn(self):
        """ Wait for spell round to begin """
        while self.is_turn_to_play():
            self.wait(1)

        print("Spell round begins")

        """ Start detecting if it's our turn to play again """
        while not self.is_turn_to_play():
            self.wait(1)

        print("Our turn to play")
        return self

    async def turn_to_play(self):
        while not self.is_turn_to_play():
            await self.wait(0.5)

    async def end_of_round(self):
        """ Similar to wait_for_next_turn, but also detects if its the end of the battle """
        """ Wait for spell round to begin """
        while self.is_turn_to_play():
            await self.wait(1)

        """ Start detecting if it's our turn to play again """
        """ Or if it's the end of the battle """
        while not (self.is_turn_to_play() or self.is_idle()):
            await self.wait(1)
        return self

    def is_idle(self):
        """ Matches a pink pixel in the pet icon (only visible when not in battle) """
        spellbook_yellow = self.pixel_matches_color(
            (781, 551), (255, 251, 64), tolerance=20
        )
        spellbook_brown = self.pixel_matches_color(
            (728, 587), (79, 29, 29), tolerance=20
        )
        return spellbook_brown and spellbook_yellow

    async def select_target(self, target_pos):
        """ Clicks the target, based on position 1, 2, 3, or 4 """
        x = (174 * (target_pos - 1)) + 130
        y = 50
        await self.click(x, y, delay=0.2)
        return self

    def get_enemy_pos(self):
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
