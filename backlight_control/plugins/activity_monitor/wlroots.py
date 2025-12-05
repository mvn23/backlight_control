from __future__ import annotations

import asyncio
import logging
from queue import Queue
from threading import Event
from typing import TYPE_CHECKING

import wayland
from wayland.client import wayland_class

from ...activity_monitor import CONF_IDLE_DELAY, ActivityMonitor

if TYPE_CHECKING:
    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    return WlrootsActivityMonitor(hub, config)


@wayland_class("ext_idle_notification_v1")
class WlrootsIdleNotification(wayland.ext_idle_notification_v1):
    monitor: WlrootsActivityMonitor = None

    def on_idled(self):
        _LOGGER.debug("  Idle")
        self.monitor.idle_queue.put_nowait(True)

    def on_resumed(self):
        _LOGGER.debug("  Resume")
        self.monitor.idle_queue.put_nowait(False)


@wayland_class("wl_registry")
class WlrootsInput(wayland.wl_registry):
    idler: wayland.ext_idle_notifier_v1 | None
    monitor: WlrootsActivityMonitor | None
    notifications: list[WlrootsIdleNotification]
    seats: list[wayland.wl_seat]

    def __init__(self):
        """Initialize values"""
        super().__init__()
        self.seats = []
        self.idler = None
        self.notifications = []
        self.monitor = None

    def on_global(self, name, interface, version):
        _LOGGER.debug(f"{interface} (version {version})")
        if interface == "wl_seat":
            seat = self.bind(name, interface, version)
            self.seats.append(seat)
            self.maybe_subscribe()
        elif interface == "ext_idle_notifier_v1":
            self.idler = self.bind(name, interface, version)
            self.maybe_subscribe()
        else:
            return  # ignore all other interfaces

    def maybe_subscribe(self):
        _LOGGER.debug("Checking if we are ready to subscribe...")
        if self.seats and self.idler:
            _LOGGER.debug("...yes we are!")
            for seat in self.seats:
                notification = self.idler.get_input_idle_notification(
                    self.monitor.config[CONF_IDLE_DELAY] * 1000, seat
                )
                notification.monitor = self.monitor
                self.notifications.append(notification)
        else:
            _LOGGER.debug("...no we're not...")


class WlrootsActivityMonitor(ActivityMonitor):
    _worker: asyncio.Future | None
    _messageprocessor: asyncio.Task | None
    _stop_event: Event

    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self.idle_queue = Queue()
        self._hub: LightControlHub = hub
        self._config: dict = config
        self._worker = None
        self._messageprocessor = None
        self._stop_event = Event()

    @property
    def config(self) -> dict:
        return self._config

    async def start(self) -> None:
        loop = asyncio.get_running_loop()
        self._worker = loop.run_in_executor(None, self._monitor, self._stop_event)
        self._messageprocessor = loop.create_task(self._process())

    def stop(self) -> None:
        self._stop_event.set()

    def _monitor(self, stopping: Event) -> None:
        display = wayland.wl_display()
        registry = display.get_registry()
        registry.monitor = self

        while True:
            display.dispatch_timeout(0.1)
            if stopping.is_set():
                return

    async def _process(self):
        while True:
            _LOGGER.debug("Waiting for idle events")
            while self.idle_queue.empty():
                await asyncio.sleep(0.1)
            state = self.idle_queue.get()
            _LOGGER.debug(f"Got event: {state}")
            if state:
                await self.trigger_idle()
            else:
                await self.end_idle()
