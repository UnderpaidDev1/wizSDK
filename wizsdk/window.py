import ctypes
from ctypes import WinDLL

user32 = ctypes.WinDLL("user32.dll")


def screen_size():
    """Returns the width and height of the screen as a two-integer tuple.
    Returns:
      (width, height) tuple of the screen size, in pixels.
    """
    return (
        ctypes.windll.user32.GetSystemMetrics(0),
        ctypes.windll.user32.GetSystemMetrics(1),
    )


class Window:
    """
    Base class for all classes in wizSDK. Keeps track of the wizard101 app window.
    """

    def __init__(self, handle=None):
        # If window_handle is None, Window represents the screen
        self.window_handle = handle

    def is_active(self) -> bool:
        """ Returns true if the window is focused """
        if self.window_handle:
            return self.window_handle == user32.GetForegroundWindow()
        else:
            # The "screen" is always active
            return True

    def set_active(self):
        """ Sets the window to active if it isn't already """
        if self.window_handle and not self.is_active():
            user32.SetForegroundWindow(self.window_handle)
        return self

    def get_rect(self) -> tuple:
        """
        Gets the area rectangle of the window (x, y, width, height) relative to the monitor position.
        
        Returns: 
            tuple (x, y, width, height) of the window
        """
        if self.window_handle:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(self.window_handle, ctypes.byref(rect))
            # Returns (x, y, w, h) tuple
            return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        else:
            # Return rect of screen
            return (0, 0, *screen_size())
