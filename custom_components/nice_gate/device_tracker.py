from __future__ import annotations

from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.components.device_tracker.const import SourceType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_HOME, STATE_NOT_HOME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, CONF_PRODUCT_TYPE, DOMAIN
from .coordinator import NiceGateDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NiceGateLocationTracker(coordinator, entry)])


class NiceGateLocationTracker(
    CoordinatorEntity[NiceGateDataUpdateCoordinator],
    TrackerEntity,
):
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator: NiceGateDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_location"
        self._attr_name = f"{entry.data.get(CONF_DEVICE_NAME, 'Nice Gate')} location"

    @property
    def latitude(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.latitude

    @property
    def longitude(self) -> float | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.longitude

    @property
    def location_accuracy(self) -> int:
        return 10

    @property
    def state(self) -> str:
        if self.latitude is None or self.longitude is None:
            return STATE_NOT_HOME
        return STATE_HOME

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "interface_name": data.interface_name,
            "timestamp": data.timestamp,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.data[CONF_DEVICE_ID])},
            "manufacturer": "Nice",
            "name": self._entry.data.get(CONF_DEVICE_NAME, "Nice Gate"),
            "model": self._entry.data.get(CONF_PRODUCT_TYPE) or "IT4WIFI",
        }
