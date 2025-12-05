from dataclasses import dataclass
from enum import StrEnum


class ActivityMonitorBackend(StrEnum):
    GNOME_DBUS = "gnome_dbus"
    WLROOTS = "wlroots"
    XLIB_XINPUT = "xlib_xinput"
    XLIB_XSS_XINPUT_MIXED = "xlib_xss_xinput_mixed"


class ConfigError(RuntimeError):
    """Raised when invalid config is encountered."""


class KeyboardBacklightBackend(StrEnum):
    DBUS_GNOME = "dbus_gnome"
    DBUS_UPOWER = "dbus_upower"
    XBACKLIGHT = "xbacklight"


class KeyboardBacklightOperatingMode(StrEnum):
    ACTIVE_OFF = "active_off"
    ACTIVE_ON = "active_on"
    IDLE_OFF = "idle_off"


class LightSensorBackend(StrEnum):
    DBUS_SENSORPROXY = "dbus_sensorproxy"
    NONE = "none"


@dataclass(kw_only=True)
class LightControlHubActivityUpdate:
    is_idle: bool


@dataclass(kw_only=True)
class LightControlHubLightSensorUpdate:
    unit: str
    value: int


@dataclass(kw_only=True)
class LightControlHubKeyboardBacklightUpdate:
    mode: KeyboardBacklightOperatingMode
