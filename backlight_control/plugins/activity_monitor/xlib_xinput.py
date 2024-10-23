from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
import logging
from typing import TYPE_CHECKING

from Xlib.display import Display
from Xlib.ext import xinput

from ...activity_monitor import ActivityMonitor
from ...hub import CONF_IDLE_DELAY
from ...types import LightControlHubActivityUpdate

if TYPE_CHECKING:
    from Xlib.xobject.drawable import Window

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    return XlibXinputActivityMonitor(hub, config[CONF_IDLE_DELAY])


class XlibXinputActivityMonitor(ActivityMonitor):
    _countdown: asyncio.Task
    _event_trigger: asyncio.Task
    _worker: asyncio.Task

    def __init__(self, hub: LightControlHub, delay: int) -> None:
        self._hub: LightControlHub = hub
        self.delay: int = delay
        self.display: Display = Display()
        self._is_idle: bool = False
        self._tpe: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    async def start(self) -> None:
        display = Display()

        version_info = display.xinput_query_version()
        _LOGGER.debug(
            "Found XInput version %d.%d",
            version_info.major_version,
            version_info.minor_version,
        )

        root = display.screen().root
        root.xinput_select_events(
            [
                (
                    xinput.AllDevices,
                    (
                        xinput.RawButtonPressMask
                        | xinput.KeyPressMask
                        | xinput.RawMotionMask
                    ),
                ),
            ]
        )

        loop = asyncio.get_running_loop()
        self._worker = loop.create_task(self.monitor(loop, root))

    async def trigger_idle(self) -> None:
        _LOGGER.debug("Entering idle state")
        self._is_idle = True
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=True))

    async def end_idle(self) -> None:
        _LOGGER.debug("Leaving idle state")
        self._is_idle = False
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=False))

    async def monitor(self, loop: asyncio.AbstractEventLoop, root: Window) -> None:
        while True:
            if self._is_idle:
                await self.end_idle()

            self._countdown = loop.create_task(self._start_countdown())
            await loop.run_in_executor(self._tpe, root.display.next_event)

            self._countdown.cancel()
            with suppress(asyncio.CancelledError):
                await self._countdown

    async def _start_countdown(self) -> None:
        await asyncio.sleep(self.delay)
        await self.trigger_idle()
