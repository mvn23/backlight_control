from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from .types import LightSensorBackend

if TYPE_CHECKING:
    from .hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


class LightSensor(ABC):

    @abstractmethod
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        raise NotImplementedError

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def pause(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def resume(self) -> None:
        raise NotImplementedError


class _DummyLightSensor(LightSensor):
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        pass

    async def start(self) -> None:
        pass

    async def pause(self) -> None:
        pass

    async def resume(self) -> None:
        pass


def get_and_verify_light_sensor_plugin(
    backend: LightSensorBackend,
    hub: LightControlHub,
    config: dict,
) -> LightSensor:
    if backend == LightSensorBackend.NONE:
        return _DummyLightSensor(hub, {})
    try:
        module = import_module(
            f".{backend.value}", "backlight_control.plugins.light_sensor"
        )
    except ImportError as e:
        _LOGGER.error("Failed to import light sensor %s: %s", backend.value, e)
        return _DummyLightSensor(hub, {})

    try:
        instance = module.get_plugin(hub, config)
    except AttributeError:
        _LOGGER.error(
            "Module %s does not define a `get_plugin` function", backend.value
        )
        return _DummyLightSensor(hub, {})

    if not isinstance(instance, LightSensor):
        _LOGGER.error(
            "Instance of %s does not inherit from LightSensor",
            instance.__class__.__name__,
        )
        return _DummyLightSensor(hub, {})

    return instance
