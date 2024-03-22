import asyncio
import contextlib
import os
import platform

# Special Event class to use Events with an event loop in another thread
# https://stackoverflow.com/questions/33000200/asyncio-wait-for-event-from-other-thread
class Event_ts(asyncio.Event):
    def __init__(self, loop=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if loop is not None:
            self._loop = loop
        if self._loop is None:
            self._loop = asyncio.get_event_loop()

    def set(self):
        self._loop.call_soon_threadsafe(super().set)

    def clear(self):
        self._loop.call_soon_threadsafe(super().clear)

def generateAESIV(seq):
    iv = bytearray(16)
    iv[0] = seq & 0xff
    return iv

async def event_wait(evt, timeout):
    # suppress TimeoutError because we'll return False in case of timeout
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(evt.wait(), timeout)
    return evt.is_set()

def get_platform_type() -> str:
    """
    Gets the platform type.
    """
    if os.environ.get("P4A_BOOTSTRAP") is not None:
        return 'Android'

    if platform.system() == "Linux":
        return 'Linux'

    if platform.system() == "Darwin":
        return 'Darwin'

    if platform.system() == "Windows":
        return 'Windows'

    raise Exception(f"Unsupported platform: {platform.system()}")
