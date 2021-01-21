from .client import Client, unregister_all, register_clients
from .utils import (
    get_all_wiz_handles,
    count_wiz_clients,
    finish_all_loading,
    XYZYaw,
)
from .card import Card
from .battle import Battle
from .mouse import Mouse
from .window import Window
from .keyboard import Keyboard
from .pixels import DeviceContext, match_image

# Clean up on exit
import ctypes
import ctypes.wintypes
import asyncio


def close_handler(dwCtrlType):
    asyncio.run(unregister_all())
    return False


handler_func_type = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)

transformed_callback = handler_func_type(close_handler)

# https://docs.microsoft.com/en-us/windows/console/setconsolectrlhandler
ctypes.windll.kernel32.SetConsoleCtrlHandler(transformed_callback, True)
