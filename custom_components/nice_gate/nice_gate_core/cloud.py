from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


BASE_URL = "https://integration.niceappdomain.com/myNiceCloud/"
CLIENT_ID = "android-client-id"
CLIENT_SECRET = "android-client-id_21"


class MyNiceCloudError(RuntimeError):
    pass


@dataclass(frozen=True)
class Token:
    access_token: str
    token_type: str = "Bearer"
    refresh_token: str | None = None
    expires_in: int | None = None


@dataclass(frozen=True)
class AccessoryCredential:
    device_id: str
    cloud_id: str | None
    nhk_username: str
    nhk_password: str
    nhk_controller_id: str
    product_type: str | None = None
    name: str | None = None
    home_id: str | None = None
    permission: str | None = None
    maintenance_state: str | None = None

    def redacted(self) -> dict[str, str | None]:
        return {
            "device_id": self.device_id,
            "cloud_id": self.cloud_id,
            "product_type": self.product_type,
            "name": self.name,
            "home_id": self.home_id,
            "permission": self.permission,
            "maintenance_state": self.maintenance_state,
            "nhk_username": mask_secret(self.nhk_username),
            "nhk_password": mask_secret(self.nhk_password),
            "nhk_controller_id": mask_secret(self.nhk_controller_id),
        }


def load_env(path: str | Path = ".env") -> dict[str, str]:
    result: dict[str, str] = {}
    env_path = Path(path)
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip('"').strip("'")
    for key, value in os.environ.items():
        if key.startswith("MYNICE_") or key.startswith("NICE_"):
            result[key] = value
    return result


def mask_secret(value: str | None, left: int = 4, right: int = 3) -> str | None:
    if not value:
        return value
    if len(value) <= left + right:
        return "*" * len(value)
    return f"{value[:left]}...{value[-right:]}"


class MyNiceCloud:
    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url.rstrip("/") + "/"

    def login(self, username: str, password: str) -> Token:
        data = self._request_json(
            "POST",
            "oauth/token",
            query={
                "grant_type": "password",
                "username": username,
                "password": password,
            },
            headers={"Authorization": self._basic_auth()},
            body=b"",
        )
        return self._token_from_response(data)

    def refresh(self, refresh_token: str) -> Token:
        data = self._request_json(
            "POST",
            "oauth/token",
            query={"grant_type": "refresh_token", "refresh_token": refresh_token},
            headers={"Authorization": self._basic_auth()},
            body=b"",
        )
        return self._token_from_response(data)

    def macro_user_data(self, token: Token) -> dict[str, Any]:
        return self._request_json(
            "GET",
            "api/v1/macrouser/user",
            headers={"Authorization": f"{token.token_type} {token.access_token}"},
        )

    def _request_json(
        self,
        method: str,
        path: str,
        query: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> dict[str, Any]:
        url = urllib.parse.urljoin(self.base_url, path.lstrip("/"))
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"
        request_headers = {
            "Accept": "application/json",
            "Accept-Language": "en",
            "OS": "Android",
            "OSVersion": "14",
            "DeviceModel": "Nice Gate local app",
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=body,
            headers=request_headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise MyNiceCloudError(f"HTTP {exc.code} from {path}: {details[:500]}") from exc
        except urllib.error.URLError as exc:
            raise MyNiceCloudError(f"Network error calling {path}: {exc}") from exc
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise MyNiceCloudError(f"Non-JSON response from {path}: {payload[:300]}") from exc
        if not isinstance(parsed, dict):
            raise MyNiceCloudError(f"Unexpected JSON response from {path}")
        return parsed

    @staticmethod
    def _basic_auth() -> str:
        raw = f"{CLIENT_ID}:{CLIENT_SECRET}".encode("utf-8")
        return "Basic " + base64.b64encode(raw).decode("ascii")

    @staticmethod
    def _token_from_response(data: dict[str, Any]) -> Token:
        access_token = data.get("access_token") or data.get("accessToken")
        if not access_token:
            raise MyNiceCloudError(f"Login response has no access token: {sorted(data.keys())}")
        return Token(
            access_token=str(access_token),
            token_type=str(data.get("token_type") or data.get("tokenType") or "Bearer"),
            refresh_token=_optional_str(data.get("refresh_token") or data.get("refreshToken")),
            expires_in=_optional_int(data.get("expires_in") or data.get("expiresIn")),
        )


def extract_accessory_credentials(payload: dict[str, Any]) -> list[AccessoryCredential]:
    found: list[AccessoryCredential] = []
    metadata_by_mac = _collect_accessory_metadata(payload)

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            credentials = obj.get("accessoryCredentials")
            if isinstance(credentials, list):
                for cred in credentials:
                    item = _credential_from_device(obj, cred)
                    if item:
                        metadata = metadata_by_mac.get(_norm_mac(item.device_id))
                        if metadata:
                            item = replace(
                                item,
                                product_type=item.product_type or metadata.get("product_type"),
                                name=item.name or metadata.get("name"),
                                home_id=item.home_id or metadata.get("home_id"),
                                permission=item.permission or metadata.get("permission"),
                                maintenance_state=item.maintenance_state
                                or metadata.get("maintenance_state"),
                            )
                        found.append(item)
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)

    visit(payload)
    deduped: dict[tuple[str, str, str], AccessoryCredential] = {}
    for item in found:
        deduped[(item.device_id, item.nhk_username, item.nhk_controller_id)] = item
    return list(deduped.values())


def _credential_from_device(device: dict[str, Any], cred: Any) -> AccessoryCredential | None:
    if not isinstance(cred, dict):
        return None
    device_id = _first_str(
        cred,
        "accessoryMacAddress",
        "macAddress",
        "accessoryMac",
        "deviceID",
        "deviceId",
    ) or _first_str(
        device,
        "accessoryMacAddress",
        "macAddress",
        "accessoryMac",
        "deviceID",
        "deviceId",
        "mac",
    )
    nhk_username = _first_str(cred, "accessoryUser", "nhkUsername", "username")
    nhk_password = _first_str(cred, "accessoryPassword", "nhkPassword", "password")
    controller_id = _first_str(cred, "controllerID", "controllerId", "nhkControllerID")
    if not (device_id and nhk_username and nhk_password and controller_id):
        return None
    return AccessoryCredential(
        device_id=device_id,
        cloud_id=_first_str(device, "id", "smartDeviceId", "smartDeviceID", "cloudID"),
        nhk_username=nhk_username,
        nhk_password=nhk_password,
        nhk_controller_id=controller_id,
        product_type=_first_str(device, "productType", "product", "model"),
        name=_first_str(device, "automationName", "accessoryName", "name", "description", "desc"),
        home_id=_first_str(device, "homeId", "homeID"),
        permission=_first_str(device, "permission", "permissions", "permissionLevel"),
        maintenance_state=_first_str(device, "maintenanceState"),
    )


def _collect_accessory_metadata(payload: dict[str, Any]) -> dict[str, dict[str, str]]:
    metadata_by_mac: dict[str, dict[str, str]] = {}

    def remember(mac: str, data: dict[str, str | None]) -> None:
        key = _norm_mac(mac)
        if not key:
            return
        current = metadata_by_mac.setdefault(key, {})
        for name, value in data.items():
            if value and not current.get(name):
                current[name] = value

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            mac = _first_str(
                obj,
                "accessoryMacAddress",
                "macAddress",
                "accessoryMac",
                "deviceID",
                "deviceId",
                "mac",
            )
            if mac:
                remember(
                    mac,
                    {
                        "product_type": _first_str(obj, "productType", "product", "model"),
                        "name": _first_str(
                            obj,
                            "automationName",
                            "accessoryName",
                            "name",
                            "description",
                            "desc",
                        ),
                        "home_id": _first_str(obj, "homeId", "homeID"),
                        "permission": _first_str(obj, "permission", "permissions", "permissionLevel"),
                        "maintenance_state": _first_str(obj, "maintenanceState"),
                    },
                )
            for value in obj.values():
                visit(value)
        elif isinstance(obj, list):
            for value in obj:
                visit(value)

    visit(payload)
    return metadata_by_mac


def _norm_mac(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in value.lower() if ch in "0123456789abcdef")


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
