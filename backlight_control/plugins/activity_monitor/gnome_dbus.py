from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Optional

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
from dbus_fast.introspection import Node

from ...activity_monitor import CONF_IDLE_DELAY, IDLE_DELAY, ActivityMonitor

if TYPE_CHECKING:
    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)

_MODULE_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_plugin(hub: LightControlHub, config: dict) -> ActivityMonitor:
    if CONF_IDLE_DELAY not in config:
        config[CONF_IDLE_DELAY] = IDLE_DELAY
    return GnomeDBusActivityMonitor(hub, config)


class GnomeDBusActivityMonitor(ActivityMonitor):

    _active_watch: Optional(int) = None
    _bus: MessageBus
    _idle_tasks: set = set()

    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._hub: LightControlHub = hub
        config[CONF_IDLE_DELAY] = config[CONF_IDLE_DELAY] * 1000  # convert to ms
        self._config: dict = config

    @property
    def config(self) -> dict:
        return self._config

    async def start(self) -> None:
        _LOGGER.debug("Starting gnome_dbus ActivityMonitor")
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()

        with open(
            os.path.join(
                _MODULE_DIR, "gnome_dbus_org.gnome.Mutter.IdleMonitor.Core.xml"
            ),
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
        self._idle_watch = await self._idle_monitor.call_add_idle_watch(
            self._config[CONF_IDLE_DELAY])
        self._idle_monitor.on_watch_fired(self._watch_fired)

    def _watch_fired(self, id: int) -> None:
        _LOGGER.debug(f"Signal fired: {id}")
        if id == self._idle_watch:
            _LOGGER.debug("Entering Idle...")
            self._active_watch = asyncio.create_task(
                self._idle_monitor.call_add_user_active_watch())
            self._add_idle_task(self.trigger_idle())
        elif id == self._active_watch.result():
            _LOGGER.debug("Back in action!")
            self._active_watch = None
            self._add_idle_task(self.end_idle())

    def _add_idle_task(self, task: asyncio.Awaitable) -> None:
        added_task = asyncio.create_task(task)
        self._idle_tasks.add(added_task)
        added_task.add_done_callback(self._idle_tasks.discard)