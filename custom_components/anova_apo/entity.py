"""Base entity for the Anova Precision Oven integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AnovaCoordinator
from .const import DOMAIN


class AnovaEntity(CoordinatorEntity[AnovaCoordinator]):
    """Common base for all Anova oven entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AnovaCoordinator, cooker_id: str, name: str) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self._cooker_id = cooker_id
        system = self._system
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cooker_id)},
            manufacturer="Anova",
            model="Precision Oven",
            name=name,
            sw_version=system.get("firmwareVersion"),
            hw_version=system.get("hardwareVersion"),
        )

    @property
    def _state(self) -> dict[str, Any]:
        return self.coordinator.oven_state(self._cooker_id)

    @property
    def _nodes(self) -> dict[str, Any]:
        return self.coordinator.nodes(self._cooker_id)

    @property
    def _system(self) -> dict[str, Any]:
        return self._state.get("systemInfo") or {}

    @property
    def _mode(self) -> str:
        return ((self._state.get("state") or {}).get("mode")) or "unknown"

    @property
    def available(self) -> bool:
        """Return True when the oven is reachable."""
        return bool(self._system.get("online"))
