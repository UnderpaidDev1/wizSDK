# Native imports
import ctypes, os
from collections import namedtuple
import asyncio

user32 = ctypes.windll.user32

"""
Used to store player location
"""
XYZYaw = namedtuple("XYZYaw", "x y z yaw")


def get_all_wiz_handles():
    """
    Retrieves all window handles for windows that have the 
    'Wizard Graphical Client' class
    """
    target_class = "Wizard Graphical Client"

    handles = []

    # callback takes a window handle and an lparam and returns true/false on if we should keep going
    # iterating
    # https://docs.microsoft.com/en-us/previous-versions/windows/desktop/legacy/ms633498(v=vs.85)
    def callback(handle, _):
        class_name = ctypes.create_unicode_buffer(len(target_class))
        win_title = ctypes.create_unicode_buffer(100)

        user32.GetClassNameW(handle, class_name, len(target_class) + 1)
        user32.GetWindowTextW(handle, win_title, 101)

        if (target_class == class_name.value) or ("Wizard101" in win_title.value):
            handles.append(handle)

        # iterate all windows
        return 1

    # https://docs.python.org/3/library/ctypes.html#callback-functions
    enumwindows_func_type = ctypes.WINFUNCTYPE(
        ctypes.c_bool,  # return type
        ctypes.c_int,  # arg1 type
        ctypes.POINTER(ctypes.c_int),  # arg2 type
    )

    # Transform callback into a form we can pass to the dll
    callback = enumwindows_func_type(callback)

    # EnumWindows takes a callback every iteration is passed to
    # and an lparam
    # https://docs.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-enumwindows
    user32.EnumWindows(callback, 0)

    return handles


def count_wiz_clients():
    """
    Returns the number of wizard101 clients detected
    """
    return len(get_all_wiz_handles())


async def finish_all_loading(*players):
    """
    Wait for all players passed in as arguments to have gone through the loading screen.
    """
    await asyncio.gather(*[player.finish_loading() for player in players])


def packaged_img(filename):
    """
    Helper function to reference images packaged with the WizSDK module
    """
    return os.path.dirname(__file__) + "/images/" + filename
