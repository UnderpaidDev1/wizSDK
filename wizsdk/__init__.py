from .client import Client, unregister_all, XYZYaw, register_clients
from .utils import get_all_wiz_handles, count_wiz_clients, finish_all_loading
from .card import Card
from .battle import Battle
from .mouse import Mouse
from .keyboard import Keyboard

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
