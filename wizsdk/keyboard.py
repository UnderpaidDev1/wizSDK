# Native imports
import ctypes
import ctypes.wintypes

# Third-party imports
import asyncio

# Custom imports
from wizsdk.constants import keycode_map

user32 = ctypes.windll.user32


class Keyboard:
    """
    Keyboard class.
    Sends events directly to the client. Must pass in ``window_handle`` of the client to use.
    """

    def __init__(self, window_handle):
        # super().__init__(window_handle)
        self.window_handle = window_handle
        self.key_tasks = {}

    async def hold_key(self, key, seconds=0.1):
        """
        Hold down a key for an amount of time. The key is sent directly to the client, the client does not need to be in focus.
        
        Args:
            key (str): The key to hold down. 
                "TAB", "ENTER", "ALT", "ESC", "SPACE" and others are also accepted as special keys
            seconds (int, optional): duration to hold for
        """
        self.key_down(key)
        await asyncio.sleep(seconds)
        self.key_up(key)

    async def send_key(self, key, seconds=0.1):
        """
        Alias for ``hold_key``
        """
        await self.hold_key(key, seconds)

    def key_down(self, key):
        """
        Hold down a key. Call ``key_up`` to release.
        
        Args:
            key (str): The key to hold down
        """
        self.key_tasks[key] = asyncio.create_task(self._key_send_task(key))

    def key_up(self, key=None):
        """
        Release a key that has been pressed down
        
        Args:
            key (str, optional): The key to release
                If no key is specified, all keys will be released
        """
        if key:
            self._key_cancel_task(key)
        else:
            for k in self.key_tasks.keys():
                self.key_up(k)

    def type_key(self, char):
        """
        Sends a key to the client.
        This is a different event than ``send_key`` and is only useful for the chat window.
        
        Args:
            char: The character to type
                "TAB", "ENTER", "ALT", "ESC", "SPACE" and others are also accepted as special keys
        """
        code = None
        try:
            code = keycode_map[char]
        except KeyError:
            code = ord(char)

        user32.PostMessageW(self.window_handle, 0x102, code, 0)

    def type_string(self, string):
        """
        Type a string of letters directly to the window.
        
        Args:
            string: the text to type
        """
        for s in string:
            self.type_key(s)

    async def _key_send_task(self, key):
        while True:
            self._send_key_event(key, 0)
            await asyncio.sleep(0.1)

    def _key_cancel_task(self, key):
        if key in self.key_tasks.keys():
            self.key_tasks[key].cancel()

        self._send_key_event(key, 1)

    def _send_key_event(self, key, event):
        try:
            code = keycode_map[key.upper()]
            msg = 0x101 if event else 0x100
            # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendmessagew
            # https://docs.microsoft.com/en-us/windows/win32/inputdev/wm-keydown
            user32.PostMessageW(self.window_handle, msg, code, 0)
        except KeyError:
            print("Invalid key provided")


if __name__ == "__main__":
    """ Some tests """
    from wizwalker.utils import get_all_wizard_handles

    try:
        window_handle = get_all_wizard_handles()[0]
    except IndexError:
        print("No running wizard101 windows")
        exit(0)

    keyboard = Keyboard(window_handle)

    async def say_hello():
        keyboard.type_key("\r")
        await asyncio.sleep(0.2)
        keyboard.type_string("Hello world!\r")

    async def test():
        # Hold down 2 keys
        keyboard.key_down("D")
        keyboard.key_down("W")
        await asyncio.sleep(2)
        # Release 1
        keyboard.key_up("D")
        await asyncio.sleep(1)
        # Release all keys
        keyboard.key_up()
        # Hold s for .5 seconds
        await keyboard.hold_key("s", 0.5)

        # Wait and say hello!
        await asyncio.sleep(0.1)
        await say_hello()

    asyncio.run(test())
