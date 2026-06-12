from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .actions import ACTIONS, ACTION_BY_SERVICE
from .const import CONF_DEVICE_ID, DOMAIN, PLATFORMS
from .coordinator import NiceGateDataUpdateCoordinator

SERVICE_ACTIONS = tuple(action.service for action in ACTIONS)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Optional(CONF_DEVICE_ID): str,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = NiceGateDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    async def handle_service(call) -> None:
        coordinators = hass.data.get(DOMAIN, {})
        if not coordinators:
            raise RuntimeError("No Nice Gate config entries are loaded")
        device_id = call.data.get(CONF_DEVICE_ID)
        coordinator = None
        if device_id:
            for item in coordinators.values():
                if item.entry.data.get(CONF_DEVICE_ID) == device_id:
                    coordinator = item
                    break
        if coordinator is None:
            coordinator = next(iter(coordinators.values()))
        action = ACTION_BY_SERVICE[call.service]
        await coordinator.async_send_command(action.key)

    schema = vol.Schema({vol.Optional(CONF_DEVICE_ID): str})
    for service in SERVICE_ACTIONS:
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(DOMAIN, service, handle_service, schema=schema)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
