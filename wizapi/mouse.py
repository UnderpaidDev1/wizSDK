import win32api, ctypes
import ctypes.wintypes

# If the mouse is over a coordinate in FAILSAFE_POINTS and FAILSAFE is True, the FailSafeException is raised.
# The rest of the points are added to the FAILSAFE_POINTS list at the bottom of this file, after size() has been defined.
# The points are for the corners of the screen, but note that these points don't automatically change if the screen resolution changes.
FAILSAFE = True
FAILSAFE_POINTS = [(0, 0)]
MINIMUM_DURATION = 0.1
MINIMUM_SLEEP = 0.05


class FailSafeException(Exception):
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


class Mouse:
    """It simulates the mouse"""

    MOUSEEVENTF_MOVE = 0x0001  # mouse move
    MOUSEEVENTF_LEFTDOWN = 0x0002  # left button down
    MOUSEEVENTF_LEFTUP = 0x0004  # left button up
    MOUSEEVENTF_RIGHTDOWN = 0x0008  # right button down
    MOUSEEVENTF_RIGHTUP = 0x0010  # right button up
    MOUSEEVENTF_MIDDLEDOWN = 0x0020  # middle button down
    MOUSEEVENTF_MIDDLEUP = 0x0040  # middle button up
    MOUSEEVENTF_WHEEL = 0x0800  # wheel button rolled
    MOUSEEVENTF_ABSOLUTE = 0x8000  # absolute move
    SM_CXSCREEN = 0
    SM_CYSCREEN = 1

    def _do_event(self, flags, x_pos, y_pos, data, extra_info):
        """generate a mouse event"""
        x_calc = int(
            65536 * x_pos / ctypes.windll.user32.GetSystemMetrics(self.SM_CXSCREEN) + 1
        )
        y_calc = int(
            65536 * y_pos / ctypes.windll.user32.GetSystemMetrics(self.SM_CYSCREEN) + 1
        )
        return ctypes.windll.user32.mouse_event(flags, x_calc, y_calc, data, extra_info)

    def _get_button_value(self, button_name, button_up=False):
        """convert the name of the button into the corresponding value"""
        buttons = 0
        if button_name.find("right") >= 0:
            buttons = self.MOUSEEVENTF_RIGHTDOWN
        if button_name.find("left") >= 0:
            buttons = buttons + self.MOUSEEVENTF_LEFTDOWN
        if button_name.find("middle") >= 0:
            buttons = buttons + self.MOUSEEVENTF_MIDDLEDOWN
        if button_up:
            buttons = buttons << 1
        return buttons

    def _set_position(self, pos):
        """move the mouse to the specified coordinates"""
        (x, y) = pos
        old_pos = self.get_position()
        x = x if (x != -1) else old_pos[0]
        y = y if (y != -1) else old_pos[1]
        self._do_event(self.MOUSEEVENTF_MOVE + self.MOUSEEVENTF_ABSOLUTE, x, y, 0, 0)

    def move_to(self, x, y, duration=0):
        # We need to get from (startx, starty) to (x, y)
        startx, starty = self.get_position()
        x_offset = x - startx
        y_offset = y - starty

        steps = [(x, y)]

        if duration > MINIMUM_DURATION:
            num_steps = max(x_offset, y_offset)
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
            if (_x, _y) not in FAILSAFE_POINTS:
                self.failSafeCheck()

            self._set_position((_x, _y))

        # Failsafe check
        if (_x, _y) not in FAILSAFE_POINTS:
            self.failSafeCheck()

    def press_button(self, pos=(-1, -1), button="left", button_up=False):
        """push a button of the mouse"""
        self.move_mouse(pos)
        self._do_event(self.get_button_value(button, button_up), 0, 0, 0, 0)

    def click(self, pos=(-1, -1), button="left"):
        """Click at the specified placed"""
        (x, y) = pos
        # If position is not set, use current mouse position
        old_pos = self.get_position()
        x = x if (x != -1) else old_pos[0]
        y = y if (y != -1) else old_pos[1]
        self.move_mouse(x, y)
        self._do_event(
            self._get_button_value(button, False)
            + self._get_button_value(button, True),
            0,
            0,
            0,
            0,
        )

    def double_click(self, pos=(-1, -1), button="left"):
        """Double click at the specifed placed"""
        for i in xrange(2):
            self.click(pos, button)

    def get_position(self):
        """get mouse position"""
        point = ctypes.wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)

    def failSafeCheck(self):
        if FAILSAFE and self.get_position() in FAILSAFE_POINTS:
            raise FailSafeException

