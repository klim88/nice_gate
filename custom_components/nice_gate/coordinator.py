from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any, TypeVar

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_ID, DOMAIN
from .nice_gate_core import GateStatus, NiceGateSession

_LOGGER = logging.getLogger(__name__)
_T = TypeVar("_T")
_RETRYABLE_NHK_ERRORS = (
    "Empty NHK response",
    "CONNECT response has no Authentication",
    "Timed out waiting for NHK response",
)


class NiceGateDataUpdateCoordinator(DataUpdateCoordinator[GateStatus]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10),
        )
        self.entry = entry
        self.session: NiceGateSession | None = None
        self.device_index = 0
        self._operation_lock = asyncio.Lock()

    async def _async_update_data(self) -> GateStatus:
        try:
            return await self._async_run_session_job("status", self.device_index, 1, False)
        except Exception as exc:
            raise UpdateFailed(f"Nice Gate status failed: {exc}") from exc

    async def async_send_command(self, action: str) -> None:
        await self._async_run_session_job("command", action, self.device_index, 1, False)
        await self.async_request_refresh()

    async def _async_run_session_job(
        self,
        name: str,
        *args: Any,
    ) -> _T:
        async with self._operation_lock:
            await self._async_ensure_session()
            assert self.session is not None

            for attempt in range(1, 4):
                try:
                    job = getattr(self.session, name)
                    return await self.hass.async_add_executor_job(job, *args)
                except Exception as exc:
                    if attempt >= 3 or not _is_retryable_nhk_error(exc):
                        raise
                    _LOGGER.debug("Retrying Nice Gate %s after NHK error: %s", name, exc)
                    await asyncio.sleep(0.7 * attempt)

            raise RuntimeError(f"Nice Gate {name} failed without an exception")

    async def _async_ensure_session(self) -> None:
        if self.session is not None:
            return
        username = self.entry.data[CONF_USERNAME]
        password = self.entry.data[CONF_PASSWORD]
        device_id = self.entry.data[CONF_DEVICE_ID]
        self.session = await self.hass.async_add_executor_job(
            NiceGateSession.login,
            username,
            password,
        )
        for device in self.session.devices():
            if device.device_id == device_id:
                self.device_index = device.index
                return
        raise RuntimeError(f"Nice device {device_id} was not found in this account")


def _is_retryable_nhk_error(exc: Exception) -> bool:
    text = str(exc)
    return any(marker in text for marker in _RETRYABLE_NHK_ERRORS)
