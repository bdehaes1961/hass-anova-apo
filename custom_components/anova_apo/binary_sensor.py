"""Binary sensor platform for the Anova Precision Oven."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AnovaCoordinator
from .const import DOMAIN
from .entity import AnovaEntity

DIAG = EntityCategory.DIAGNOSTIC


def _get(data: dict[str, Any], path: str) -> Any:
    node: Any = data
    for key in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


@dataclass(frozen=True, kw_only=True)
class AnovaBinaryDescription(BinarySensorEntityDescription):
    """Describe an Anova binary sensor."""

    value: Callable[[dict[str, Any], dict[str, Any]], Any]


BINARY_SENSORS: tuple[AnovaBinaryDescription, ...] = (
    AnovaBinaryDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=DIAG,
        value=lambda s, n: _get(s, "systemInfo.online"),
    ),
    AnovaBinaryDescription(
        key="door_open",
        name="Door",
        device_class=BinarySensorDeviceClass.DOOR,
        value=lambda s, n: not _get(n, "door.closed"),
    ),
    AnovaBinaryDescription(
        key="water_tank_empty",
        name="Water tank empty",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda s, n: _get(n, "waterTank.empty"),
    ),
    AnovaBinaryDescription(
        key="probe_connected",
        name="Probe connected",
        device_class=BinarySensorDeviceClass.PLUG,
        value=lambda s, n: _get(n, "temperatureProbe.connected"),
    ),
    AnovaBinaryDescription(
        key="lamp_on",
        name="Lamp",
        device_class=BinarySensorDeviceClass.LIGHT,
        value=lambda s, n: _get(n, "lamp.on"),
    ),
    AnovaBinaryDescription(
        key="vent_open",
        name="Vent open",
        entity_registry_enabled_default=False,
        value=lambda s, n: _get(n, "vent.open"),
    ),
    AnovaBinaryDescription(
        key="top_element",
        name="Top element",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.RUNNING,
        value=lambda s, n: _get(n, "heatingElements.top.on"),
    ),
    AnovaBinaryDescription(
        key="bottom_element",
        name="Bottom element",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.RUNNING,
        value=lambda s, n: _get(n, "heatingElements.bottom.on"),
    ),
    AnovaBinaryDescription(
        key="rear_element",
        name="Rear element",
        entity_registry_enabled_default=False,
        device_class=BinarySensorDeviceClass.RUNNING,
        value=lambda s, n: _get(n, "heatingElements.rear.on"),
    ),
    AnovaBinaryDescription(
        key="descale_required",
        name="Descale required",
        device_class=BinarySensorDeviceClass.PROBLEM,
        value=lambda s, n: _get(n, "steamGenerators.boiler.descaleRequired"),
    ),
    AnovaBinaryDescription(
        key="boiler_failed",
        name="Boiler failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "steamGenerators.boiler.failed")
        or _get(n, "steamGenerators.boiler.overheated"),
    ),
    AnovaBinaryDescription(
        key="evaporator_failed",
        name="Evaporator failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "steamGenerators.evaporator.failed")
        or _get(n, "steamGenerators.evaporator.overheated"),
    ),
    AnovaBinaryDescription(
        key="element_failure",
        name="Element failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: any(
            _get(n, f"heatingElements.{key}.failed") for key in ("top", "bottom", "rear")
        ),
    ),
    AnovaBinaryDescription(
        key="fan_failed",
        name="Fan failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "fan.failed"),
    ),
    AnovaBinaryDescription(
        key="overheated",
        name="Cavity overheated",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "temperatureBulbs.dryTop.overheated")
        or _get(n, "temperatureBulbs.dryBottom.overheated"),
    ),
    AnovaBinaryDescription(
        key="triacs_failed",
        name="Triac failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(s, "systemInfo.triacsFailed"),
    ),
    AnovaBinaryDescription(
        key="ui_communication_failed",
        name="UI communication failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "userInterfaceCircuit.communicationFailed"),
    ),
    AnovaBinaryDescription(
        key="dose_failed",
        name="Water dosing failure",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=DIAG,
        value=lambda s, n: _get(n, "temperatureBulbs.wet.doseFailed"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the oven binary sensors."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaBinarySensor(
            coordinator, cooker_id, device.get("name") or "Anova oven", description
        )
        for cooker_id, device in coordinator.api.devices.items()
        for description in BINARY_SENSORS
    )


class AnovaBinarySensor(AnovaEntity, BinarySensorEntity):
    """A single Anova oven binary sensor."""

    entity_description: AnovaBinaryDescription

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        cooker_id: str,
        name: str,
        description: AnovaBinaryDescription,
    ) -> None:
        """Initialise the binary sensor."""
        super().__init__(coordinator, cooker_id, name)
        self.entity_description = description
        self._attr_unique_id = f"{cooker_id}_{description.key}"

    @property
    def available(self) -> bool:
        """The connectivity sensor stays available when the oven is offline."""
        if self.entity_description.key == "online":
            return bool(self._state)
        return super().available

    @property
    def is_on(self) -> bool | None:
        """Return the sensor state."""
        return bool(self.entity_description.value(self._state, self._nodes))
