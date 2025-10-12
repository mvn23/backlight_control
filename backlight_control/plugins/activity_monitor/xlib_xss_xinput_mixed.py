from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import TYPE_CHECKING

from Xlib.display import Display

from ...activity_monitor import CONF_IDLE_DELAY, IDLE_DELAY, ActivityMonitor

if TYPE_CHECKING:
    from Xlib.xobject.drawable import Window

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    if CONF_IDLE_DELAY not in config:
        config[CONF_IDLE_DELAY] = IDLE_DELAY
    return XlibXssXinputMixedActivityMonitor(hub, config[CONF_IDLE_DELAY])


class XlibXssXinputMixedActivityMonitor(ActivityMonitor):
    _worker: asyncio.Task

    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._hub: LightControlHub = hub
        self._config: dict = config
        self._tpe: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    @property
    def config(self) -> dict:
        return self._config

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

    async def _monitor(self, loop: asyncio.AbstractEventLoop, root: Window) -> None:
        idle_ms = 0
        idle_delay_ms = self.config[CONF_IDLE_DELAY] * 1000

        while True:
            while root.display.pending_events():
                root.display.next_event()
            if not self._is_idle:
                await asyncio.sleep((idle_delay_ms - idle_ms) / 1000)
                idle_ms = root.screensaver_query_info().idle  # type: ignore[attr-defined]
                if idle_ms >= idle_delay_ms:
                    await self.trigger_idle()
            else:
                await loop.run_in_executor(self._tpe, root.display.next_event)
                await self.end_idle()
