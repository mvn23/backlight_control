from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from dbus_fast import BusType
from dbus_fast.aio import MessageBus, proxy_object
from dbus_fast.introspection import Node

from ...activity_monitor import CONF_IDLE_DELAY, ActivityMonitor

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)

_MODULE_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_plugin(hub: LightControlHub, config: dict) -> ActivityMonitor:
    return GnomeDBusActivityMonitor(hub, config)


class GnomeDBusActivityMonitor(ActivityMonitor):
    _active_watch: asyncio.Task | None = None
    _bus: MessageBus
    _idle_tasks: set
    _idle_watch: int | None = None
    _idle_monitor: proxy_object.ProxyInterface | None = None

    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._hub: LightControlHub = hub
        self._idle_tasks = set()
        config[CONF_IDLE_DELAY] = config[CONF_IDLE_DELAY] * 1000  # convert to ms
        self._config: dict = config

    @property
    def config(self) -> dict:
        """Return the config"""
        return self._config

    async def start(self) -> None:
        """Start the activity monitor"""
        _LOGGER.debug("Starting gnome_dbus ActivityMonitor")
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()

        with open(
            os.path.join(
                _MODULE_DIR,
                "gnome_dbus_org.gnome.Mutter.IdleMonitor.Core.xml",
            ),
            encoding="utf-8",
        ) as f:
            node_introspection = f.read()

        idle_monitor_proxy = self._bus.get_proxy_object(
            "org.gnome.Mutter.IdleMonitor",
            "/org/gnome/Mutter/IdleMonitor/Core",
            Node.parse(node_introspection),
        )
        self._idle_monitor = idle_monitor_proxy.get_interface(
            "org.gnome.Mutter.IdleMonitor",
        )
        self._idle_watch = await self._idle_monitor.call_add_idle_watch(  # type: ignore[attr-defined]
            self._config[CONF_IDLE_DELAY]
        )
        self._idle_monitor.on_watch_fired(self._watch_fired)  # type: ignore[attr-defined]

    def _watch_fired(self, signal_id: int) -> None:
        _LOGGER.debug("Signal fired: %d", signal_id)
        if signal_id == self._idle_watch:
            _LOGGER.debug("Entering Idle...")
            if self._idle_monitor is None:
                _LOGGER.error(
                    "No idle monitor found."
                    " This is a bug in the gnome_dbus activity monitor"
                )
                return
            self._active_watch = asyncio.create_task(
                self._idle_monitor.call_add_user_active_watch()  # type: ignore[attr-defined]
            )
            self._add_idle_task(self.trigger_idle())
        elif self._active_watch is None or signal_id == self._active_watch.result():
            _LOGGER.debug("Back in action!")
            self._active_watch = None
            self._add_idle_task(self.end_idle())

    def _add_idle_task(self, task: Coroutine) -> None:
        added_task: asyncio.Task = asyncio.create_task(task)
        self._idle_tasks.add(added_task)
        added_task.add_done_callback(self._idle_tasks.discard)
