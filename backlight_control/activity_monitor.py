from __future__ import annotations

from abc import ABC, abstractmethod, abstractproperty
from importlib import import_module
import logging
from typing import TYPE_CHECKING

from .types import ActivityMonitorBackend, LightControlHubActivityUpdate

if TYPE_CHECKING:
    from .hub import LightControlHub

CONF_IDLE_DELAY = "idle_delay"
DEFAULT_IDLE_DELAY = 30

_LOGGER = logging.getLogger(__name__)


class ActivityMonitor(ABC):
    _hub: LightControlHub
    _is_idle: bool = False

    @abstractmethod
    def __init__(self, hub: LightControlHub, config: dict):
        raise NotImplementedError

    @abstractproperty
    def config(self) -> dict:
        raise NotImplementedError

    async def end_idle(self) -> None:
        self._is_idle = False
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=False))

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        return

    async def trigger_idle(self) -> None:
        self._is_idle = True
        await self._hub.activity_update(LightControlHubActivityUpdate(is_idle=True))


class _DummyActivityMonitor(ActivityMonitor):
    def __init__(self, hub: LightControlHub, config: dict):
        pass

    @property
    def config(self) -> dict:
        return {}

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

    config[CONF_IDLE_DELAY] = config.get(CONF_IDLE_DELAY, DEFAULT_IDLE_DELAY)
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
