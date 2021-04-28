# Native imports
import ctypes
import os, sys
import asyncio
from typing import Optional

# Third-party imports
import cv2
import numpy
import wizwalker
from wizwalker.utils import calculate_perfect_yaw

# Custom imports
from .utils import get_all_wiz_handles, XYZYaw, packaged_img
from .pixels import DeviceContext, match_image
from .keyboard import Keyboard
from .mouse import Mouse
from .window import Window
from .battle import Battle
from .card import Card

# rectangles defined as (x, y, width, height)
AREA_FRIENDS = (623, 63, 35, 250)
AREA_SPELLS = (245, 290, 370, 70)
AREA_CONFIRM = (355, 370, 100, 70)

SPELLS_FOLDER = "spells"
""" Default folder to look for spells in"""

IMAGE_FOLDER = ""
""" Default folder to look for images in."""

DEFAULT_MOUNT_SPEED = 1.4
""" Default mount speed (40%) """

user32 = ctypes.windll.user32

# Keep track of all clients
all_clients = []


async def unregister_all():
    """
    Properly unregisters all clients
    """
    print("Un-hooking all registered clients")
    for client in all_clients:
        await client.unregister()


class Client(DeviceContext, Keyboard, Window):
    """
    Main class for wizSDK.

    Example:
        .. code-block:: py

            # registers a new client
            player = client.register(name="My Bot")
            await player.activate_hooks()


    """

    def __init__(self, handle=None, silent_mouse=False):
        # Inherit all methods from Parent Classes
        super().__init__(handle)
        self.window_handle = handle
        self.logging = True
        self.name = None

        self._default_image_folder = IMAGE_FOLDER
        self.walker = None
        self.silent_mouse = silent_mouse
        self.mouse = None

        self._last_health = 99_999
        self._last_health_max = 99_999
        self._last_health_percentage = 99_999
        self._last_mana = 99_999
        self._last_mana_max = 99_999
        self._last_mana_percentage = 99_999
        self._level = 99_999
        self._gold = 99_999
        self._energy_max = 99_999
        self._fishing_experience = 99_999
        self._fishing_level = 99_999
        self._gardening_experience = 99_999
        self._gardening_level = 99_999

    @classmethod
    def register(cls, nth=0, name=None, handle=None, silent_mouse: bool = False):
        """
        Assigns the instance to a wizard101 window. (Required before using any other SDK methods)

        Args:
            nth (int, optional): Index of the wizard101 client to use (if there's more than one)
            name (str, optional): Name to prepend to the window title. Used for identifying which windows are controlled.
            silent_mouse: When enabled, moves the mouse without taking control of the actual cursor
        """
        client = cls()
        global all_clients

        client.silent_mouse = silent_mouse
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

        client.mouse = Mouse(client.window_handle, client.silent_mouse, client.walker)

        if name:
            client.set_name(name)

        return client

    async def activate_hooks(self, *hook_names):
        """
        Activate a number of hooks or pass None/no args to activate all (excluding special hooks like "mouseless_cursor_move")

        Args:
            hook_names: The hooks to activate

        Examples:
            .. code-block:: py

                # activates player_struct and player_stat_struct
                await activate_hooks("player_struct", "player_stat_struct")

                # activates all hooks (excluding special hooks like "mouseless_cursor_move")
                await activate_hooks()
        """
        hooks = hook_names
        if len(hook_names) == 0:
            hooks = tuple(
                [h for h in self.walker.get_hooks() if h != "mouseless_cursor_move"]
            )

        await self.walker.activate_hooks(*hooks)
        await self.send_key("d")
        await self.send_key("a")

    async def activate_all_hooks(self):
        """
        Activate all hooks (including special hooks like "mouseless_cursor_move")
        """
        await self.walker.activate_hooks()
        await self.send_key("d")
        await self.send_key("a")

    def set_name(self, name: str):
        """
        Sets the window title. Useful to identify which window the bot is running on
        Args:
            name (str): The text to prepend to the window title
        """
        self.name = name
        user32.SetWindowTextW(self.window_handle, f"[{name}] Wizard101")

    def log(self, message: str):
        """
        Debug log function. Useful to identify which client the log is coming from.
        Args:
            message (str): The message to log. ``[client-name]: message``
        """
        if self.logging:
            s = ""
            if self.name != None:
                s += f"[{self.name}] "
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
        """
        Properly unregister hooks and clean up possible ongoing asyncio tasks
        """
        user32.SetWindowTextW(self.window_handle, "Wizard101")
        self._anti_disconnect_task.cancel()
        await self.walker.close()
        return 1

    async def wait(self, seconds: float):
        """
        Alias for asyncio.sleep()

        Args:
            seconds (float): number of seconds to "sleep"
        """
        await asyncio.sleep(seconds)
        return self

    """
    STATE DETECTION
    """

    async def get_player_level(self) -> int:
        """
        Gets player level value from memory.

        Returns:
            The level of the player as an int
        """

        mem_level = await self.walker.level()
        self._level = mem_level

        return self._level

    async def get_gold(self) -> int:
        """
        Gets gold value from memory.

        Returns:
            The player's gold value as an int
        """

        mem_gold = await self.walker.gold()
        self._gold = mem_gold

        return self._gold

    async def get_health(self) -> int:
        """
        Gets health value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The health value of the player as an int
        """

        mem_health = await self.walker.health()
        if (mem_health != None) and (mem_health >= 0) and (mem_health < 20_000):
            self._last_health = mem_health

        return self._last_health

    async def get_health_max(self) -> int:
        """
        Gets maximum health value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The health value of the player as an int
        """

        mem_health_max = await self.walker.max_health()
        if (
            (mem_health_max != None)
            and (mem_health_max >= 0)
            and (mem_health_max < 20_000)
        ):
            self._last_health_max = mem_health_max

        return self._last_health_max

    async def get_health_percentage(self) -> int:
        """
        Gets health, and max health value from memory then divides them. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The health percentage of the player as an int rounded down to the first decimal.
        """

        mem_health = await self.walker.health()
        mem_health_max = await self.walker.max_health()
        if (mem_health != None) and (mem_health >= 0) and (mem_health < 20_000):
            health_percentage = (mem_health / mem_health_max) * 100
            self._last_health_percentage = round(health_percentage, 1)

        return self._last_health_percentage

    async def get_mana(self) -> int:
        """
        Gets mana value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The mana value of the player as an int
        """

        mem_mana = await self.walker.mana()
        if (mem_mana != None) and (mem_mana >= 0) and (mem_mana < 20_000):
            self._last_mana = mem_mana

        return self._last_mana

    async def get_mana_max(self) -> int:
        """
        Gets maximum mana value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The maximum mana value of the player as an int
        """

        mem_mana_max = await self.walker.max_mana()
        if (mem_mana_max != None) and (mem_mana_max >= 0) and (mem_mana_max < 20_000):
            self._last_mana_max = mem_mana_max

        return self._last_mana_max

    async def get_mana_percentage(self) -> int:
        """
        Gets health, and max health value from memory then divides them. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.

        Returns:
            The health percentage of the player as an int rounded down to the first decimal.
        """

        mem_mana = await self.walker.mana()
        mem_mana_max = await self.walker.max_mana()
        if (mem_mana != None) and (mem_mana >= 0) and (mem_mana < 20_000):
            mana_percentage = (mem_mana / mem_mana_max) * 100
            self._last_mana_percentage = round(mana_percentage, 1)

        return self._last_mana_percentage

    async def get_energy_max(self) -> int:
        """
        Gets players maximum energy value from memory.

        Returns:
            The player's maximum energy value as an int
        """

        mem_energy_max = await self.walker.energy()
        self._energy_max = mem_energy_max

        return self._energy_max

    async def get_fishing_experience(self) -> int:
        """
        Gets fishing experience value from memory.

        Returns:
            The player's fishing experience value as an int
        """

        mem_fishing_experience = await self.walker.fishing_experience()
        self._fishing_experience = mem_fishing_experience

        return self._fishing_experience

    async def get_fishing_level(self) -> int:
        """
        Gets fishing level value from memory.

        Returns:
            The player's fishing level value as an int
        """

        mem_fishing_level = await self.walker.fishing_level()
        self._fishing_level = mem_fishing_level

        return self._fishing_level

    async def get_gardening_level(self) -> int:
        """
        Gets gardening level value from memory.

        Returns:
            The player's gardening level value as an int
        """

        mem_gardening_level = await self.walker.gardening_level()
        self._gardening_level = mem_gardening_level

        return self._gardening_level

    async def get_gardening_experience(self) -> int:
        """
        Gets gardening experience value from memory.

        Returns:
            The player's gardening experience value as an int
        """

        mem_gardening_experience = await self.walker.gardening_experience()
        self._gardening_experience = mem_gardening_experience

        return self._gardening_experience

    def is_crown_shop(self) -> bool:
        """
        Detects if the crown shop is open by matching a red pixel in the "close" icon.

        Returns:
            bool: True if the menu is open / False otherwise
        """
        return self.pixel_matches_color((788, 53), (197, 40, 41), 50)

    def is_idle(self):
        """
        Detects if the player is idle (out of loading and not in battle) by matching pixels in the spellbook.

        Returns:
            bool: True if the player is idle / False otherwise
        """
        # spellbook_yellow = self.pixel_matches_color(
        #     (781, 551), (255, 251, 64), tolerance=30
        # )
        # spellbook_brown = self.pixel_matches_color(
        #     (728, 587), (79, 29, 29), tolerance=30
        # )

        # spellbook_gray = self.pixel_matches_color(
        #     (747, 538), (27, 47, 63), tolerance=30
        # )
        # print(spellbook_brown, spellbook_yellow, spellbook_gray)
        # return spellbook_brown and spellbook_yellow and spellbook_gray
        spell_book_area = self.get_image(region=(725, 555, 60, 60))
        return match_image(spell_book_area, packaged_img("spellbook.png"))

    def is_dialog_more(self):
        """
        Detects if the dialog (from NPCs etc.) is open by matching pixels in the "more" or "done" button.

        Returns:
            bool: True if the dialog menu is open / False otherwise
        """
        more_lower_right = self.pixel_matches_color((669, 611), (112, 32, 54), 15)
        more_top_left = self.pixel_matches_color((585, 609), (115, 32, 56), 15)
        return more_lower_right and more_top_left

    def is_health_low(self):
        """
        DEPRECATED:
        Detects if the player's health is low by matching a red pixel in the lower third of the globe.

        Returns:
            bool: is the health low
        """
        # Matches a pixel in the lower third of the health globe
        POSITION = (23, 563)
        COLOR = (126, 41, 3)
        TOLERANCE = 15
        return not self.pixel_matches_color(POSITION, COLOR, tolerance=TOLERANCE)

    def is_mana_low(self):
        """
        DEPRECATED:
        Detects if the player's mana is low by matching a blue pixel in the lower third of the globe.

        Returns:
            bool: is the mana low
        """
        # Matches a pixel in the lower third of the mana globe
        POSITION = (79, 591)
        COLOR = (66, 13, 83)
        TOLERANCE = 15
        return not self.pixel_matches_color(POSITION, COLOR, tolerance=TOLERANCE)

    def is_press_x(self):
        """
        Detects if the "press x" prompt is present by matching the "x" image.

        Returns:
            bool: "press X" has been found
        """
        x_area = self.get_image(region=(350, 540, 100, 20))
        found = match_image(x_area, packaged_img("x.png"))
        return found != False

    def get_confirm(self):
        """
        Detects if a "confirm" prompt is open (either from teleporting a friend or exiting an unfinished dungeon). It does this by matching a "confirm" image.

        Returns:
            tuple: (x, y) where the confirm button has been found
        """
        confirm_img = self.get_image(AREA_CONFIRM)
        found = match_image(confirm_img, packaged_img("confirm.png"), threshold=0.2)
        if found:
            x = found[0] + AREA_CONFIRM[0]
            y = found[1] + AREA_CONFIRM[1]
            found = (x, y)

        return found

    async def get_backpack_space_left(self) -> Optional[int]:
        """
        Gets the backpack space left. Will try to refresh the value by quickly opening and closing the backpack if necessary. Returns None if it wasn't able to get the value.

        Returns:
            space left in the backpack, None if it's not able to get the value.
        """

        refresh_triggered = False
        time_awaited = 0
        interval = 0.1
        space_used = await self.walker.backpack_space_used()
        while space_used == None and time_awaited < 1 and self.is_idle():
            if not refresh_triggered:
                self.log("Refreshing backpack space value")
                # Open and close character page to force memory update
                await self.send_key("b")
                await self.send_key("b")
                refresh_triggered = True

            # Wait
            await self.wait(interval)
            time_awaited += interval

            # re-try accessing the values
            space_used = await self.walker.backpack_space_used()

        if space_used == None:
            return None

        space_total = await self.walker.backpack_space_total()
        return space_total - space_used

    """
    ACTIONS BASED ON STATES
    """

    async def use_potion_if_needed(self, health=1000, mana=20):
        """
        Clicks on a potion if health or mana values drop below the settings

        Args:
            health: Health value threshold. Potion will be used if health value drops below
            mana:   Mana value threshold. Potion will be used if mana value drops below

        Returns:
            None
        """
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

    async def finish_loading(self, *, timeout=None) -> bool:
        """
        Waits for player to have gone through the loading screen.
        If this function is called too late and the player is already out of the loading screen, it will wait indefinitely.

        Args:
            timeout (optional): value in seconds to timeout if it hasn't finished yet. Defaults to None

        Returns:
            True if the function completed successfully, False if the function timed out.
        """

        async def _loading_coro():
            self.log("Awaiting loading")

            base_addr = lambda: self.walker._memory.process.read_int(
                self.walker._memory.player_struct_addr
            )
            player_struct = base_addr()

            # Wait for base_addr to change
            while player_struct == base_addr():
                await asyncio.sleep(0.2)

            await asyncio.sleep(2)

        # run it with the timeout
        try:
            await asyncio.wait_for(_loading_coro(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def go_through_dialog(self, times=1, *, timeout=None):
        # Wait for press X, or more/done button
        """
        Goes through the prompts of the dialog ("press x" or "more"/"continue"). Waits for "press x" or the dialog box before starting.

        Args:
            times (int): Defaults to 1
                The number of times to repeat. (When going through quests, you might need to set this to 2. There's one to hand in the quest, the second to get the next quest)
            timeout (optional): value in seconds to timeout if it hasn't finished yet. Defaults to None

        Returns:
            True if the function completed successfully, False if the function timed out.
        """

        async def _dialog_coro(times):
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

        # run it with the timeout
        try:
            await asyncio.wait_for(_dialog_coro(times), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def logout_and_in(self, confirm=False, *, confirm_timeout=None, timeout=None):
        """
        Logs the user out and then logs it in again.

        Args:
            confirm (bool, optional): Should the bot wait for a "confirm" prompt before continuing. Defaults to False
                Set to True if logging out durring a battle or to exit an unfinished dungeon.
            confirm_timeout: timeout argument for the ``click_confirm`` task. Defaults to None
            timeout: time in seconds before the function times out. Defaults to None

        Returns:
            True if the function completed successfully, False if the function timed out.
        """

        async def _coro():
            self.log("Logging out")
            await self.send_key("ESC", 0.1)
            await self.mouse.click(259, 506, delay=0.3)
            if confirm:
                await self.click_confirm(timeout=confirm_timeout)
            # wait for player select screen
            self.log("Wait for loading")
            while not (
                self.pixel_matches_color((361, 599), (133, 36, 62), tolerance=20)
            ):
                await self.wait(0.5)

            self.log("Logging back in")
            await self.mouse.click(395, 594)
            await self.finish_loading()
            if self.is_crown_shop():
                await self.wait(0.5)
                await self.send_key("ESC", 0.1)
                await self.send_key("ESC", 0.1)

        # run it with the timeout
        try:
            await asyncio.wait_for(_coro(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def press_x(self, *, timeout=None):
        """
        Waits for the "press x" prompt and sends the "X" key.

        Args:
            timeout (optional): value in seconds to timeout if it hasn't finished yet. Defaults to None

        Returns:
            True if the function completed successfully, False if the function timed out.
        """

        async def _press_x_coro():
            while not self.is_press_x():
                await self.wait(0.5)
            await self.send_key("X", 0.1)

        # run it with the timeout
        try:
            await asyncio.wait_for(_press_x_coro(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def click_confirm(self, *, timeout=None):
        """
        Waits for the "confirm" prompt, and clicks "confirm"

        Args:
            timeout (optional): value in seconds to timeout if it hasn't finished yet. Defaults to None

        Returns:
            True if the function completed successfully, False if the function timed out.
        """

        async def _confirm_coro():
            await self.wait(0.2)  #
            confirm = self.get_confirm()
            while not confirm:
                await self.wait(0.5)
                confirm = self.get_confirm()

            await self.mouse.click(*confirm, duration=0.2, delay=0.2)
            await self.wait(0.5)

        # run it with the timeout
        try:
            await asyncio.wait_for(_confirm_coro(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    """
    POSITION & MOVEMENT
    """

    async def get_quest_xyz(self) -> tuple:
        """
        Gets the X, Y, Z coordinates to the quest destination
        Requires the ``quest_struct`` hook to be activated

        Returns:
            tuple: (X, Y, Z) value of the quest goal location.
        """
        return await self.walker.quest_xyz()

    async def get_player_location(self) -> XYZYaw:
        """
        Fetches the player's XYZYaw location
        Requires the `player_struct` hook to be activated

        Returns:
            XYZYaw: (X, Y, Z, Yaw) tuple values of the player's position and direction.
        """
        xyz = await self.walker.xyz()
        yaw = await self.walker.yaw()
        return XYZYaw(x=xyz.x, y=xyz.y, z=xyz.z, yaw=yaw)

    async def teleport_to(self, location: XYZYaw):
        """
        Teleports to XYZYaw location
        Will return immediately if player movement is locked
        Requires the ``player_struct`` hook to be activated

        Args:
            location (XYZYaw): location to move to
        """
        if await self.walker.move_lock():
            return

        await self.walker.teleport(**location._asdict())
        await self.send_key("W", 0.1)

    async def walk_to(self, location: XYZYaw, mount_speed: float = -1):
        """
        Walks to XYZYaw location in a **straight** line only.
        Will _not_ work if there are obstacles in the way. Ideal for short distances
        Will return immediately if player movement is locked
        Requires the `player_struct` hook to be activated.


        Args:
            location (XYZYaw): The location to walk to.
                (Only the x and y value will actually be used)
            mount_speed (float): mount speed multiplier. Defaults to 1.4 (40% speed mount).
                Default can be changed by setting the ``wizsdk.client.DEFAULT_MOUNT_SPEED`` value
        """
        if mount_speed == -1:
            mount_speed = DEFAULT_MOUNT_SPEED

        if mount_speed:
            wizwalker.client.WIZARD_SPEED = 580 * mount_speed

        if await self.walker.move_lock():
            return

        await self.walker.goto(location.x, location.y)

    async def teleport_to_friend(self, match_img) -> bool:
        """
        Completes a set of actions to teleport to a friend.
        The friend must have the proper symbol next to it.
        The symbol must match the image passed as 'match_img'.

        Args:
            match_img: A string of the image file name, or a list of bytes returned by ``Client.get_image``
                The friend icon to find to select which friend to teleport to.

        Returns:
            bool: Whether the friend was found or not.
        """
        if not self.silent_mouse:
            self.set_active()
        # Check if friends already opened (and close it)
        friend_icon_area = self.get_image(region=(750, 35, 30, 30))
        while not match_image(
            friend_icon_area, packaged_img("friendlist.png"), threshold=0.05
        ):
            await self.send_key("F")
            await self.wait(0.2)
            friend_icon_area = self.get_image(region=(775, 30, 40, 40))

        # Open friend menu
        await self.send_key("F")
        await self.wait(0.2)

        # Find friend that matches friend match_img
        found = False
        last_page = False
        while (not found) and (not last_page):
            last_page = not self.pixel_matches_color((775, 328), (206, 44, 24), 50)
            found = self.locate_on_screen(match_img, region=AREA_FRIENDS, threshold=0.2)

            if (not found) and not last_page:
                await self.mouse.click(775, 328, duration=0.2)
                await self.mouse.move_to(775, 328, 0.3)

        if found is not False:
            _, y = found

            # Select friend
            await self.mouse.click(670, y, duration=0.2, delay=0.5)
            # Select port
            await self.mouse.click(450, 115, duration=0.2, delay=0.5)
            # Select yes
            await self.click_confirm()
            await self.wait(1)

            return True
        else:
            self.log("Friend could not be found")
            return False

    async def face_quest_destination(self) -> None:
        """
        Changes the player's yaw to be facing the quest destination.
        *Note:* depending on your location, this may differ from where your quest arrow is pointing to
        """
        xyz = await self.walker.xyz()
        quest_xyz = await self.walker.quest_xyz()
        yaw = calculate_perfect_yaw(xyz, quest_xyz)
        await self.walker.set_yaw(yaw)

    async def is_move_locked(self):
        """
        Detects if player is locked in combat

        Returns:
            bool: Whether player is move locked by combat or not.
        """

        move_lock = await self.walker.move_lock()
        if move_lock is True:
            return True
        else:
            return False

    """
    BATTLE ACTIONS & METHODS
    """

    def get_battle(self, name: str = None) -> Battle:
        """
        Fetch a ``battle`` associated with the client

        Args:
            name (str): Name of battle for logging purposes.

        Returns:
            Battle: object with battle methods linked to this client
        """
        return Battle(self, name, default_image_folder=self._default_image_folder)

    async def find_spell(
        self, spell_name: str, threshold: float = 0.12, ignore_gray_detection=False
    ) -> Card:
        """
        Searches spell area for an image matching ``spell_name``. An additional check to see if the spell is grayed out is done by default.

        Args:
            spell_name (str): The name of the spell as you have it saved in your spells image folder.
            threshold (float): How precise the match should be. The lower this value, the more exact the match will be.
            ignore_gray_detection (bool): should the gray detection be ignored. defaults to False

        Returns:
            int: x positions of spell if found, None otherwise
        """
        # Move into the window if the window isn't active
        if not self.silent_mouse and not self.is_active():
            self.set_active()
            await self.mouse.move_to(100, 100, duration=0.2)
        else:
            # Move mouse out of area to get a clear image
            await self.mouse.move_out(AREA_SPELLS)

        # Get screenshot of `spell_area`
        b_spell_area = self.get_image(AREA_SPELLS)

        extensions = [".png", ".jpg", "jpeg", ".bmp"]
        file_name = spell_name
        if not spell_name[-4:] in extensions:
            file_name += ".png"

        spell_path = os.path.join(SPELLS_FOLDER, file_name)

        res = match_image(b_spell_area, spell_path, threshold)

        if res:
            x, y = res
            # We're only interested in the x position
            offset_x = AREA_SPELLS[0]
            # a card width is 52 pixels, round to the nearest 1/2 card (26 pixels)
            adjusted_x = round(x / 26) * 26

            spell_pos = offset_x + adjusted_x

            if not ignore_gray_detection:
                # Check if the card is grayed out
                grayness = self.is_gray_rect(
                    (spell_pos - 10, 310, 20, 20), threshold=25
                )
                # print(file_name, grayness)
                if grayness < 25:
                    if grayness > 20:
                        print(f"{file_name} was found, but gray was detected.")
                        print("If this is an error, contact wizSDK dev.")
                    return None

            return Card(self, spell_name, spell_pos)
        else:
            return None

    async def pass_turn(self) -> None:
        """
        Clicks `pass` while in a battle
        """
        await self.mouse.click(254, 398, duration=0.2, delay=0.5)
        await self.wait(0.5)

    async def autocast(self, *spells: str, target=None):
        """
        Short-hand for ``find_spell`` followed by ``cast_spell``. Finds and casts spells. If 2 spells are provided, it will enchant spell 2 with spell 1. If target is provided, it will click the target. If any of the spells are not found, this function exits with False.

        Args:
            spells: provide up to 2 spell arguments
            target (int, optional): the target to cast the spell on. See ``Card.cast``

        Returns:
            True if all spells were found, False otherwise

        Examples:
            .. code-block:: py

                player = Client.register(name="Bot")
                battle = player.get_battle("Test")
                # Loop
                while await battle.loop():
                    # The following are all correct ways of using `autocast`
                    await player.autocast("epic", "bat", target=0)
                    await player.autocast("epic", "tempest")
                    await player.autocast("storm-blade", target=4)
        """

        if len(spells) == 0:
            print(f"Invalid call to `autocast`, expected 1-3 arguments, received none")
            return

        elif type(spells[-1]) == int:
            # The 3rd argument becomes the target
            target = spells[-1]
            spells = spells[:-1]

        found = [await self.find_spell(s) for s in spells[:2]]

        # Return False if some spells weren't found
        if sum([bool(c) for c in found]) != len(found):
            return False

        if len(found) == 2:
            to_cast = await found[0].enchant(found[1])
        else:
            to_cast = found[0]

        await to_cast.cast(target=target)
        return True


def register_clients(
    n_handles_expected: int,
    names: list = [],
    confirm_position: bool = False,
    silent_mouse: bool = False,
) -> list:
    """
    Register multiple clients, sorted from left to right, top to bottom.

    Args:
        n_handles_expected (int): the expected # of wiz windows opened. Use -1 for undetermined
        names (list): A list of strings that will serve as the names of the windows
        confirm_position (bool): prompt the user to confirm the windows order before continuing
        silent_mouse: When enabled, moves the mouse without taking control of the actual cursor

    Returns:
        client_list (list): A list populated with ``Client`` instances
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
        w = [
            Client.register(handle=handles[i], silent_mouse=silent_mouse)
            for i in range(n_handles)
        ]

        # Sort
        def sort_func(win):
            rect = win.get_rect()
            round_y = (rect[1] // 100) * 100
            return rect[0] + (round_y * 10)

        w.sort(key=sort_func)

        # Set names
        for i in range(len(w)):
            if i < len(names):
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
