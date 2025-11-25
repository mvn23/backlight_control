from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from ...keyboard_backlight import KeyboardBacklight

if TYPE_CHECKING:
    from ...hub import LightControlHub

CONF_CONTROL = "control"
CONF_FADE_FPS = "fade_fps"
CONF_FADE_TIME = "fade_time"
DEFAULT_CONTROL = "chromeos::kbd_backlight"
DEFAULT_FADE_FPS = 30
DEFAULT_FADE_TIME = 300

_LOGGER = logging.getLogger(__name__)


def get_plugin(hub: LightControlHub, config: dict):
    config[CONF_CONTROL] = config.get(CONF_CONTROL, DEFAULT_CONTROL)
    config[CONF_FADE_FPS] = config.get(CONF_FADE_FPS, DEFAULT_FADE_FPS)
    config[CONF_FADE_TIME] = config.get(CONF_FADE_TIME, DEFAULT_FADE_TIME)
    return XBacklightKeyboardBacklight(hub, config)


class XBacklightKeyboardBacklight(KeyboardBacklight):
    def __init__(self, hub: LightControlHub, config: dict) -> None:
        self._config = config
        self._maximum: int = 100
        self.stored: int = 1
        self._hub: LightControlHub = hub

    async def get_current(self) -> int:
        proc = await asyncio.create_subprocess_exec(
            "xbacklight",
            "-ctrl",
            self._config[CONF_CONTROL],
            "-get",
            stdout=asyncio.subprocess.PIPE,
        )
        output, _ = await proc.communicate()
        return int(output)

    @property
    def maximum(self) -> int:
        return self._maximum

    async def set_absolute(self, value: int) -> None:
        proc = await asyncio.create_subprocess_exec(
            "xbacklight",
            "-ctrl",
            self._config[CONF_CONTROL],
            "-set",
            str(value),
            "-time",
            str(self._config[CONF_FADE_TIME]),
            "-fps",
            str(self._config[CONF_FADE_FPS]),
        )
        await proc.wait()

    async def start(self) -> None:
        pass
