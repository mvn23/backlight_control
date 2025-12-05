from __future__ import annotations

from abc import ABC, abstractmethod, abstractproperty
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from .types import (
    KeyboardBacklightBackend,
    KeyboardBacklightOperatingMode,
    LightControlHubActivityUpdate,
    LightControlHubKeyboardBacklightUpdate,
    LightControlHubLightSensorUpdate,
)

if TYPE_CHECKING:
    from .hub import LightControlHub

CONF_KEYBOARD_MIN_BRIGHTNESS = "keyboard_min_brightness"
CONF_LUX_FOR_KEYBOARD_OFF = "lux_for_keyboard_off"
CONF_LUX_FOR_MAX_BRIGHTNESS = "lux_for_max_brightness"
CONF_LUX_FOR_MIN_BRIGHTNESS = "lux_for_min_brightness"
DEFAULT_KEYBOARD_MIN_BRIGHTNESS = 10
DEFAULT_LUX_FOR_KEYBOARD_OFF = 400
DEFAULT_LUX_FOR_MAX_BRIGHTNESS = 300
DEFAULT_LUX_FOR_MIN_BRIGHTNESS = 10

_LOGGER = logging.getLogger(__name__)


class KeyboardBacklight(ABC):
    stored: int = 0
    _config: dict

    @abstractmethod
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        raise NotImplementedError

    @property
    def config(self) -> dict:
        return self._config

    @abstractmethod
    async def get_current(self) -> int:
        raise NotImplementedError

    @abstractproperty
    def maximum(self) -> int:
        raise NotImplementedError

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

    @abstractmethod
    async def set_absolute(self, value: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        return

    async def update_stored(self) -> int:
        self.stored = await self.get_current()
        _LOGGER.debug("Stored brightness: %d", self.stored)
        return self.stored


def get_and_verify_keyboard_backlight_plugin(
    backend: KeyboardBacklightBackend,
    hub: LightControlHub,
    config: dict,
) -> KeyboardBacklight:
    try:
        module = import_module(
            f".{backend.value}", "backlight_control.plugins.keyboard_backlight"
        )
    except ImportError as e:
        raise ImportError(f"Failed to import keyboard backlight {backend.value}") from e

    config = _parse_config(config)
    try:
        instance = module.get_plugin(hub, config)
    except AttributeError as e:
        raise AttributeError(
            f"Module {backend.value} does not define a `get_plugin` function"
        ) from e

    if not isinstance(instance, KeyboardBacklight):
        raise RuntimeError(
            f"Instance of {instance.__class__.__name__} does not inherit from"
            " KeyboardBacklight",
        )

    return instance


def _parse_config(config: dict) -> dict:
    """Make sure the config is complete."""
    config[CONF_KEYBOARD_MIN_BRIGHTNESS] = config.get(
        CONF_KEYBOARD_MIN_BRIGHTNESS, DEFAULT_KEYBOARD_MIN_BRIGHTNESS
    )
    config[CONF_LUX_FOR_KEYBOARD_OFF] = config.get(
        CONF_LUX_FOR_KEYBOARD_OFF, DEFAULT_LUX_FOR_KEYBOARD_OFF
    )
    config[CONF_LUX_FOR_MAX_BRIGHTNESS] = config.get(
        CONF_LUX_FOR_MAX_BRIGHTNESS, DEFAULT_LUX_FOR_MAX_BRIGHTNESS
    )
    config[CONF_LUX_FOR_MIN_BRIGHTNESS] = config.get(
        CONF_LUX_FOR_MIN_BRIGHTNESS, DEFAULT_LUX_FOR_MIN_BRIGHTNESS
    )
    return config
