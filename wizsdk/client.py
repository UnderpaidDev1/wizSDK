# Native imports
import ctypes
import os, sys

# Third-party imports
import cv2
import numpy
import asyncio
import wizwalker
from wizwalker.utils import calculate_perfect_yaw
from simple_chalk import chalk

# Custom imports
from .utils import get_all_wiz_handles, XYZYaw, packaged_img
from .pixels import DeviceContext, match_image
from .keyboard import Keyboard
from .mouse import Mouse
from .window import Window
from .battle import Battle
from .card import Card

SPELLS_FOLDER = "spells"

user32 = ctypes.windll.user32
__DIRNAME__ = os.path.dirname(__file__)
all_clients = []


async def unregister_all():
    print("Un-hooking all registered clients")
    for client in all_clients:
        await client.unregister()


class Client(DeviceContext, Keyboard, Window):
    def __init__(self, handle=None):
        # Inherit all methods from Parent Classes
        super().__init__(handle)
        self.window_handle = handle
        self.logging = True
        self.name = None
        # rectangles defined as (x, y, width, height)
        self._friends_area = (625, 65, 20, 240)
        self._spell_area = (245, 290, 370, 70)
        self._confirm_area = (355, 370, 100, 70)

        self.walker = None
        self.mouse = Mouse(handle)

        # Health and Mana (*only updated after fights)
        self.health = 9999
        self.mana = 999

    @classmethod
    def register(cls, nth=0, name=None, handle=None, hooks=[]):
        """
        Assigns the instance to a wizard101 window (Required before using any other API functions)
        """
        client = cls()
        global all_clients

        if handle:
            client.window_handle = handle
        else:
            handles = get_all_wiz_handles()

            if len(handles) == 0:
                client.log("No Wizard101 windows detected")
                return None

            handles.sort()
            # Assigns the one at index nth
            client.window_handle = handles[nth]

        # A window exists, add it to global variable
        all_clients.append(client)

        # Start `_anti_disconnect` task
        client._anti_disconnect_task = asyncio.create_task(client._anti_disconnect())

        client.walker = wizwalker.Client(client.window_handle)

        client.activate_hooks = client.walker.activate_hooks

        client.mouse = Mouse(client.window_handle)

        if name:
            client.set_name(name)

        return client

    def set_name(self, name):
        self.name = name
        user32.SetWindowTextW(self.window_handle, f"[{name}] Wizard101")

    def log(self, message):
        if self.logging:
            s = ""
            if self.name != None:
                s += chalk.magentaBright(f"[{self.name}] ")
            s += message
            print(s)
            sys.stdout.flush()

    async def _anti_disconnect(self):
        while True:
            # Wait 10 minute
            await asyncio.sleep(10 * 60)
            # Sent o key to stay awake
            await self.send_key("O", 0.1)
            await self.send_key("O", 0.1)

    async def unregister(self):
        """ Properly unregister hooks and more """
        user32.SetWindowTextW(self.window_handle, "Wizard101")
        self._anti_disconnect_task.cancel()
        await self.walker.close()
        return 1

    async def wait(self, s):
        """ Alias for asyncio.sleep() that return self for function chaining """
        await asyncio.sleep(s)
        return self

    """
    STATE DETECTION
    """

    async def get_health(self):
        refresh_triggered = False
        mem_health = await self.walker.health()
        while (not mem_health) or (mem_health < 0) or (mem_health > 20_000):
            if not refresh_triggered:
                # Open and close character page to force memory update
                self.log("Refreshing health value")
                await self.send_key("C", 0.1)
                await self.wait(0.8)
                await self.send_key("C", 0.1)
                refresh_triggered = True
            await self.wait(0.2)
            mem_health = await self.walker.health()

        return mem_health

    async def get_mana(self):
        refresh_triggered = False
        mem_mana = await self.walker.mana()
        while (not mem_mana) or (mem_mana < 0) or (mem_mana > 2_000):
            if not refresh_triggered:
                self.log("Refreshing mana value")
                # Open and close character page to force memory update
                await self.send_key("C", 0.1)
                await self.send_key("C", 0.1)
                refresh_triggered = True
            await self.wait(0.2)
            mem_mana = await self.walker.mana()

        return mem_mana

    def is_crown_shop(self):
        """ Matches a red pixel in the close icon of the opened crown shop menu """
        return self.pixel_matches_color((788, 53), (197, 40, 41), 50)

    def is_idle(self):
        """ Matches pixels in the spell book (only visible when not in battle) """
        spellbook_yellow = self.pixel_matches_color(
            (781, 551), (255, 251, 64), tolerance=40
        )
        spellbook_brown = self.pixel_matches_color(
            (728, 587), (79, 29, 29), tolerance=40
        )
        # print("brown", spellbook_brown)
        # print("yellow", spellbook_yellow)
        return spellbook_brown and spellbook_yellow

    def is_dialog_more(self):
        more_lower_right = self.pixel_matches_color((669, 611), (112, 32, 54), 15)
        more_top_left = self.pixel_matches_color((585, 609), (115, 32, 56), 15)
        return more_lower_right and more_top_left

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

    def is_press_x(self):
        x_area = self.get_image(region=(350, 540, 100, 20))
        found = match_image(x_area, packaged_img("x.png"))
        return found != False

    def get_confirm(self):
        confirm_img = self.get_image(self._confirm_area)
        found = match_image(confirm_img, packaged_img("confirm.png"), threshold=0.2)
        if found:
            x = found[0] + self._confirm_area[0]
            y = found[1] + self._confirm_area[1]
            found = (x, y)

        return found

    def locate_on_screen(self, match_img, region=None, threshold=0.1, debug=False):
        """
        Attempts to locate `match_img` in the Wizard101 window.
        Returns (x, y) tuple for center of match if found. False otherwise.
        pass a rect tuple `(x, y, width, height)` as the `region` argument to narrow 
        down the area to look for the image.
        Adjust `threshold` for the precision of the match (between 0 and 1, the lowest being more precise).
        Set `debug` to True for extra debug info
        
        """
        match = match_image(
            self.get_image(region=region), match_img, threshold, debug=debug
        )

        if not match or not region:
            return match

        region_x, region_y = region[:2]
        x, y = match
        return x + region_x, y + region_y

    """
    ACTIONS BASED ON STATES
    """

    async def use_potion_if_needed(self, health=1000, mana=20):
        h = await self.get_health()
        m = await self.get_mana()

        mana_low = m < mana
        health_low = h < health

        if mana_low:
            self.log(f"Mana is at {m}, using potion")
        if health_low:
            self.log(f"Health is at {h}, using potion")
        if mana_low or health_low:
            await self.mouse.click(160, 590, delay=0.2)

    async def finish_loading(self):
        self.log("Awaiting loading")
        while self.is_idle():
            await asyncio.sleep(0.2)

        while not (self.is_idle() or self.is_crown_shop()):
            await asyncio.sleep(0.5)

        await asyncio.sleep(1)

    async def go_through_dialog(self, times=1):
        # Wait for press X, or more/done button
        self.log("Going through dialog")
        while times >= 1:
            times -= 1
            while (not self.is_press_x()) and (not self.is_dialog_more()):
                await asyncio.sleep(0.5)

            if self.is_press_x():
                await self.send_key("X", 0.1)

            while not self.is_dialog_more():
                await asyncio.sleep(0.5)

            while self.is_dialog_more():
                await self.send_key("SPACEBAR", 0.1)
                await asyncio.sleep(0.1)

        await asyncio.sleep(1)

    async def logout_and_in(self, confirm=False):
        self.log("Logging out")
        await self.send_key("ESC", 0.1)
        await self.mouse.click(259, 506, delay=0.3)
        if confirm:
            await self.click_confirm()
        # wait for player select screen
        print("Wait for loading")
        while not (self.pixel_matches_color((361, 599), (133, 36, 62), tolerance=20)):
            await self.wait(0.5)

        print("Logging back in")
        await self.mouse.click(395, 594)
        await self.finish_loading()
        if self.is_crown_shop():
            await self.wait(0.5)
            await self.send_key("ESC", 0.1)
            await self.send_key("ESC", 0.1)

    async def press_x(self):
        while not self.is_press_x():
            await self.wait(0.5)
        await self.send_key("X", 0.1)

    async def click_confirm(self):
        await self.wait(0.2)  #
        confirm = self.get_confirm()
        while not confirm:
            await self.wait(0.5)
            confirm = self.get_confirm()

        await self.mouse.click(*confirm, duration=0.2, delay=0.2)
        await self.wait(0.5)

    """
    POSITION & MOVEMENT
    """

    async def get_quest_xyz(self):
        """
        Returns the X, Y, Z coordinates to the quest destination
        Requires the `quest_struct` hook to be activated
        """
        return await self.walker.quest_xyz()

    async def get_player_location(self):
        """
        Fetches the player's XYZYaw location
        Requires the `player_struct` hook to be activated
        """
        xyz = await self.walker.xyz()
        yaw = await self.walker.yaw()
        return XYZYaw(x=xyz.x, y=xyz.y, z=xyz.z, yaw=yaw)

    async def teleport_to(self, location: XYZYaw):
        """
        Teleports to XYZYaw location
        Will return immediately if player movement is locked
        Requires the `player_struct` hook to be activated
        """
        if await self.walker.move_lock():
            return

        await self.walker.teleport(**location._asdict())
        await self.send_key("W", 0.1)

    async def walk_to(self, location):
        """
        Walks to XYZYaw location in a **straight** line only.
        Will _not_ work if there are obstacles in the way. Ideal for short distances
        Will return immediately if player movement is locked
        Requires the `player_struct` hook to be activated
        """
        if await self.walker.move_lock():
            return

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
            await self.mouse.click(780, 364, duration=0.1)
            await self.wait(0.2)

        # Open friend menu
        await self.mouse.click(780, 50, duration=0.2)
        await self.wait(0.2)

        # Find friend that matches friend match_img
        friend_area_img = self.get_image(region=self._friends_area)

        found = match_image(friend_area_img, match_img, threshold=0.2)

        if found is not False:
            _, y = found
            offset_y = self._friends_area[1]

            # Select friend
            await self.mouse.click(670, offset_y + y, duration=0.2, delay=0.5)
            # Select port
            await self.mouse.click(450, 115, duration=0.2, delay=0.5)
            # Select yes
            await self.click_confirm()
            await self.wait(1)

            return self
        else:
            self.log("Friend could not be found")
            return False

    async def face_quest_destination(self):
        """
        Changes the player's yaw to be facing the quest destination.
        *Note:* depending on your location, this may differ from where your quest arrow is pointing to
        """
        xyz = await self.walker.xyz()
        quest_xyz = await self.walker.quest_xyz()
        yaw = calculate_perfect_yaw(xyz, quest_xyz)
        await self.walker.set_yaw(yaw)

    """
    BATTLE ACTIONS & METHODS
    """

    def get_battle(self, name=None) -> Battle:
        """
        Returns a `Battle` object linked to this client
        """
        return Battle(self, name)

    async def find_spell(self, spell_name, threshold=0.1) -> Card:
        """
        Searches spell area for an image matching `spell_name`
        Returns x positions of spell if found
        returns None if not found
        """
        # Move into the window if the window isn't active
        if not self.is_active():
            self.set_active()
            await self.mouse.move_to(100, 100, duration=0.2)
        # Move mouse out of area to get a clear image
        else:
            await self.mouse.move_out(self._spell_area)

        # Get screenshot of `spell_area`
        b_spell_area = self.get_image(self._spell_area)

        extensions = [".png", ".jpg", "jpeg", ".bmp"]
        file_name = spell_name
        if not spell_name[-4:] in extensions:
            file_name += ".png"

        spell_path = os.path.join(SPELLS_FOLDER, file_name)

        res = match_image(b_spell_area, spell_path, threshold, debug=False)

        if res:
            x, y = res
            # We're only interested in the x position
            offset_x = self._spell_area[0]
            # a card width is 52 pixels, round to the nearest 1/2 card (26 pixels)
            adjusted_x = round(x / 26) * 26

            spell_pos = offset_x + adjusted_x
            return Card(self, spell_name, spell_pos)
        else:
            return None

    async def pass_turn(self) -> None:
        """
        Clicks `pass` while in a battle
        """
        await self.mouse.click(254, 398, duration=0.2, delay=0.5)
        await self.wait(0.5)


def register_clients(
        n_handles_expected: int, names: list = [], confirm_position: bool = False
):
    """
    n_handles_expected: the expected # of wiz windows opened. Use -1 for undetermined
    names: A list of strings that will serve as the names of the windows
    """
    accepted = False
    while not accepted:
        handles = get_all_wiz_handles()
        n_handles = len(handles)

        if n_handles != n_handles_expected and n_handles_expected > 0:
            print(
                f"Invalid number of windows open. {n_handles_expected} required, {n_handles} detected."
            )
            os.system("pause")
            exit()
        else:
            print(f"{n_handles} windows detected")

        # Fill names array if necessary
        for i in range(n_handles - len(names)):
            names.append(None)

        # Register and order the windows from left to right, top to bottom
        w = [Client.register(handle=handles[i]) for i in range(n_handles)]

        # Sort
        def sort_func(win):
            rect = win.get_rect()
            round_y = (rect[1] // 100) * 100
            return rect[0] + (round_y * 10)

        w.sort(key=sort_func)

        # Set names
        for i in range(len(w)):
            w[i].set_name(names[i])

        # Confirm position
        if confirm_position:
            print("Is this order ok?")
            answer = input("[y] or n: ")
            if answer.lower().strip()[0] == "y" or answer == "":
                accepted = True
            else:
                print("Re-order the windows")
                os.system("pause")
        else:
            accepted = True

    # Returns the sorted clients in an array
    return w
