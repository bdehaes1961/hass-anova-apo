"""Constants for the Anova Precision Oven integration."""

from __future__ import annotations

DOMAIN = "anova_apo"

CONF_ACCESS_TOKEN = "access_token"

WS_URL = "wss://devices.anovaculinary.io/"
WS_SUBPROTOCOL = "ANOVA_V2"
PLATFORM_ID = "android"

SIGNAL_STATE = f"{DOMAIN}_state"
SIGNAL_NEW_DEVICE = f"{DOMAIN}_new_device"

EVENT_TARGET_REACHED = f"{DOMAIN}_target_reached"
EVENT_COOK_STARTED = f"{DOMAIN}_cook_started"
EVENT_COOK_STOPPED = f"{DOMAIN}_cook_stopped"

SERVICE_START_COOK = "start_cook"
SERVICE_START_CUSTOM_COOK = "start_custom_cook"
SERVICE_STOP_COOK = "stop_cook"

ATTR_OVEN = "oven"
ATTR_TEMPERATURE = "temperature"
ATTR_BULB_MODE = "bulb_mode"
ATTR_STEAM_MODE = "steam_mode"
ATTR_STEAM_PERCENTAGE = "steam_percentage"
ATTR_RELATIVE_HUMIDITY = "relative_humidity"
ATTR_FAN_SPEED = "fan_speed"
ATTR_HEATING_ELEMENTS = "heating_elements"
ATTR_VENT_OPEN = "vent_open"
ATTR_RACK_POSITION = "rack_position"
ATTR_TIMER_SECONDS = "timer_seconds"
ATTR_PROBE_TARGET = "probe_target"
ATTR_STAGES = "stages"

BULB_MODES = ["dry", "wet"]
STEAM_MODES = ["off", "steam-percentage", "relative-humidity"]
ELEMENT_PRESETS = {
    "rear": {"top": False, "bottom": False, "rear": True},
    "top": {"top": True, "bottom": False, "rear": False},
    "bottom": {"top": False, "bottom": True, "rear": False},
    "top_bottom": {"top": True, "bottom": True, "rear": False},
    "all": {"top": True, "bottom": True, "rear": True},
}

DEFAULT_TEMPERATURE = 180.0
DEFAULT_FAN_SPEED = 100
DEFAULT_RACK = 3
MIN_TEMP = 25.0
MAX_TEMP = 250.0
