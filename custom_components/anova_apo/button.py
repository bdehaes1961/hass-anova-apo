"""Button platform: start and stop a cook with the stored settings."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AnovaCoordinator
from .const import DOMAIN
from .entity import AnovaEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the start and stop buttons."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[ButtonEntity] = []
    for cooker_id, device in coordinator.api.devices.items():
        name = device.get("name") or "Anova oven"
        entities.append(AnovaStartButton(coordinator, cooker_id, name))
        entities.append(AnovaStopButton(coordinator, cooker_id, name))
    async_add_entities(entities)


class AnovaStartButton(AnovaEntity, ButtonEntity):
    """Start a cook using the stored settings."""

    _attr_name = "Start cook"
    _attr_icon = "mdi:play"

    def __init__(self, coordinator: AnovaCoordinator, cooker_id: str, name: str) -> None:
        """Initialise the button."""
        super().__init__(coordinator, cooker_id, name)
        self._attr_unique_id = f"{cooker_id}_start_cook"

    async def async_press(self) -> None:
        """Start the cook."""
        await self.coordinator.async_start(self._cooker_id)


class AnovaStopButton(AnovaEntity, ButtonEntity):
    """Stop the running cook."""

    _attr_name = "Stop cook"
    _attr_icon = "mdi:stop"

    def __init__(self, coordinator: AnovaCoordinator, cooker_id: str, name: str) -> None:
        """Initialise the button."""
        super().__init__(coordinator, cooker_id, name)
        self._attr_unique_id = f"{cooker_id}_stop_cook"

    async def async_press(self) -> None:
        """Stop the cook."""
        await self.coordinator.async_stop(self._cooker_id)
