# Native imports
import ctypes
import os, sys

# Third-party imports
import cv2
import numpy
import asyncio
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

SPELLS_FOLDER = "spells"
""" Default folder to look for spells in"""

DEFAULT_MOUNT_SPEED = 1.4
""" Default mount speed (40%) """

user32 = ctypes.windll.user32
__DIRNAME__ = os.path.dirname(__file__)
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

        self._last_health = 99_999
        self._last_mana = 99_999

    @classmethod
    def register(cls, nth=0, name=None, handle=None):
        """
        Assigns the instance to a wizard101 window. (Required before using any other SDK methods)
        
        Args:
            nth (int, optional): Index of the wizard101 client to use (if there's more than one)
            name (str, optional): Name to prepend to the window title. Used for identifying which windows are controlled.
            
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

        client.mouse = Mouse(client.window_handle)

        if name:
            client.set_name(name)

        return client

    async def activate_hooks(self, *hook_names):
        """
        Activate a number of hooks or pass None/no args to activate all
        
        Args:
            hook_names: The hooks to activate
        
        Examples:
            .. code-block:: py
            
                # activates player_struct and player_stat_struct
                await activate_hooks("player_struct", "player_stat_struct")
                
                # activates all hooks
                await activate_hooks()
        """
        await self.walker.activate_hooks(*hook_names)
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

    async def get_health(self) -> int:
        """
        Gets health value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.
        
        Returns:
            The health value of the player as an int
        """
        # refresh_triggered = False
        # mem_health = await self.walker.health()
        # while (not mem_health) or (mem_health < 0) or (mem_health > 20_000):
        #     # print(mem_health)
        #     if not refresh_triggered:
        #         # Open and close character page to force memory update
        #         self.log("Refreshing health value")
        #         await self.send_key("C", 0.1)
        #         await self.wait(0.8)
        #         await self.send_key("C", 0.1)
        #         refresh_triggered = True
        #     await self.wait(0.2)
        #     mem_health = await self.walker.health()

        # return int(mem_health)
        mem_health = await self.walker.health()
        if (mem_health) and (mem_health >= 0) and (mem_health < 20_000):
            self._last_health = mem_health

        return self._last_health

    async def get_mana(self) -> int:
        """
        Gets mana value from memory. For accurate values, only use after finishing a fight or after getting whisps. Returns 99,999 if the stats hook hasn't run.
        
        Returns:
            The mana value of the player as an int
        """
        # refresh_triggered = False
        # mem_mana = await self.walker.mana()
        # while (not mem_mana) or (mem_mana < 0) or (mem_mana > 20_000):
        #     if not refresh_triggered:
        #         self.log("Refreshing mana value")
        #         # Open and close character page to force memory update
        #         await self.send_key("C", 0.1)
        #         await self.send_key("C", 0.1)
        #         refresh_triggered = True
        #     await self.wait(0.2)
        #     mem_mana = await self.walker.mana()

        # return int(mem_mana)
        mem_mana = await self.walker.mana()
        if (mem_mana) and (mem_mana >= 0) and (mem_mana < 20_000):
            self._last_mana = mem_mana

        return self._last_mana

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
        spellbook_yellow = self.pixel_matches_color(
            (781, 551), (255, 251, 64), tolerance=30
        )
        spellbook_brown = self.pixel_matches_color(
            (728, 587), (79, 29, 29), tolerance=30
        )

        spellbook_gray = self.pixel_matches_color(
            (747, 538), (27, 47, 63), tolerance=30
        )
        return spellbook_brown and spellbook_yellow and spellbook_gray

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
        confirm_img = self.get_image(self._confirm_area)
        found = match_image(confirm_img, packaged_img("confirm.png"), threshold=0.2)
        if found:
            x = found[0] + self._confirm_area[0]
            y = found[1] + self._confirm_area[1]
            found = (x, y)

        return found

    async def get_backpack_space_left(self) -> optional[int]:
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

    async def finish_loading(self):
        """
        Waits for player to have gone through the loading screen.
        It first waits until it detects the loading screen, then waits until the loading screen is gone. 
        If this function is called too late and the player is already out of the loading screen, it will wait indefinitely.
        """
        self.log("Awaiting loading")
        while self.is_idle():
            await asyncio.sleep(0.2)

        while not (self.is_idle() or self.is_crown_shop()):
            await asyncio.sleep(0.5)

        await asyncio.sleep(1)

    async def go_through_dialog(self, times=1):
        # Wait for press X, or more/done button
        """
        Goes through the prompts of the dialog ("press x" or "more"/"continue"). Waits for "press x" or the dialog box before starting.
        
        Args:
            times (int): Defaults to 1
                The number of times to go through. (When going through quests, you might need to set this to 2. There's one to hand in the quest, the second to get the next quest)
        """
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
        """
        Logs the user out and then logs it in again.
        
        Args:
            confirm (bool, optional): Should the bot wait for a "confirm" prompt before continuing. Defaults to False
                Set to True if logging out durring a battle or to exit an unfinished dungeon.
        """
        self.log("Logging out")
        await self.send_key("ESC", 0.1)
        await self.mouse.click(259, 506, delay=0.3)
        if confirm:
            await self.click_confirm()
        # wait for player select screen
        self.log("Wait for loading")
        while not (self.pixel_matches_color((361, 599), (133, 36, 62), tolerance=20)):
            await self.wait(0.5)

        self.log("Logging back in")
        await self.mouse.click(395, 594)
        await self.finish_loading()
        if self.is_crown_shop():
            await self.wait(0.5)
            await self.send_key("ESC", 0.1)
            await self.send_key("ESC", 0.1)

    async def press_x(self):
        """
        Waits for the "press x" prompt and sends the "X" key.
        """
        while not self.is_press_x():
            await self.wait(0.5)
        await self.send_key("X", 0.1)

    async def click_confirm(self):
        """
        Waits for the "confirm" prompt, and clicks "confirm"
        """
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
        self.set_active()
        # Check if friends already opened (and close it)
        while self.pixel_matches_color((780, 364), (230, 0, 0), 40):
            await self.mouse.click(780, 364, duration=0.1)
            await self.wait(0.2)

        # Open friend menu
        await self.mouse.click(780, 50, duration=0.2)
        await self.wait(0.2)

        # Find friend that matches friend match_img
        found = False
        last_page = False
        while (not found) and (not last_page):
            print("finding")
            last_page = not self.pixel_matches_color((775, 328), (206, 44, 24), 50)
            found = self.locate_on_screen(
                match_img, region=self._friends_area, threshold=0.2
            )

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
        return Battle(self, name)

    async def find_spell(self, spell_name: str, threshold: float = 0.12) -> Card:
        """
        Searches spell area for an image matching ``spell_name``
        
        Args:
            spell_name (str): The name of the spell as you have it saved in your spells image folder.
            threshold (float): How precise the match should be. The lower this value, the more exact the match will be.
        
        Returns:
            int: x positions of spell if found, None otherwise
        """
        # Move into the window if the window isn't active
        if not self.is_active():
            self.set_active()
            await self.mouse.move_to(100, 100, duration=0.2)
        else:
            # Move mouse out of area to get a clear image
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
) -> list:
    """
    Register multiple clients, sorted from left to right, top to bottom.
    
    Args:
        n_handles_expected (int): the expected # of wiz windows opened. Use -1 for undetermined
        names (list): A list of strings that will serve as the names of the windows
        confirm_position (bool): prompt the user to confirm the windows order before continuing
    
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
