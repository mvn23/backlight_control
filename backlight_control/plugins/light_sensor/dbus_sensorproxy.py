from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
from dbus_fast.introspection import Node

from ...light_sensor import LightSensor
from ...types import LightControlHubLightSensorUpdate

if TYPE_CHECKING:
    from dbus_fast.aio.proxy_object import ProxyInterface

    from ...hub import LightControlHub

_LOGGER = logging.getLogger(__name__)

_MODULE_DIR = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))


def get_plugin(hub: LightControlHub, config: dict):
    return DBusSensorProxyLightSensor(hub)


class DBusSensorProxyLightSensor(LightSensor):
    def __init__(self, hub: LightControlHub) -> None:
        self._hub: LightControlHub = hub
        self._iio_sensor: ProxyInterface | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        bus = await MessageBus(bus_type=BusType.SYSTEM).connect()

        with open(
            os.path.join(_MODULE_DIR, "dbus_sensorproxy_net.hadess.SensorProxy.xml"),
        ) as f:
            node_introspection = f.read()

        iio_sensor_proxy = bus.get_proxy_object(
            "net.hadess.SensorProxy",
            "/net/hadess/SensorProxy",
            Node.parse(node_introspection),
        )
        self._iio_sensor = iio_sensor_proxy.get_interface(
            "net.hadess.SensorProxy",
        )

        self._loop = asyncio.get_running_loop()

        def on_properties_changed(
            interface_name,
            changed_properties,
            invalidated_properties,
        ):
            update = LightControlHubLightSensorUpdate(
                unit="",
                value=0,
            )
            for changed, variant in changed_properties.items():
                _LOGGER.debug("property changed: %s - %s", changed, variant.value)
                if changed == "LightLevelUnit":
                    update.unit = variant.value
                elif changed == "LightLevel":
                    update.value = int(variant.value)
            self._update_task = self._loop.create_task(self._send_update(update))

        self._iio_dbus_properties = iio_sensor_proxy.get_interface(
            "org.freedesktop.DBus.Properties",
        )
        self._iio_dbus_properties.on_properties_changed(on_properties_changed)  # type: ignore[attr-defined]

        await self.resume()

    async def resume(self):
        await self._iio_sensor.call_claim_light()
        await self._send_update(
            LightControlHubLightSensorUpdate(
                unit=await self._iio_sensor.get_light_level_unit(),  # type: ignore[attr-defined]
                value=int(await self._iio_sensor.get_light_level()),  # type: ignore[attr-defined]
            )
        )

    async def pause(self):
        await self._iio_sensor.call_release_light()

    async def _send_update(self, update: LightControlHubLightSensorUpdate):
        await self._hub.light_sensor_update(update)
        self._update_task = None
