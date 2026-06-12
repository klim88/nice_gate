from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector

from .actions import (
    ACTION_BY_KEY,
    ACTIONS,
    CONF_ACTION_DASHBOARD,
    CONF_ACTION_NAME,
    CONF_ACTION_OPTIONS,
    CONF_ACTION_YANDEX,
    normalize_action_options,
)
from .const import (
    CONF_CLOUD_ID,
    CONF_DEVICE_ID,
    CONF_DEVICE_INDEX,
    CONF_DEVICE_NAME,
    CONF_HOME_ID,
    CONF_PERMISSION,
    CONF_PRODUCT_TYPE,
    DOMAIN,
)
from .nice_gate_core import NiceGateSession

CONF_ACTION_KEY = "action_key"
CONF_ACTION_TITLE = "action_title"
CONF_SHOW_DASHBOARD = "show_dashboard"
CONF_EXPOSE_YANDEX = "expose_yandex"


class NiceGateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._devices = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NiceGateOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            try:
                session = await self.hass.async_add_executor_job(
                    NiceGateSession.login,
                    username,
                    password,
                )
                devices = session.devices()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._username = username
                self._password = password
                self._devices = devices
                if len(devices) == 1:
                    return await self._create_entry_for_device(devices[0])
                return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        errors = {}
        options = {
            str(device.index): f"{device.name or device.device_id} ({device.product_type or 'Nice'})"
            for device in self._devices
        }
        if user_input is not None:
            selected_index = int(user_input[CONF_DEVICE_INDEX])
            for device in self._devices:
                if device.index == selected_index:
                    return await self._create_entry_for_device(device)
            errors["base"] = "unknown_device"

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_INDEX): vol.In(options)}),
            errors=errors,
        )

    async def async_step_import(self, import_config):
        self._username = import_config[CONF_USERNAME]
        self._password = import_config[CONF_PASSWORD]
        requested_device_id = import_config.get(CONF_DEVICE_ID)
        try:
            session = await self.hass.async_add_executor_job(
                NiceGateSession.login,
                self._username,
                self._password,
            )
            devices = session.devices()
        except Exception:
            return self.async_abort(reason="cannot_connect")
        if requested_device_id:
            for device in devices:
                if device.device_id == requested_device_id:
                    return await self._create_entry_for_device(device)
            return self.async_abort(reason="unknown_device")
        if not devices:
            return self.async_abort(reason="cannot_connect")
        return await self._create_entry_for_device(devices[0])

    async def _create_entry_for_device(self, device):
        await self.async_set_unique_id(device.device_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.name or device.device_id,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_DEVICE_ID: device.device_id,
                CONF_DEVICE_NAME: device.name or device.device_id,
                CONF_CLOUD_ID: device.cloud_id,
                CONF_PRODUCT_TYPE: device.product_type,
                CONF_HOME_ID: device.home_id,
                CONF_PERMISSION: device.permission,
            },
        )


class NiceGateOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry) -> None:
        self._entry = config_entry
        self._username: str | None = config_entry.data.get(CONF_USERNAME)
        self._password: str | None = config_entry.data.get(CONF_PASSWORD)
        self._devices = []
        self._selected_action_key: str | None = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["account", "actions"],
        )

    async def async_step_account(self, user_input=None):
        errors = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME]
            password = user_input.get(CONF_PASSWORD) or self._password
            try:
                session = await self.hass.async_add_executor_job(
                    NiceGateSession.login,
                    username,
                    password,
                )
                devices = session.devices()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                self._username = username
                self._password = password
                self._devices = devices
                if len(devices) == 1:
                    return await self._update_entry_for_device(devices[0])
                return await self.async_step_device()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default=self._username or ""): str,
                    vol.Optional(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        errors = {}
        options = {
            str(device.index): f"{device.name or device.device_id} ({device.product_type or 'Nice'})"
            for device in self._devices
        }
        current_device_id = self._entry.data.get(CONF_DEVICE_ID)
        current_index = next(
            (str(device.index) for device in self._devices if device.device_id == current_device_id),
            next(iter(options), ""),
        )

        if user_input is not None:
            selected_index = int(user_input[CONF_DEVICE_INDEX])
            for device in self._devices:
                if device.index == selected_index:
                    return await self._update_entry_for_device(device)
            errors["base"] = "unknown_device"

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_INDEX, default=current_index): vol.In(options)}),
            errors=errors,
        )

    async def async_step_actions(self, user_input=None):
        action_options = normalize_action_options(self._entry.options)
        choices = {}
        for action in ACTIONS:
            config = action_options[action.key]
            flags = []
            if config[CONF_ACTION_DASHBOARD]:
                flags.append("HA")
            if config[CONF_ACTION_YANDEX]:
                flags.append("Yandex")
            suffix = f" [{', '.join(flags)}]" if flags else ""
            choices[action.key] = f"{config[CONF_ACTION_NAME]} ({action.key}){suffix}"

        if user_input is not None:
            self._selected_action_key = user_input[CONF_ACTION_KEY]
            return await self.async_step_action()

        return self.async_show_form(
            step_id="actions",
            data_schema=vol.Schema({vol.Required(CONF_ACTION_KEY): vol.In(choices)}),
        )

    async def async_step_action(self, user_input=None):
        if not self._selected_action_key or self._selected_action_key not in ACTION_BY_KEY:
            return await self.async_step_actions()

        action = ACTION_BY_KEY[self._selected_action_key]
        options = dict(self._entry.options)
        action_options = normalize_action_options(options)
        current = action_options[action.key]

        if user_input is not None:
            name = (user_input.get(CONF_ACTION_TITLE) or action.default_name).strip()
            action_options[action.key] = {
                CONF_ACTION_NAME: name or action.default_name,
                CONF_ACTION_DASHBOARD: bool(user_input.get(CONF_SHOW_DASHBOARD)),
                CONF_ACTION_YANDEX: bool(user_input.get(CONF_EXPOSE_YANDEX)),
            }
            options[CONF_ACTION_OPTIONS] = action_options
            return self.async_create_entry(title="", data=options)

        return self.async_show_form(
            step_id="action",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ACTION_TITLE, default=current[CONF_ACTION_NAME]): str,
                    vol.Required(CONF_SHOW_DASHBOARD, default=current[CONF_ACTION_DASHBOARD]): bool,
                    vol.Required(CONF_EXPOSE_YANDEX, default=current[CONF_ACTION_YANDEX]): bool,
                }
            ),
            description_placeholders={
                "action_key": action.key,
                "service_name": action.service,
            },
        )

    async def _update_entry_for_device(self, device):
        data = dict(self._entry.data)
        data.update(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_DEVICE_ID: device.device_id,
                CONF_DEVICE_NAME: device.name or device.device_id,
                CONF_CLOUD_ID: device.cloud_id,
                CONF_PRODUCT_TYPE: device.product_type,
                CONF_HOME_ID: device.home_id,
                CONF_PERMISSION: device.permission,
            }
        )
        self.hass.config_entries.async_update_entry(
            self._entry,
            title=device.name or device.device_id,
            data=data,
        )
        await self.hass.config_entries.async_reload(self._entry.entry_id)
        return self.async_create_entry(title="", data=dict(self._entry.options))
