from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import TYPE_CHECKING

from Xlib.display import Display

from ...activity_monitor import ActivityMonitor
from ...hub import CONF_IDLE_DELAY
from ...types import LightControlHubActivityUpdate

if TYPE_CHECKING:
    from Xlib.xobject.drawable import Window

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    return XlibXssXinputMixedActivityMonitor(hub, config[CONF_IDLE_DELAY])


class XlibXssXinputMixedActivityMonitor(ActivityMonitor):
    _worker: asyncio.Task

    def __init__(self, hub: LightControlHub, delay: int) -> None:
        self._hub: LightControlHub = hub
        self.delay: int = delay
        self._is_idle: bool = False
        self._tpe: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    async def start(self) -> None:
        display = Display()

        xss_version_info = display.screensaver_query_version()
        _LOGGER.debug(
            "Found XScreensaver version: %d.%d",
            xss_version_info.major_version,
            xss_version_info.minor_version,
        )
        xinput_version_info = display.xinput_query_version()
        _LOGGER.debug(
            "Found XInput version: %d.%d",
            xinput_version_info.major_version,
            xinput_version_info.minor_version,
        )

        root = display.screen().root

        loop = asyncio.get_running_loop()
        self._worker = loop.create_task(self._monitor(loop, root))

    async def trigger_idle(self) -> None:
        self._is_idle = True
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=True))

    async def end_idle(self) -> None:
        self._is_idle = False
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=False))

    async def _monitor(self, loop: asyncio.AbstractEventLoop, root: Window) -> None:
        idle_ms = 0

        while True:
            while root.display.pending_events():
                root.display.next_event()
            if not self._is_idle:
                await asyncio.sleep((self.delay * 1000 - idle_ms) / 1000)
                idle_ms = root.screensaver_query_info().idle  # type: ignore[attr-defined]
                if idle_ms >= (self.delay * 1000):
                    await self.trigger_idle()
            else:
                await loop.run_in_executor(self._tpe, root.display.next_event)
                await self.end_idle()
