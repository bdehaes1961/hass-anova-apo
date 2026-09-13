"""Number platform: cook settings used when Home Assistant starts a cook."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import AnovaCoordinator
from .const import DOMAIN, MAX_TEMP, MIN_TEMP
from .entity import AnovaEntity


@dataclass(frozen=True, kw_only=True)
class AnovaNumberDescription(NumberEntityDescription):
    """Describe an Anova cook setting."""

    setting: str


NUMBERS: tuple[AnovaNumberDescription, ...] = (
    AnovaNumberDescription(
        key="target_temperature",
        name="Target temperature",
        setting="temperature",
        native_min_value=MIN_TEMP,
        native_max_value=MAX_TEMP,
        native_step=1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
    ),
    AnovaNumberDescription(
        key="steam_percentage_setting",
        name="Steam percentage",
        setting="steam_percentage",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    AnovaNumberDescription(
        key="relative_humidity_setting",
        name="Target humidity",
        setting="relative_humidity",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    AnovaNumberDescription(
        key="fan_speed_setting",
        name="Fan speed setting",
        setting="fan_speed",
        native_min_value=0,
        native_max_value=100,
        native_step=25,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
    ),
    AnovaNumberDescription(
        key="timer_setting",
        name="Timer",
        setting="timer_seconds",
        native_min_value=0,
        native_max_value=86400,
        native_step=60,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        mode=NumberMode.BOX,
    ),
    AnovaNumberDescription(
        key="probe_target_setting",
        name="Probe target",
        setting="probe_target",
        native_min_value=0,
        native_max_value=100,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=NumberDeviceClass.TEMPERATURE,
        mode=NumberMode.BOX,
    ),
    AnovaNumberDescription(
        key="rack_position_setting",
        name="Rack position",
        setting="rack_position",
        native_min_value=1,
        native_max_value=5,
        native_step=1,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the cook setting numbers."""
    coordinator: AnovaCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        AnovaNumber(coordinator, cooker_id, device.get("name") or "Anova oven", description)
        for cooker_id, device in coordinator.api.devices.items()
        for description in NUMBERS
    )


class AnovaNumber(AnovaEntity, NumberEntity, RestoreEntity):
    """A stored cook setting."""

    entity_description: AnovaNumberDescription

    def __init__(
        self,
        coordinator: AnovaCoordinator,
        cooker_id: str,
        name: str,
        description: AnovaNumberDescription,
    ) -> None:
        """Initialise the number."""
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
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            try:
                self._apply(float(last.state))
            except ValueError:
                pass

    def _apply(self, value: float) -> None:
        settings = self.coordinator.settings_for(self._cooker_id)
        current = getattr(settings, self.entity_description.setting)
        setattr(
            settings,
            self.entity_description.setting,
            int(value) if isinstance(current, int) else float(value),
        )

    @property
    def native_value(self) -> float:
        """Return the stored setting."""
        settings = self.coordinator.settings_for(self._cooker_id)
        return float(getattr(settings, self.entity_description.setting))

    async def async_set_native_value(self, value: float) -> None:
        """Store a new setting value."""
        self._apply(value)
        self.async_write_ha_state()
