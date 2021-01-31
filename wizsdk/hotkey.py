import asyncio
import ctypes
import re
import inspect

user32 = ctypes.windll.user32

from wizsdk.constants import keycode_map
from wizsdk.client import unregister_all


class HotkeyEvents:
    """
    Hotkey event manager class
    
    Examples:
        .. code-block:: py
        
            import wizsdk
            import asyncio

            # Initiate the event manager
            events = wizsdk.HotkeyEvents()

            # Add hotkeys
            def print_hello():
                print("Hello, world!")

            events.set_hotkey("ctrl + q", events.safe_quit) # safetly quit the program
            events.set_hotkey("SPACEBAR", print_hello)
            events.set_hotkey("Left mouse", lambda: print("click"))


            async def main_function():
                # main script goes here

            # run the two coroutines at the same time
            wizsdk.run_threads(events.listen(), main_function())

    
    """

    def __init__(self, debug=False):
        self._actions = {}
        self._pressed = {}
        self.debug = debug

    def _code_from_str(self, key):
        try:
            return keycode_map[key]
        except KeyError:
            # If this throws an error, it won't be catched
            # This is expected behavior
            return keycode_map[key.upper()]

    def _str_to_keycodes(self, trigger):
        # Split
        keys = re.split("\s*\+\s*", trigger)
        # Conver to keycodes
        return tuple([self._code_from_str(k) for k in keys])

    def _trigger_to_str(self, trigger):
        rev = {a: b for (b, a) in keycode_map.items()}
        return " + ".join([rev[k] for k in trigger])

    def set_hotkey(self, trigger: str, action):
        """
        Registers a hotkey
        
        Args:
            trigger: the hotkey(s) that will trigger the action. Separate multiple keys with a ``+``
            action: the function that will run when the hotkey is triggered. This can be a regular or an ``await``able function
        
        """
        if type(trigger) != str:
            print(f"Invalid trigger of type {type(trigger)}. Expecting type `str`")
            return False

        if not callable(action):
            print("Invalid param `action`. Param not callable")
            return False

        try:

            keys_as_codes = self._str_to_keycodes(trigger)

            self.debug and print(trigger, keys_as_codes)

            self._actions[keys_as_codes] = action
            # Start as True so that it's not executed on start
            self._pressed[keys_as_codes] = True
        except KeyError:
            print("One or more of the hot keys are invalid:", trigger)
            return False

    def unset_hotkey(self, trigger):
        """
        Removes a previously set hotkey
        
        Args:
            trigger: the same trigger used to register the hotkey
        """
        self._actions.pop(self._str_to_keycodes(trigger), None)
        print(self._actions.keys())

    async def listen(self):
        """
        starts an event loop that will listen for key presses and call actions triggered by the hotkeys.
        """
        while True:
            await asyncio.sleep(0.02)
            for (trigger, action) in self._actions.items():
                all_keys_pressed = all(
                    [user32.GetAsyncKeyState(keycode) for keycode in trigger]
                )
                was_pressed = self._pressed[trigger]
                if not was_pressed and all_keys_pressed:
                    self.debug and print(
                        f"hotkey {self._trigger_to_str(trigger)} triggered"
                    )
                    # Check if the action is a coroutine and needs to be awaited
                    if inspect.iscoroutinefunction(action):
                        await action()
                    else:
                        action()
                    # prevents double events by waiting for the keys to be released before being triggered again
                    self._pressed[trigger] = True

                elif not all_keys_pressed and was_pressed:
                    self._pressed[trigger] = False

    async def safe_quit(self):
        """
        Safetly quit the program by first un-hooking all clients.
        """
        await unregister_all()
        quit()


if __name__ == "__main__":
    from utils import run_threads

    # A few tests
    events = HotkeyEvents(debug=True)
    events.set_hotkey("alt + q", events.safe_quit)
    events.set_hotkey("Left mouse", lambda: print("click"))

    async def main_function():
        while True:
            await asyncio.sleep(1)
            print("waiting")

    run_threads(events.listen(), main_function())
