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
    return DBusUPowerKeyboardBacklight(hub, config)


class DBusUPowerKeyboardBacklight(KeyboardBacklight):
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._config = config
        self._maximum: int = 1
        self.stored: int = 1
        self._hub: LightControlHub = hub
        self._bus: MessageBus | None = None
        self._kbd_backlight: ProxyInterface | None = None

    async def get_current(self) -> int:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call start() first.")
        return int(await self._kbd_backlight.call_get_brightness())  # type: ignore[attr-defined]

    @property
    def maximum(self) -> int:
        return self._maximum

    async def set_absolute(self, value: int) -> None:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call start() first.")
        if 0 <= value <= self._maximum:
            await self._kbd_backlight.call_set_brightness(value)  # type: ignore[attr-defined]

    async def start(self) -> None:
        self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        with open(
            os.path.join(
                _MODULE_DIR, "dbus_upower_org.freedesktop.UPower.KbdBacklight.xml"
            ),
        ) as f:
            node_introspection = f.read()

        kbd_backlight_proxy = self._bus.get_proxy_object(
            "org.freedesktop.UPower",
            "/org/freedesktop/UPower/KbdBacklight",
            Node.parse(node_introspection),
        )
        self._kbd_backlight = kbd_backlight_proxy.get_interface(
            "org.freedesktop.UPower.KbdBacklight",
        )
        self._maximum = await self._kbd_backlight.call_get_max_brightness()  # type: ignore[attr-defined]
        self.stored = await self._kbd_backlight.call_get_brightness()  # type: ignore[attr-defined]
