# Native imports
import ctypes, os
from collections import namedtuple
import asyncio

user32 = ctypes.windll.user32

XYZYaw = namedtuple("XYZYaw", "x y z yaw")
"""
Used to store player location

:meta private:
"""


def run_threads(*coroutines, return_when=asyncio.FIRST_COMPLETED):
    """
    creates an asyncio event loop to run coroutines concurrently
    
    Args:
        coroutines: any amount of coroutines to run at the same time
        return_when: when to stop the threads and return: asyncio.FIRST_COMPLETED, asyncio.ALL_COMPLETED, or asyncio.FIRST_EXCEPTION

    """

    loop = asyncio.get_event_loop()
    job = asyncio.wait(coroutines, return_when=return_when)

    done, pending = loop.run_until_complete(job)

    # finish / cancel all tasks properly
    # https://stackoverflow.com/a/62443715/10751635
    for t in pending:
        t.cancel()

    while not all([t.done() for t in pending]):
        loop._run_once()


def get_all_wiz_handles() -> list:
    """
    Retrieves all window handles for windows that have the 
    'Wizard Graphical Client' class
    
    Returns:
        List of all the wizard101 device handles
    """
    target_class = "Wizard Graphical Client"

    handles = []

    # callback takes a window handle and an lparam and returns true/false on if we should keep going
    # iterating
    # https://docs.microsoft.com/en-us/previous-versions/windows/desktop/legacy/ms633498(v=vs.85)
    def callback(handle, _):
        class_name = ctypes.create_unicode_buffer(len(target_class))
        # win_title = ctypes.create_unicode_buffer(100)

        user32.GetClassNameW(handle, class_name, len(target_class) + 1)
        # user32.GetWindowTextW(handle, win_title, 101)

        if target_class == class_name.value:
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


def count_wiz_clients() -> int:
    """
    Returns the number of wizard101 clients detected
    
    Returns:
        Number of wizard101 clients detected
    """
    return len(get_all_wiz_handles())


async def finish_all_loading(*players):
    """
    Wait for all players passed in as arguments to have gone through the loading screen.
    """
    await asyncio.gather(*[player.finish_loading() for player in players])


def packaged_img(filename: str = ""):
    """
    Helper function to reference images packaged within the WizSDK module
    
    Returns:
        Full file path to the packaged image.
    """
    return os.path.dirname(__file__) + "/images/" + filename
