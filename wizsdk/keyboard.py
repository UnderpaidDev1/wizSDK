# Native imports
import ctypes
import ctypes.wintypes

# Third-party imports
import asyncio

# Custom imports
from wizwalker.windows.input import InputHandler

user32 = ctypes.windll.user32

keycode_map = {"TAB": 9, "ENTER": 13, "ALT": 18, "ESC": 27, "SPACE": 32}


class Keyboard(InputHandler):
    def __init__(self, window_handle):
        super().__init__(window_handle)
        self.window_handle = window_handle

    def type_key(self, char):
        code = None

        try:
            code = keycode_map[char]
        except KeyError:
            code = ord(char)

        user32.PostMessageW(self.window_handle, 0x102, code, 0)

    def type_keycode(self, code):
        user32.PostMessageW(self.window_handle, 0x102, code, 0)

    def type_string(self, string):
        for s in string:
            self.type_key(s)


if __name__ == "__main__":
    """ Some tests """
    from wizwalker.utils import get_all_wizard_handles

    try:
        window_handle = get_all_wizard_handles()[0]
    except IndexError:
        print("No running wizard windows")
        exit(0)

    async def say_hello():

        keyboard = Keyboard(window_handle)

        await keyboard.send_key("ENTER", 0.01)
        keyboard.type_string("Hello world!")
        await keyboard.send_key("ENTER", 0.1)

    asyncio.run(say_hello())
