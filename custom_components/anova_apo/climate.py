"""Climate platform for the Anova Precision Oven."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AnovaCoordinator
from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .entity import AnovaEntity

FAN_MODES = ["off", "low", "medium", "high", "max"]
FAN_SPEEDS = {"off": 0, "low": 25, "medium": 50, "high": 75, "max": 100}
ACTIVE_MODES = ("cook", "preheat", "cooking", "preheating")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the oven climate entities."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaOvenClimate(coordinator, cooker_id, device.get("name") or "Anova oven")
        for cooker_id, device in coordinator.api.devices.items()
    )


class AnovaOvenClimate(AnovaEntity, ClimateEntity):
    """Represent the oven as a climate entity."""

    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_fan_modes = FAN_MODES
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 1.0
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: AnovaCoordinator, cooker_id: str, name: str) -> None:
        """Initialise the climate entity."""
        super().__init__(coordinator, cooker_id, name)
        self._attr_unique_id = f"{cooker_id}_oven"

    @property
    def _settings(self):
        return self.coordinator.settings_for(self._cooker_id)

    @property
    def _bulbs(self) -> dict[str, Any]:
        return self._nodes.get("temperatureBulbs") or {}

    @property
    def current_temperature(self) -> float | None:
        """Return the current cavity temperature."""
        bulbs = self._bulbs
        mode = bulbs.get("mode") or "dry"
        return ((bulbs.get(mode) or {}).get("current") or {}).get("celsius")

    @property
    def target_temperature(self) -> float | None:
        """Return the setpoint, from the oven when cooking, else the stored one."""
        bulbs = self._bulbs
        mode = bulbs.get("mode") or "dry"
        setpoint = ((bulbs.get(mode) or {}).get("setpoint") or {}).get("celsius")
        if self._mode in ACTIVE_MODES and setpoint:
            return setpoint
        return self._settings.temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return HEAT when a cook is running."""
        return HVACMode.HEAT if self._mode in ACTIVE_MODES else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction:
        """Return whether the elements are actually firing."""
        if self._mode not in ACTIVE_MODES:
            return HVACAction.OFF
        elements = self._nodes.get("heatingElements") or {}
        if any((elements.get(key) or {}).get("on") for key in ("top", "bottom", "rear")):
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str:
        """Return the fan mode."""
        speed = (self._nodes.get("fan") or {}).get("speed")
        if self._mode not in ACTIVE_MODES:
            speed = self._settings.fan_speed
        speed = speed or 0
        return min(FAN_MODES, key=lambda key: abs(FAN_SPEEDS[key] - speed))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the full cook context."""
        timer = self._nodes.get("timer") or {}
        probe = self._nodes.get("temperatureProbe") or {}
        steam = self._nodes.get("steamGenerators") or {}
        settings = self._settings
        return {
            "oven_mode": self._mode,
            "cooker_id": self._cooker_id,
            "bulb_mode": (self._bulbs.get("mode")),
            "steam_mode": steam.get("mode"),
            "relative_humidity": (steam.get("relativeHumidity") or {}).get("current"),
            "timer_mode": timer.get("mode"),
            "timer_initial": timer.get("initial"),
            "timer_remaining": timer.get("current"),
            "probe_connected": probe.get("connected"),
            "probe_temperature": ((probe.get("current") or {}).get("celsius")),
            "door_closed": (self._nodes.get("door") or {}).get("closed"),
            "water_tank_empty": (self._nodes.get("waterTank") or {}).get("empty"),
            "next_cook_steam_mode": settings.steam_mode,
            "next_cook_steam_percentage": settings.steam_percentage,
            "next_cook_heating_elements": settings.heating_elements,
            "next_cook_timer_seconds": settings.timer_seconds,
            "next_cook_probe_target": settings.probe_target,
            "next_cook_rack_position": settings.rack_position,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new setpoint, restarting the cook when one is running."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._settings.temperature = float(temperature)
        if self._mode in ACTIVE_MODES:
            await self.coordinator.async_start(self._cooker_id)
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan speed, restarting the cook when one is running."""
        self._settings.fan_speed = FAN_SPEEDS[fan_mode]
        if self._mode in ACTIVE_MODES:
            await self.coordinator.async_start(self._cooker_id)
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Start or stop the cook."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_stop(self._cooker_id)
        else:
            await self.coordinator.async_start(self._cooker_id)

    async def async_turn_on(self) -> None:
        """Start a cook."""
        await self.coordinator.async_start(self._cooker_id)

    async def async_turn_off(self) -> None:
        """Stop the cook."""
        await self.coordinator.async_stop(self._cooker_id)
