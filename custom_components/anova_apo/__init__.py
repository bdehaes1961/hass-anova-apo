"""The Anova Precision Oven integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import AnovaApoApi, AnovaError, build_stages
from .const import (
    ATTR_BULB_MODE,
    ATTR_FAN_SPEED,
    ATTR_HEATING_ELEMENTS,
    ATTR_PROBE_TARGET,
    ATTR_RACK_POSITION,
    ATTR_RELATIVE_HUMIDITY,
    ATTR_STAGES,
    ATTR_STEAM_MODE,
    ATTR_STEAM_PERCENTAGE,
    ATTR_TEMPERATURE,
    ATTR_TIMER_SECONDS,
    ATTR_VENT_OPEN,
    BULB_MODES,
    DEFAULT_FAN_SPEED,
    DEFAULT_RACK,
    DEFAULT_TEMPERATURE,
    DOMAIN,
    ELEMENT_PRESETS,
    EVENT_TARGET_REACHED,
    MAX_TEMP,
    MIN_TEMP,
    SERVICE_START_COOK,
    SERVICE_START_CUSTOM_COOK,
    SERVICE_STOP_COOK,
    STEAM_MODES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
]


@dataclass
class CookSettings:
    """Settings used for the next cook started from Home Assistant."""

    temperature: float = DEFAULT_TEMPERATURE
    bulb_mode: str = "dry"
    steam_mode: str = "off"
    steam_percentage: int = 100
    relative_humidity: int = 100
    fan_speed: int = DEFAULT_FAN_SPEED
    heating_elements: str = "rear"
    vent_open: bool = False
    rack_position: int = DEFAULT_RACK
    timer_seconds: int = 0
    probe_target: float = 0.0

    def as_kwargs(self) -> dict[str, Any]:
        """Return kwargs for build_stages()."""
        return {
            "temperature": self.temperature,
            "bulb_mode": self.bulb_mode,
            "steam_mode": self.steam_mode,
            "steam_percentage": self.steam_percentage,
            "relative_humidity": self.relative_humidity,
            "fan_speed": self.fan_speed,
            "heating_elements": self.heating_elements,
            "vent_open": self.vent_open,
            "rack_position": self.rack_position,
            "timer_seconds": self.timer_seconds or None,
            "probe_target": self.probe_target or None,
        }


class AnovaCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Push based coordinator holding the state of every oven."""

    def __init__(self, hass: HomeAssistant, api: AnovaApoApi) -> None:
        """Initialise the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.api = api
        self.settings: dict[str, CookSettings] = {}
        self.data = {}
        self._targets: dict[str, bool] = {}

    def settings_for(self, cooker_id: str) -> CookSettings:
        """Return (and create) the cook settings of one oven."""
        return self.settings.setdefault(cooker_id, CookSettings())

    def handle_state(self, cooker_id: str, payload: dict[str, Any]) -> None:
        """Store a new oven state and notify entities."""
        data = dict(self.data or {})
        data[cooker_id] = payload
        self._check_targets(cooker_id, payload)
        self.async_set_updated_data(data)

    def _check_targets(self, cooker_id: str, payload: dict[str, Any]) -> None:
        """Fire an event when a probe or timer target has been reached."""
        nodes = (payload.get("state") or {}).get("nodes") or {}
        probe = nodes.get("temperatureProbe") or {}
        timer = nodes.get("timer") or {}
        reached = False
        reason = None
        if probe.get("connected") and probe.get("setpoint"):
            current = ((probe.get("current") or {}).get("celsius")) or 0
            target = ((probe.get("setpoint") or {}).get("celsius")) or 0
            if target and current >= target:
                reached, reason = True, "probe"
        if timer.get("mode") == "completed" or (
            timer.get("initial") and timer.get("current") == 0 and timer.get("mode") == "running"
        ):
            reached, reason = True, "timer"
        previous = self._targets.get(cooker_id, False)
        self._targets[cooker_id] = reached
        if reached and not previous:
            self.hass.bus.async_fire(
                EVENT_TARGET_REACHED,
                {"cooker_id": cooker_id, "reason": reason},
            )

    def oven_state(self, cooker_id: str) -> dict[str, Any]:
        """Return the raw state dict of one oven."""
        return ((self.data or {}).get(cooker_id) or {}).get("state") or {}

    def nodes(self, cooker_id: str) -> dict[str, Any]:
        """Return the nodes dict of one oven."""
        return self.oven_state(cooker_id).get("nodes") or {}

    async def async_start(self, cooker_id: str, **overrides: Any) -> None:
        """Start a cook using stored settings plus optional overrides."""
        settings = self.settings_for(cooker_id)
        kwargs = settings.as_kwargs()
        kwargs.update({k: v for k, v in overrides.items() if v is not None})
        try:
            await self.api.async_start_cook(cooker_id, build_stages(**kwargs))
        except AnovaError as err:
            raise HomeAssistantError(f"Anova start failed: {err}") from err

    async def async_stop(self, cooker_id: str) -> None:
        """Stop the running cook."""
        try:
            await self.api.async_stop_cook(cooker_id)
        except AnovaError as err:
            raise HomeAssistantError(f"Anova stop failed: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Anova Precision Oven from a config entry."""
    session = async_get_clientsession(hass)
    api = AnovaApoApi(session, entry.data[CONF_ACCESS_TOKEN])
    coordinator = AnovaCoordinator(hass, api)
    api._on_state = coordinator.handle_state  # noqa: SLF001

    await api.start()
    try:
        await asyncio.wait_for(api._devices_seen.wait(), timeout=45)  # noqa: SLF001
    except (TimeoutError, asyncio.TimeoutError) as err:
        await api.stop()
        raise ConfigEntryNotReady("No oven list received from the Anova cloud") from err

    # Give the ovens a moment to push their first state.
    await asyncio.sleep(3)
    coordinator.data = dict(api.states)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator: AnovaCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.api.stop()
    return unloaded


def _resolve(hass: HomeAssistant, call: ServiceCall) -> list[tuple[AnovaCoordinator, str]]:
    """Resolve the targeted ovens from a service call."""
    registry = dr.async_get(hass)
    device_ids = call.data.get("device_id") or []
    if isinstance(device_ids, str):
        device_ids = [device_ids]
    result: list[tuple[AnovaCoordinator, str]] = []
    for device_id in device_ids:
        device = registry.async_get(device_id)
        if device is None:
            continue
        cooker_id = next(
            (ident[1] for ident in device.identifiers if ident[0] == DOMAIN), None
        )
        if cooker_id is None:
            continue
        for entry_id in device.config_entries:
            coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
            if coordinator is not None:
                result.append((coordinator, cooker_id))
                break
    if not result:
        raise HomeAssistantError("No Anova oven matched this service call")
    return result


START_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.Any(cv.string, [cv.string]),
        vol.Required(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_TEMP, max=MAX_TEMP)
        ),
        vol.Optional(ATTR_BULB_MODE): vol.In(BULB_MODES),
        vol.Optional(ATTR_STEAM_MODE): vol.In(STEAM_MODES),
        vol.Optional(ATTR_STEAM_PERCENTAGE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional(ATTR_RELATIVE_HUMIDITY): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=100)
        ),
        vol.Optional(ATTR_FAN_SPEED): vol.All(vol.Coerce(int), vol.Range(min=0, max=100)),
        vol.Optional(ATTR_HEATING_ELEMENTS): vol.In(list(ELEMENT_PRESETS)),
        vol.Optional(ATTR_VENT_OPEN): cv.boolean,
        vol.Optional(ATTR_RACK_POSITION): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        vol.Optional(ATTR_TIMER_SECONDS): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_PROBE_TARGET): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=100)
        ),
    }
)

CUSTOM_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.Any(cv.string, [cv.string]),
        vol.Required(ATTR_STAGES): vol.Any(cv.string, list),
    }
)

STOP_SCHEMA = vol.Schema({vol.Required("device_id"): vol.Any(cv.string, [cv.string])})


def _async_register_services(hass: HomeAssistant) -> None:
    """Register the integration services once."""
    if hass.services.has_service(DOMAIN, SERVICE_STOP_COOK):
        return

    async def _start(call: ServiceCall) -> None:
        overrides = {
            key: call.data.get(key)
            for key in (
                ATTR_TEMPERATURE,
                ATTR_BULB_MODE,
                ATTR_STEAM_MODE,
                ATTR_STEAM_PERCENTAGE,
                ATTR_RELATIVE_HUMIDITY,
                ATTR_FAN_SPEED,
                ATTR_HEATING_ELEMENTS,
                ATTR_VENT_OPEN,
                ATTR_RACK_POSITION,
                ATTR_TIMER_SECONDS,
                ATTR_PROBE_TARGET,
            )
            if key in call.data
        }
        for coordinator, cooker_id in _resolve(hass, call):
            await coordinator.async_start(cooker_id, **overrides)

    async def _start_custom(call: ServiceCall) -> None:
        stages = call.data[ATTR_STAGES]
        if isinstance(stages, str):
            import json

            stages = json.loads(stages)
        for coordinator, cooker_id in _resolve(hass, call):
            try:
                await coordinator.api.async_start_cook(cooker_id, stages)
            except AnovaError as err:
                raise HomeAssistantError(f"Anova custom start failed: {err}") from err

    async def _stop(call: ServiceCall) -> None:
        for coordinator, cooker_id in _resolve(hass, call):
            await coordinator.async_stop(cooker_id)

    hass.services.async_register(DOMAIN, SERVICE_START_COOK, _start, schema=START_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_START_CUSTOM_COOK, _start_custom, schema=CUSTOM_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_STOP_COOK, _stop, schema=STOP_SCHEMA)
