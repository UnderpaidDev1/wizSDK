import cv2
import ctypes
from ctypes import WinDLL
import wizwalker
from wizwalker.utils import calculate_perfect_yaw
import asyncio
import numpy

from wizwalker.utils import XYZ
from .utils import get_all_wiz_handles, XYZYaw
from .pixels import DeviceContext, match_image
from .keyboard import Keyboard
from .mouse import Mouse
from .window import Window
from .battle import Battle


user32 = WinDLL("user32")

all_clients = []


async def unregister_all():
    print("Un-hooking all registered clients")
    for client in all_clients:
        await client.unregister_window()


class Client(DeviceContext, Keyboard, Window):
    def __init__(self, handle=None):
        # Inherit all methods from Parent Classes
        super().__init__(handle)
        self.window_handle = handle
        self.logging = True
        self.name = None
        # rectangles defined as (x, y, width, height)
        self._friends_area = (625, 65, 20, 240)

        self.walker = None
        self.mouse = Mouse(handle)

    def register_window(self, nth=0, name=None, handle=None, hooks=[]):
        """
        Assigns the instance to a wizard101 window (Required before using any other API functions)
        """
        global all_clients
        all_clients.append(self)

        if handle:
            self.window_handle = handle
        else:
            handles = get_all_wiz_handles()
            
            if len(handles) == 0:
                self.log('No w101 windows detected')
                return None
            
            handles.sort()
            # Assigns the one at index nth
            self.window_handle = handles[nth]

        self.walker = wizwalker.Client(self.window_handle)

        self.activate_hooks = self.walker.activate_hooks

        self.mouse = Mouse(self.window_handle)

        if name:
            self.name = name
            user32.SetWindowTextW(self.window_handle, f"[{name}] Wizard101")
        return self

    def log(self, message):
        if self.logging:
            s = ""
            if self.name != None:
                s += f"[{self.name}] "
            s += message
            print(s)
        
    async def unregister_window(self):
        """ Properly unregister hooks and more """
        user32.SetWindowTextW(self.window_handle, "Wizard101")
        await self.walker.close()
        return 1

    async def wait(self, s):
        """ Alias for asyncio.sleep() that return self for function chaining """
        await asyncio.sleep(s)
        return self

    """
    STATE DETECTION
    """
    def is_crown_shop(self):
        """ Matches a red pixel in the close icon of the opened crown shop menu """
        return self.pixel_matches_color((788, 53), (197, 40, 41), 10)
   
    def is_idle(self):
        """ Matches pixels in the spell book (only visible when not in battle) """
        spellbook_yellow = self.pixel_matches_color(
            (781, 551), (255, 251, 64), tolerance=20
        )
        spellbook_brown = self.pixel_matches_color(
            (728, 587), (79, 29, 29), tolerance=20
        )
        return spellbook_brown and spellbook_yellow
    
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

    """
    ACTIONS BASED ON STATES
    """
    async def use_potion_if_needed(self):
        mana_low = self.is_mana_low()
        health_low = self.is_health_low()

        if mana_low:
            self.log("Mana is low, using potion")
        if health_low:
            self.log("Health is low, using potion")
        if mana_low or health_low:
            await self.click(160, 590, delay=0.2)

    async def finish_loading(self):
        self.log("Awaiting loading")
        while self.is_idle():
            await asyncio.sleep(0.2)

        while not self.is_idle():
            await asyncio.sleep(0.5)

        await asyncio.sleep(1)
    """
    POSITION & MOVEMENT
    """
    async def get_quest_xyz(self):
        return await self.walker.quest_xyz()

    async def teleport_to(self, location):
        await self.walker.teleport(**location._asdict())
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
                    offset_x + x + 50, offset_y + y, duration=0.2, delay=0.5
                )
                .click(
                    450, 115, duration=0.2, delay=0.5
                )  # Select friend  # Select port
                .click(415, 395, duration=0.2, delay=0.5)  # Select yes
            )
            return self
        else:
            self.log("Friend cound not be found")
            return False

    async def face_quest_destination(self):
        xyz = await self.walker.xyz()
        quest_xyz = await self.walker.quest_xyz()
        yaw = calculate_perfect_yaw(xyz, quest_xyz)
        await self.walker.set_yaw(yaw)

    def get_battle(self, name=None):
        return Battle(self, name)

