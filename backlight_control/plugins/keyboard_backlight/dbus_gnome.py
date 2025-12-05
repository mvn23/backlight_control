from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
from dbus_fast.introspection import Node

from ...keyboard_backlight import KeyboardBacklight

if TYPE_CHECKING:
    from dbus_fast.aio.proxy_object import ProxyInterface

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)

_MODULE_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_plugin(hub: LightControlHub, config: dict):
    return DBusGnomeKeyboardBacklight(hub, config)


class DBusGnomeKeyboardBacklight(KeyboardBacklight):
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._config = config
        self._maximum: int = 100
        self.stored: int = 1
        self._hub: LightControlHub = hub
        self._bus: MessageBus | None = None
        self._kbd_backlight: ProxyInterface | None = None

    async def get_current(self) -> int:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call start() first.")
        return int(await self._kbd_backlight.get_brightness())  # type: ignore[attr-defined]

    @property
    def maximum(self) -> int:
        return self._maximum

    async def set_absolute(self, value: int) -> None:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call start() first.")
        if 0 <= value <= self._maximum:
            await self._kbd_backlight.set_brightness(value)  # type: ignore[attr-defined]

    async def start(self) -> None:
        self._bus = await MessageBus(bus_type=BusType.SESSION).connect()

        with open(
            os.path.join(_MODULE_DIR, "dbus_gnome_org.gnome.SettingsDaemon.Power.xml"),
        ) as f:
            node_introspection = f.read()

        kbd_backlight_proxy = self._bus.get_proxy_object(
            "org.gnome.SettingsDaemon.Power",
            "/org/gnome/SettingsDaemon/Power",
            Node.parse(node_introspection),
        )
        self._kbd_backlight = kbd_backlight_proxy.get_interface(
            "org.gnome.SettingsDaemon.Power.Keyboard",
        )
        self.stored = await self._kbd_backlight.get_brightness()  # type: ignore[attr-defined]
