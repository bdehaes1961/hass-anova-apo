"""Sensor platform for the Anova Precision Oven."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AnovaCoordinator
from .const import DOMAIN
from .entity import AnovaEntity

TEMP = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "state_class": SensorStateClass.MEASUREMENT,
    "suggested_display_precision": 1,
}
POWER = {
    "device_class": SensorDeviceClass.POWER,
    "native_unit_of_measurement": UnitOfPower.WATT,
    "state_class": SensorStateClass.MEASUREMENT,
}


def _get(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for key in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


@dataclass(frozen=True, kw_only=True)
class AnovaSensorDescription(SensorEntityDescription):
    """Describe an Anova sensor."""

    value: Callable[[dict[str, Any], dict[str, Any]], Any]


SENSORS: tuple[AnovaSensorDescription, ...] = (
    AnovaSensorDescription(
        key="mode",
        name="Mode",
        device_class=SensorDeviceClass.ENUM,
        options=["idle", "cook", "preheat", "cooking", "preheating", "unknown"],
        value=lambda state, nodes: _get(state, "state.mode") or "unknown",
    ),
    AnovaSensorDescription(
        key="dry_temperature",
        name="Cavity temperature",
        value=lambda s, n: _get(n, "temperatureBulbs.dry.current.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="dry_setpoint",
        name="Cavity setpoint",
        value=lambda s, n: _get(n, "temperatureBulbs.dry.setpoint.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="wet_temperature",
        name="Wet bulb temperature",
        value=lambda s, n: _get(n, "temperatureBulbs.wet.current.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="wet_setpoint",
        name="Wet bulb setpoint",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "temperatureBulbs.wet.setpoint.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="dry_top_temperature",
        name="Top element temperature",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "temperatureBulbs.dryTop.current.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="dry_bottom_temperature",
        name="Bottom element temperature",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "temperatureBulbs.dryBottom.current.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="probe_temperature",
        name="Probe temperature",
        value=lambda s, n: _get(n, "temperatureProbe.current.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="probe_setpoint",
        name="Probe target",
        value=lambda s, n: _get(n, "temperatureProbe.setpoint.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="humidity",
        name="Relative humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s, n: _get(n, "steamGenerators.relativeHumidity.current"),
    ),
    AnovaSensorDescription(
        key="steam_mode",
        name="Steam mode",
        value=lambda s, n: _get(n, "steamGenerators.mode"),
    ),
    AnovaSensorDescription(
        key="steam_percentage",
        name="Steam percentage setpoint",
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "steamGenerators.steamPercentage.setpoint"),
    ),
    AnovaSensorDescription(
        key="evaporator_temperature",
        name="Evaporator temperature",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "steamGenerators.evaporator.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="evaporator_power",
        name="Evaporator power",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "steamGenerators.evaporator.watts"),
        **POWER,
    ),
    AnovaSensorDescription(
        key="boiler_temperature",
        name="Boiler temperature",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "steamGenerators.boiler.celsius"),
        **TEMP,
    ),
    AnovaSensorDescription(
        key="boiler_power",
        name="Boiler power",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "steamGenerators.boiler.watts"),
        **POWER,
    ),
    AnovaSensorDescription(
        key="fan_speed",
        name="Fan speed",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value=lambda s, n: _get(n, "fan.speed"),
    ),
    AnovaSensorDescription(
        key="timer_mode",
        name="Timer mode",
        value=lambda s, n: _get(n, "timer.mode"),
    ),
    AnovaSensorDescription(
        key="timer_remaining",
        name="Timer remaining",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        value=lambda s, n: _get(n, "timer.current"),
    ),
    AnovaSensorDescription(
        key="timer_initial",
        name="Timer initial",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "timer.initial"),
    ),
    AnovaSensorDescription(
        key="top_element_power",
        name="Top element power",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "heatingElements.top.watts"),
        **POWER,
    ),
    AnovaSensorDescription(
        key="bottom_element_power",
        name="Bottom element power",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "heatingElements.bottom.watts"),
        **POWER,
    ),
    AnovaSensorDescription(
        key="rear_element_power",
        name="Rear element power",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "heatingElements.rear.watts"),
        **POWER,
    ),
    AnovaSensorDescription(
        key="firmware_version",
        name="Firmware version",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(s, "systemInfo.firmwareVersion"),
    ),
    AnovaSensorDescription(
        key="last_connected",
        name="Last connected",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(s, "systemInfo.lastConnectedTimestamp"),
    ),
    AnovaSensorDescription(
        key="updated_timestamp",
        name="State updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value=lambda s, n: s.get("updatedTimestamp"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the oven sensors."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaSensor(coordinator, cooker_id, device.get("name") or "Anova oven", description)
        for cooker_id, device in coordinator.api.devices.items()
        for description in SENSORS
    )


class AnovaSensor(AnovaEntity, SensorEntity):
    """A single Anova oven sensor."""

    entity_description: AnovaSensorDescription

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        cooker_id: str,
        name: str,
        description: AnovaSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, cooker_id, name)
        self.entity_description = description
        self._attr_unique_id = f"{cooker_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        value = self.entity_description.value(self._state, self._nodes)
        if self.entity_description.device_class is SensorDeviceClass.TIMESTAMP and value:
            from homeassistant.util import dt as dt_util

            return dt_util.parse_datetime(value)
        return value
