from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .actions import NiceGateAction, configured_name, yandex_actions
from .const import CONF_DEVICE_ID, CONF_DEVICE_NAME, CONF_PRODUCT_TYPE, DOMAIN
from .coordinator import NiceGateDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([NiceGateYandexSwitch(coordinator, entry, action) for action in yandex_actions(entry.options)])


class NiceGateYandexSwitch(CoordinatorEntity[NiceGateDataUpdateCoordinator], SwitchEntity):
    def __init__(
        self,
        coordinator: NiceGateDataUpdateCoordinator,
        entry: ConfigEntry,
        action: NiceGateAction,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self.action = action
        base_name = entry.data.get(CONF_DEVICE_NAME, "Nice Gate")
        self._attr_unique_id = f"{entry.entry_id}_yandex_{action.key}"
        self._attr_name = f"{base_name} {configured_name(entry.options, action)}"
        self._attr_icon = action.icon

    @property
    def is_on(self) -> bool:
        status = self.coordinator.data.status if self.coordinator.data else "unknown"
        if self.action.key == "close":
            return status == "closed"
        if self.action.key.startswith("light"):
            return False
        return status in {"open", "opening", "closing", "stopped"}

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_send_command(self.action.key)

    async def async_turn_off(self, **kwargs) -> None:
        off_action = self.action.yandex_turn_off_action
        if off_action:
            await self.coordinator.async_send_command(off_action)

    @property
    def extra_state_attributes(self):
        return {
            "nice_gate_action": self.action.key,
            "yandex_proxy": True,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.data[CONF_DEVICE_ID])},
            "manufacturer": "Nice",
            "name": self._entry.data.get(CONF_DEVICE_NAME, "Nice Gate"),
            "model": self._entry.data.get(CONF_PRODUCT_TYPE) or "IT4WIFI",
        }
