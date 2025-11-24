import asyncio
import logging

from .activity_monitor import (
    CONF_IDLE_DELAY,
    IDLE_DELAY,
    get_and_verify_activity_plugin,
)
from .keyboard_backlight import (
    CONF_KEYBOARD_MIN_BRIGHTNESS,
    CONF_LUX_FOR_KEYBOARD_OFF,
    CONF_LUX_FOR_MAX_BRIGHTNESS,
    CONF_LUX_FOR_MIN_BRIGHTNESS,
    KEYBOARD_MIN_BRIGHTNESS,
    LUX_FOR_KEYBOARD_OFF,
    LUX_FOR_MAX_BRIGHTNESS,
    LUX_FOR_MIN_BRIGHTNESS,
    get_and_verify_keyboard_backlight_plugin,
)
from .light_sensor import get_and_verify_light_sensor_plugin
from .types import (
    ActivityMonitorBackend,
    KeyboardBacklightBackend,
    KeyboardBacklightOperatingMode,
    LightControlHubActivityUpdate,
    LightControlHubLightSensorUpdate,
    LightSensorBackend,
)

ACTIVITY_BACKEND = ActivityMonitorBackend.WAYLAND
KEYBOARD_BACKLIGHT_BACKEND = KeyboardBacklightBackend.XBACKLIGHT
LIGHT_SENSOR_BACKEND = LightSensorBackend.DBUS_SENSORPROXY

_LOGGER = logging.getLogger(__name__)


class LightControlHub:
    def __init__(self, config) -> None:
        self.stopping = asyncio.Event()

        self._activity_monitor = get_and_verify_activity_plugin(
            ACTIVITY_BACKEND,
            self,
            {CONF_IDLE_DELAY: IDLE_DELAY},
        )
        self._keyboard_backlight = get_and_verify_keyboard_backlight_plugin(
            KEYBOARD_BACKLIGHT_BACKEND,
            self,
            {
                CONF_KEYBOARD_MIN_BRIGHTNESS: KEYBOARD_MIN_BRIGHTNESS,
                CONF_LUX_FOR_KEYBOARD_OFF: LUX_FOR_KEYBOARD_OFF,
                CONF_LUX_FOR_MAX_BRIGHTNESS: LUX_FOR_MAX_BRIGHTNESS,
                CONF_LUX_FOR_MIN_BRIGHTNESS: LUX_FOR_MIN_BRIGHTNESS,
            },
        )
        self._light_sensor = get_and_verify_light_sensor_plugin(
            LIGHT_SENSOR_BACKEND,
            self,
            {},
        )

    async def start(self) -> None:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._activity_monitor.start())
            tg.create_task(self._keyboard_backlight.start())
            tg.create_task(self._light_sensor.start())

        await self.stopping.wait()

    def stop(self) -> None:
        self.stopping.set()

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
