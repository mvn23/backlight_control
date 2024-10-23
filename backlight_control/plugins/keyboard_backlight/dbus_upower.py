from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
from dbus_fast.introspection import Node

from ...hub import (
    CONF_KEYBOARD_MIN_BRIGHTNESS,
    CONF_LUX_FOR_KEYBOARD_OFF,
    CONF_LUX_FOR_MAX_BRIGHTNESS,
    CONF_LUX_FOR_MIN_BRIGHTNESS,
)
from ...keyboard_backlight import KeyboardBacklight
from ...types import (
    KeyboardBacklightOperatingMode,
    LightControlHubActivityUpdate,
    LightControlHubKeyboardBacklightUpdate,
    LightControlHubLightSensorUpdate,
)

if TYPE_CHECKING:
    from dbus_fast.aio.proxy_object import ProxyInterface

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)

_MODULE_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_plugin(hub: LightControlHub, config: dict):
    return DBusUPowerKeyboardBacklight(hub, config)


class DBusUPowerKeyboardBacklight(KeyboardBacklight):
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self.config = config
        self.maximum: int = 1
        self.stored: int = 1
        self._hub: LightControlHub = hub
        self._bus: MessageBus | None = None
        self._kbd_backlight: ProxyInterface | None = None

    async def start(self) -> None:
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        with open(
            os.path.join(
                _MODULE_DIR, "dbus_upower_org.freedesktop.UPower.KbdBacklight.xml"
            ),
        ) as f:
            node_introspection = f.read()

        kbd_backlight_proxy = self.bus.get_proxy_object(
            "org.freedesktop.UPower",
            "/org/freedesktop/UPower/KbdBacklight",
            Node.parse(node_introspection),
        )
        self._kbd_backlight = kbd_backlight_proxy.get_interface(
            "org.freedesktop.UPower.KbdBacklight",
        )
        self.maximum = await self._kbd_backlight.call_get_max_brightness()  # type: ignore[attr-defined]
        self.stored = await self._kbd_backlight.call_get_brightness()  # type: ignore[attr-defined]

    async def on_idle_event(
        self, update: LightControlHubActivityUpdate
    ) -> LightControlHubKeyboardBacklightUpdate:
        if update.is_idle:
            await self.update_stored()
            await self.set_absolute(0)
            return LightControlHubKeyboardBacklightUpdate(
                mode=KeyboardBacklightOperatingMode.IDLE_OFF
            )
        else:
            if await self.get_current() == 0:
                await self.set_absolute(self.stored)
            return LightControlHubKeyboardBacklightUpdate(
                mode=KeyboardBacklightOperatingMode.ACTIVE_ON
            )

    async def on_lighting_event(
        self, update: LightControlHubLightSensorUpdate
    ) -> LightControlHubKeyboardBacklightUpdate:
        if update.value >= self.config[CONF_LUX_FOR_KEYBOARD_OFF]:
            await self.set_absolute(0)
            return LightControlHubKeyboardBacklightUpdate(
                mode=KeyboardBacklightOperatingMode.ACTIVE_OFF
            )

        if update.value <= self.config[CONF_LUX_FOR_MIN_BRIGHTNESS]:
            target_brightness = self.config[CONF_KEYBOARD_MIN_BRIGHTNESS]
        elif update.value >= self.config[CONF_LUX_FOR_MAX_BRIGHTNESS]:
            target_brightness = self.maximum
        else:
            target_brightness = int(
                self.config[CONF_KEYBOARD_MIN_BRIGHTNESS]
                + (
                    (update.value - self.config[CONF_LUX_FOR_MIN_BRIGHTNESS])
                    / (
                        self.config[CONF_LUX_FOR_MAX_BRIGHTNESS]
                        - self.config[CONF_LUX_FOR_MIN_BRIGHTNESS]
                    )
                )
                * (self.maximum - self.config[CONF_KEYBOARD_MIN_BRIGHTNESS])
            )

        _LOGGER.debug("Target keyboard brightness: %d", target_brightness)

        await self.set_absolute(target_brightness)
        return LightControlHubKeyboardBacklightUpdate(
            mode=KeyboardBacklightOperatingMode.ACTIVE_ON
        )

    async def update_stored(self) -> int:
        self.stored = await self.get_current()
        _LOGGER.debug("Stored brightness: %d", self.stored)
        return self.stored

    async def get_current(self) -> int:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call connect() first.")
        return int(await self._kbd_backlight.call_get_brightness())  # type: ignore[attr-defined]

    async def set_absolute(self, value: int) -> int:
        if not self._kbd_backlight:
            raise RuntimeError("Not connected to DBus. Call connect() first.")
        if 0 <= value <= self.maximum:
            await self._kbd_backlight.call_set_brightness(value)  # type: ignore[attr-defined]

        # Return current backlight level percentage
        return int(100 * value / self.maximum)
