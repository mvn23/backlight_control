from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from .types import (
    KeyboardBacklightBackend,
    LightControlHubActivityUpdate,
    LightControlHubKeyboardBacklightUpdate,
    LightControlHubLightSensorUpdate,
)

if TYPE_CHECKING:
    from .hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


class KeyboardBacklight(ABC):
    @abstractmethod
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def on_idle_event(
        self, update: LightControlHubActivityUpdate
    ) -> LightControlHubKeyboardBacklightUpdate:
        raise NotImplementedError

    @abstractmethod
    async def on_lighting_event(
        self, update: LightControlHubLightSensorUpdate
    ) -> LightControlHubKeyboardBacklightUpdate:
        raise NotImplementedError


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
