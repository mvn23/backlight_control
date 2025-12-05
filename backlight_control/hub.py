from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from .activity_monitor import get_and_verify_activity_plugin
from .keyboard_backlight import get_and_verify_keyboard_backlight_plugin
from .light_sensor import get_and_verify_light_sensor_plugin
from .types import (
    ActivityMonitorBackend,
    ConfigError,
    KeyboardBacklightBackend,
    KeyboardBacklightOperatingMode,
    LightControlHubActivityUpdate,
    LightControlHubLightSensorUpdate,
    LightSensorBackend,
)

if TYPE_CHECKING:
    from .activity_monitor import ActivityMonitor
    from .keyboard_backlight import KeyboardBacklight
    from .light_sensor import LightSensor


CONF_ACTIVITY_MONITOR = "activity_monitor"
CONF_KEYBOARD_BACKLIGHT = "keyboard_backlight"
CONF_LIGHT_SENSOR = "light_sensor"
CONF_TYPE = "type"

_LOGGER = logging.getLogger(__name__)


class LightControlHub:
    """backlight_control coordinator hub"""

    def __init__(self, config: dict) -> None:
        self.stopping = asyncio.Event()

        self._activity_monitor = self._get_activity_monitor_plugin_from_config(config)
        self._keyboard_backlight = self._get_keyboard_backlight_plugin_from_config(
            config
        )
        self._light_sensor = self._get_light_sensor_plugin_from_config(config)

    async def start(self) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._activity_monitor.start())
            tg.create_task(self._keyboard_backlight.start())
            tg.create_task(self._light_sensor.start())

        await self.stopping.wait()

    def stop(self) -> None:
        self.stopping.set()

        self._activity_monitor.stop()
        self._keyboard_backlight.stop()
        self._light_sensor.stop()

    async def activity_update(self, update: LightControlHubActivityUpdate) -> None:
        _LOGGER.debug("Got activity update: %s", update)
        kb_update = await self._keyboard_backlight.on_idle_event(update)
        if kb_update.mode == KeyboardBacklightOperatingMode.IDLE_OFF:
            await self._light_sensor.pause()
        else:
            await self._light_sensor.resume()

    async def light_sensor_update(
        self,
        update: LightControlHubLightSensorUpdate,
    ) -> None:
        _LOGGER.debug("Got light sensor update: %s", update)
        await self._keyboard_backlight.on_lighting_event(update)

    def _get_activity_monitor_plugin_from_config(
        self,
        config: dict,
    ) -> ActivityMonitor:
        """Return ActivityMonitor from config."""
        try:
            plugin = ActivityMonitorBackend(config[CONF_ACTIVITY_MONITOR][CONF_TYPE])
        except ValueError as e:
            raise ConfigError(
                "No valid activity_monitor plugin defined in config."
            ) from e

        _LOGGER.debug("Using activity_monitor plugin %s", plugin.value)
        return get_and_verify_activity_plugin(
            plugin,
            self,
            config[CONF_ACTIVITY_MONITOR],
        )

    def _get_keyboard_backlight_plugin_from_config(
        self,
        config: dict,
    ) -> KeyboardBacklight:
        """Return KeyboardBacklight from config."""
        try:
            plugin = KeyboardBacklightBackend(
                config[CONF_KEYBOARD_BACKLIGHT][CONF_TYPE]
            )
        except ValueError as e:
            raise ConfigError(
                "No valid keyboard_backlight plugin defined in config."
            ) from e

        _LOGGER.debug("Using keyboard_backlight plugin %s", plugin.value)
        return get_and_verify_keyboard_backlight_plugin(
            plugin,
            self,
            config[CONF_KEYBOARD_BACKLIGHT],
        )

    def _get_light_sensor_plugin_from_config(
        self,
        config: dict,
    ) -> LightSensor:
        """Return LightSensor from config."""
        if config.get(CONF_LIGHT_SENSOR) is None:
            _LOGGER.info("No light sensor defined in config, falling back to none.")
            return get_and_verify_light_sensor_plugin(LightSensorBackend.NONE, self, {})
        try:
            plugin = LightSensorBackend(config[CONF_LIGHT_SENSOR][CONF_TYPE])
        except ValueError as e:
            raise ConfigError("No valid light_sensor plugin defined in config.") from e

        _LOGGER.debug("Using light_sensor plugin %s", plugin.value)
        return get_and_verify_light_sensor_plugin(
            plugin,
            self,
            config[CONF_LIGHT_SENSOR],
        )
