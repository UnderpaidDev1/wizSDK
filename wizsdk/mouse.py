# Native imports
import ctypes
from ctypes.wintypes import POINT
import time
import asyncio

# Custom imports
from wizsdk.window import Window, screen_size

# If the mouse is over a coordinate in FAILSAFE_POINTS and FAILSAFE is True, the FailSafeException is raised.
# The rest of the points are added to the FAILSAFE_POINTS list at the bottom of this file, after size() has been defined.
# The points are for the corners of the screen, but note that these points don't automatically change if the screen resolution changes.
FAILSAFE = True
FAILSAFE_POINTS = [(0, 0)]
MINIMUM_DURATION = 0.1
MINIMUM_SLEEP = 0.02


class FailSafeException(Exception):
    """
    Exception raised when the mouse is over (0, 0). Protactive measure to regain control of your mouse.
    """

    def __init__(
        self,
        message="Mouse fail-safe triggered from mouse moving to a corner of the screen.",
    ):
        self.message = message
        super().__init__(self.message)


def getPointOnLine(x1, y1, x2, y2, n):
    """
    Returns an (x, y) tuple of the point that has progressed a proportion ``n`` along the line defined by the two
    ``x1``, ``y1`` and ``x2``, ``y2`` coordinates.
    This function was copied from pytweening module, so that it can be called even if PyTweening is not installed.
    """
    x = ((x2 - x1) * n) + x1
    y = ((y2 - y1) * n) + y1
    return (x, y)


class Mouse(Window):
    """
    Class for controlling the computer's mouse.
    """

    _MOUSEEVENTF_MOVE = 0x0001  # mouse move
    _MOUSEEVENTF_LEFTDOWN = 0x0002  # left button down
    _MOUSEEVENTF_LEFTUP = 0x0004  # left button up
    _MOUSEEVENTF_RIGHTDOWN = 0x0008  # right button down
    _MOUSEEVENTF_RIGHTUP = 0x0010  # right button up
    _MOUSEEVENTF_MIDDLEDOWN = 0x0020  # middle button down
    _MOUSEEVENTF_MIDDLEUP = 0x0040  # middle button up
    _MOUSEEVENTF_WHEEL = 0x0800  # wheel button rolled
    _MOUSEEVENTF_ABSOLUTE = 0x8000  # absolute move
    _SM_CXSCREEN = 0
    _SM_CYSCREEN = 1

    def __init__(self, window_handle=None, silent_mode=False, walker=None):
        """
        Args:
            silent_mode: When enabled, moves the mouse without taking control of the actual cursor
            walker: A wizwalker client. It is required for silent mode
        """
        super().__init__(window_handle)
        # Window handle to which the mouse events will be relative to
        self.window_handle = window_handle
        self.walker = walker

        if silent_mode and walker == None:
            raise ValueError("A walker must be passed to Mouse to use silent mode")

        self.silent_mode = silent_mode
        self.silent_xpos = 0
        self.silent_ypos = 0

    def _do_event(self, flags, x_pos, y_pos, data, extra_info):
        """generate a mouse event"""
        if not self.silent_mode:
            x_calc = int(
                65536 * x_pos / ctypes.windll.user32.GetSystemMetrics(self._SM_CXSCREEN) + 1
            )
            y_calc = int(
                65536 * y_pos / ctypes.windll.user32.GetSystemMetrics(self._SM_CYSCREEN) + 1
            )
            return ctypes.windll.user32.mouse_event(flags, x_calc, y_calc, data, extra_info)
        else:
            raise RuntimeError("Mouse._do_event is not supported with silent mode enabled")

    def _get_button_value(self, button_name, button_up=False):
        """convert the name of the button into the corresponding value"""
        buttons = 0
        if button_name.find("right") >= 0:
            buttons = self._MOUSEEVENTF_RIGHTDOWN
        if button_name.find("left") >= 0:
            buttons = buttons + self._MOUSEEVENTF_LEFTDOWN
        if button_name.find("middle") >= 0:
            buttons = buttons + self._MOUSEEVENTF_MIDDLEDOWN
        if button_up:
            buttons = buttons << 1
        return buttons

    async def _set_position(self, pos):
        """
        Set the position of the mouse to the specified coordinates
        relative to the window
        """
        (x, y) = pos

        if not self.silent_mode:
            old_pos = self.get_position()
            x = x if (x != -1) else old_pos[0]
            y = y if (y != -1) else old_pos[1]
            self._do_event(self._MOUSEEVENTF_MOVE + self._MOUSEEVENTF_ABSOLUTE, x, y, 0, 0)
        else:
            point = POINT()
            point.x = x
            point.y = y
            ctypes.windll.user32.ClientToScreen(self.window_handle, ctypes.byref(point))
            self.silent_xpos = point.x
            self.silent_ypos = point.y
            await self.walker.set_mouse_position(self.silent_xpos, self.silent_ypos, convert_from_client=False)

    async def move_to(self, x, y, duration=0.5):
        """
        Move the mouse to the x, y coordinates relative to the window
        """
        # We need to get from (startx, starty) to (x, y)

        # Set the X, Y to be relative to the window position
        wX, wY, *_ = self.get_rect()
        x += wX
        y += wY

        startx, starty = self.get_position()
        x_offset = x - startx
        y_offset = y - starty

        width, height = screen_size()

        steps = [(x, y)]

        if duration > MINIMUM_DURATION:
            num_steps = max(width, height)
            sleep_amount = duration / num_steps

            if sleep_amount < MINIMUM_SLEEP:
                num_steps = int(duration / MINIMUM_SLEEP)
                sleep_amount = duration / num_steps

            steps = [
                getPointOnLine(startx, starty, x, y, (n / num_steps))
                for n in range(num_steps)
            ]
            steps.append((x, y))

        for _x, _y in steps:
            if len(steps) > 1:
                # A single step doesn't require tweening
                time.sleep(sleep_amount)

            _x = int(round(_x))
            _y = int(round(_y))

            # Failsafe check
            if not self.silent_mode and (_x, _y) not in FAILSAFE_POINTS:
                self.failSafeCheck()

            await self._set_position((_x, _y))

        # Failsafe check
        if not self.silent_mode and not (_x, _y) not in FAILSAFE_POINTS:
            self.failSafeCheck()

    def press_button(self, x=-1, y=-1, button="left", button_up=False):
        """push a button of the mouse"""
        self.move_to(x, y)
        if not self.silent_mode:
            self._do_event(self._get_button_value(button, button_up), 0, 0, 0, 0)
        else:
            pass # TODO: do something

    async def click(self, x=-1, y=-1, button="left", duration=None, delay=0.1):
        """Click at the specified placed"""
        # Set default duration
        if duration is None:
            if x == -1 and y == -1:
                duration = 0
            else:
                duration = 0.5

        # If position is not set, use current mouse position
        old_pos = self.get_position()
        x = x if (x != -1) else old_pos[0]
        y = y if (y != -1) else old_pos[1]
        await self.move_to(x, y, duration=duration)
        await asyncio.sleep(delay)
        if not self.silent_mode:
            self.set_active()
            self._do_event(
                self._get_button_value(button, False)
                + self._get_button_value(button, True),
                0,
                0,
                0,
                0,
            )
        else:
            await self.walker.click(x, y, right_click=button!="left", sleep_duration=delay)

    def double_click(self, pos=(-1, -1), button="left"):
        """Double click at the specifed placed"""
        for i in range(2):
            self.click(pos, button)

    def get_position(self):
        """get mouse position"""
        if not self.silent_mode:
            point = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
            return (point.x, point.y)
        else:
            return (self.silent_xpos, self.silent_ypos)

    def get_rel_position(self):
        """get mouse position relative to window"""
        if not self.silent_mode:
            wx, wy = self.get_rect()[:2]
            x, y = self.get_position()
            return (x - wx, y - wy)
        else:
            point = POINT()
            point.x = self.silent_xpos
            point.y = self.silent_ypos
            ctypes.windll.user32.ScreenToClient(self.window_handle, ctypes.byref(point))
            return (point.x, point.y)

    def in_rect(self, rect_area):
        """
        Returns true if the mouse is in the given region
        """
        x, y, w, h = rect_area
        wx, wy = self.get_rect()[:2]
        # Make the position of the rect relative to the window
        x += wx
        y += wy

        mouseX, mouseY = self.get_position()
        return mouseX > x and mouseX < (x + w) and mouseY > y and mouseY < (y + h)

    async def move_out(self, rect_area):
        """
        Move the mouse outside of the given rect
        If the mouse is already outside, return
        """
        x, y = self.get_rel_position()
        while self.in_rect(rect_area):
            # TODO find fastest way out of rect
            y -= 100
            await self.move_to(x, y, duration=0.2)

    def failSafeCheck(self):
        if not self.silent_mode and FAILSAFE and self.get_position() in FAILSAFE_POINTS:
            raise FailSafeException


if __name__ == "__main__":
    import asyncio

    async def main():
        mouse = Mouse()
        mouse._set_position((100, 100))
        await mouse.move_to(10, 100, duration=1)

    asyncio.run(main())
