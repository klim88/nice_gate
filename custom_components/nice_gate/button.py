from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .actions import NiceGateAction, configured_name, dashboard_actions
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, CONF_PRODUCT_TYPE, DOMAIN
from .coordinator import NiceGateDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NiceGateButton(coordinator, entry, action) for action in dashboard_actions(entry.options)])


class NiceGateButton(CoordinatorEntity[NiceGateDataUpdateCoordinator], ButtonEntity):
    def __init__(
        self,
        coordinator: NiceGateDataUpdateCoordinator,
        entry: ConfigEntry,
        action: NiceGateAction,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        base_name = entry.data.get(CONF_DEVICE_NAME, "Nice Gate")
        self.action = action
        self._attr_unique_id = f"{entry.entry_id}_{action.key}"
        self._attr_name = f"{base_name} {configured_name(entry.options, action)}"
        self._attr_icon = action.icon

    async def async_press(self) -> None:
        await self.coordinator.async_send_command(self.action.key)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.data[CONF_DEVICE_ID])},
            "manufacturer": "Nice",
            "name": self._entry.data.get(CONF_DEVICE_NAME, "Nice Gate"),
            "model": self._entry.data.get(CONF_PRODUCT_TYPE) or "IT4WIFI",
        }
