from __future__ import annotations

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
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
    async_add_entities([NiceGateCover(coordinator, entry)])


class NiceGateCover(CoordinatorEntity[NiceGateDataUpdateCoordinator], CoverEntity):
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
    )
    _attr_device_class = CoverDeviceClass.GATE

    def __init__(self, coordinator: NiceGateDataUpdateCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_gate"
        self._attr_name = entry.data.get(CONF_DEVICE_NAME, "Nice Gate")

    @property
    def is_closed(self) -> bool | None:
        if self._status == "closed":
            return True
        if self._status in {"open", "opening", "closing", "stopped"}:
            return False
        return None

    @property
    def is_opening(self) -> bool:
        return self._status == "opening"

    @property
    def is_closing(self) -> bool:
        return self._status == "closing"

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if data is None:
            return {}
        return {
            "raw_status": data.status,
            "obstruct": data.obstruct,
            "device_event": data.device_event,
            "interface_event": data.interface_event,
            "timestamp": data.timestamp,
            "latitude": data.latitude,
            "longitude": data.longitude,
        }

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry.data[CONF_DEVICE_ID])},
            "manufacturer": "Nice",
            "name": self._entry.data.get(CONF_DEVICE_NAME, "Nice Gate"),
            "model": self._entry.data.get(CONF_PRODUCT_TYPE) or "IT4WIFI",
        }

    async def async_open_cover(self, **kwargs) -> None:
        await self.coordinator.async_send_command("open")

    async def async_close_cover(self, **kwargs) -> None:
        await self.coordinator.async_send_command("close")

    async def async_stop_cover(self, **kwargs) -> None:
        await self.coordinator.async_send_command("stop")

    @property
    def _status(self) -> str:
        if self.coordinator.data is None:
            return "unknown"
        return self.coordinator.data.status
