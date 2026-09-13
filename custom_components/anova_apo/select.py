"""Select platform: cook mode settings for the next Home Assistant cook."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AnovaCoordinator
from .const import BULB_MODES, DOMAIN, ELEMENT_PRESETS, STEAM_MODES
from .entity import AnovaEntity


@dataclass(frozen=True, kw_only=True)
class AnovaSelectDescription(SelectEntityDescription):
    """Describe an Anova select setting."""

    setting: str


SELECTS: tuple[AnovaSelectDescription, ...] = (
    AnovaSelectDescription(
        key="bulb_mode_setting",
        name="Bulb mode",
        setting="bulb_mode",
        options=BULB_MODES,
    ),
    AnovaSelectDescription(
        key="steam_mode_setting",
        name="Steam mode setting",
        setting="steam_mode",
        options=STEAM_MODES,
    ),
    AnovaSelectDescription(
        key="heating_elements_setting",
        name="Heating elements",
        setting="heating_elements",
        options=list(ELEMENT_PRESETS),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cook setting selects."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaSelect(coordinator, cooker_id, device.get("name") or "Anova oven", description)
        for cooker_id, device in coordinator.api.devices.items()
        for description in SELECTS
    )


class AnovaSelect(AnovaEntity, SelectEntity, RestoreEntity):
    """A stored cook mode setting."""

    entity_description: AnovaSelectDescription

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        cooker_id: str,
        name: str,
        description: AnovaSelectDescription,
    ) -> None:
        """Initialise the select."""
        super().__init__(coordinator, cooker_id, name)
        self.entity_description = description
        self._attr_unique_id = f"{cooker_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Settings remain editable while the oven is offline."""
        return True

    async def async_added_to_hass(self) -> None:
        """Restore the previous value."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in (self.options or []):
            setattr(
                self.coordinator.settings_for(self._cooker_id),
                self.entity_description.setting,
                last.state,
            )

    @property
    def current_option(self) -> str:
        """Return the stored option."""
        return getattr(
            self.coordinator.settings_for(self._cooker_id),
            self.entity_description.setting,
        )

    async def async_select_option(self, option: str) -> None:
        """Store a new option."""
        setattr(
            self.coordinator.settings_for(self._cooker_id),
            self.entity_description.setting,
            option,
        )
        self.async_write_ha_state()
