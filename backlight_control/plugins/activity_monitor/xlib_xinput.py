from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
import logging
from typing import TYPE_CHECKING

from Xlib.display import Display
from Xlib.ext import xinput

from ...activity_monitor import CONF_IDLE_DELAY, ActivityMonitor

if TYPE_CHECKING:
    from Xlib.xobject.drawable import Window

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    return XlibXinputActivityMonitor(hub, config)


class XlibXinputActivityMonitor(ActivityMonitor):
    _countdown: asyncio.Task
    _event_trigger: asyncio.Task
    _worker: asyncio.Task
    _root: Window

    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._hub: LightControlHub = hub
        self._config: dict = config
        self._tpe: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=1)

    @property
    def config(self) -> dict:
        return self._config

    async def start(self) -> None:
        display = Display()

        version_info = display.xinput_query_version()
        _LOGGER.debug(
            "Found XInput version %d.%d",
            version_info.major_version,
            version_info.minor_version,
        )

        self._root = display.screen().root
        self._root.xinput_select_events(  # type: ignore[attr-defined]
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

        def dc(fut):
            fut.result()

        loop = asyncio.get_running_loop()
        self._worker = loop.create_task(self.monitor(self._root))
        self._worker.add_done_callback(dc)

    async def monitor(self, root: Window) -> None:
        loop = asyncio.get_running_loop()
        while True:
            if self._is_idle:
                await self.end_idle()

            self._countdown = loop.create_task(self._start_countdown())
            await loop.run_in_executor(self._tpe, root.display.next_event)

            self._countdown.cancel()
            with suppress(asyncio.CancelledError):
                await self._countdown

    async def _start_countdown(self) -> None:
        await asyncio.sleep(self._config[CONF_IDLE_DELAY])
        await self.trigger_idle()
