from __future__ import annotations

from abc import ABC, abstractmethod
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from .types import ActivityMonitorBackend

if TYPE_CHECKING:
    from .hub import LightControlHub

_LOGGER = logging.getLogger(__name__)


class ActivityMonitor(ABC):
    @abstractmethod
    def __init__(self, hub: LightControlHub, config: dict):
        raise NotImplementedError

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError


class _DummyActivityMonitor(ActivityMonitor):
    def __init__(self, hub: LightControlHub, config: dict):
        pass

    async def start(self) -> None:
        pass


def get_and_verify_activity_plugin(
    backend: ActivityMonitorBackend,
    hub: LightControlHub,
    config: dict,
) -> ActivityMonitor:
    try:
        module = import_module(
            f".{backend.value}", "backlight_control.plugins.activity_monitor"
        )
    except ImportError as e:
        _LOGGER.error("Failed to import activity monitor %s: %s", backend.value, e)
        return _DummyActivityMonitor(hub, {})

    try:
        instance = module.get_plugin(hub, config)
    except AttributeError:
        _LOGGER.error(
            "Module %s does not define a `get_plugin` function", backend.value
        )
        return _DummyActivityMonitor(hub, {})

    if not isinstance(instance, ActivityMonitor):
        _LOGGER.warning(
            "Instance of %s does not inherit from ActivityMonitor",
            instance.__class__.__name__,
        )

    return instance
