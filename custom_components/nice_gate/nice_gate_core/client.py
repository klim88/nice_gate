from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from typing import Literal

from .cloud import AccessoryCredential, MyNiceCloud, extract_accessory_credentials
from .nhk import NHKClient, NHKError, parse_nhk_error


GateCommand = Literal[
    "open",
    "stop",
    "close",
    "step",
    "partial1",
    "partial2",
    "partial3",
    "light-on",
    "light-toggle",
]

REMOTE_HOST = "integration.niceappdomain.com"
REMOTE_PORT = 7890


@dataclass(frozen=True)
class GateDevice:
    index: int
    device_id: str
    cloud_id: str | None
    name: str | None
    product_type: str | None
    home_id: str | None
    permission: str | None
    maintenance_state: str | None

    def as_dict(self) -> dict[str, str | int | None]:
        return asdict(self)


@dataclass(frozen=True)
class GateStatus:
    status: str
    obstruct: str
    device_event: str
    interface_event: str
    timestamp: str
    raw_xml: str | None = None

    def as_dict(self, include_raw: bool = False) -> dict[str, str | None]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw_xml", None)
        return data


@dataclass(frozen=True)
class GateInfo:
    type: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    description: str | None = None
    version_hardware: str | None = None
    version_firmware: str | None = None
    serial: str | None = None
    raw_xml: str | None = None

    def as_dict(self, include_raw: bool = False) -> dict[str, str | None]:
        data = asdict(self)
        if not include_raw:
            data.pop("raw_xml", None)
        return data


class NiceGateSession:
    def __init__(
        self,
        credentials: list[AccessoryCredential],
        host: str = REMOTE_HOST,
        port: int = REMOTE_PORT,
        timeout: float = 12.0,
    ) -> None:
        self.credentials = credentials
        self.host = host
        self.port = int(port)
        self.timeout = timeout

    @classmethod
    def login(cls, username: str, password: str, timeout: float = 12.0) -> "NiceGateSession":
        cloud = MyNiceCloud()
        token = cloud.login(username, password)
        credentials = extract_accessory_credentials(cloud.macro_user_data(token))
        if not credentials:
            raise RuntimeError("No Nice accessories were found in this MyNice account")
        return cls(credentials=credentials, timeout=timeout)

    def devices(self) -> list[GateDevice]:
        return [
            GateDevice(
                index=index,
                device_id=credential.device_id,
                cloud_id=credential.cloud_id,
                name=credential.name,
                product_type=credential.product_type,
                home_id=credential.home_id,
                permission=credential.permission,
                maintenance_state=credential.maintenance_state,
            )
            for index, credential in enumerate(self.credentials)
        ]

    def status(self, device_index: int = 0, device_id: int = 1, include_raw: bool = False) -> GateStatus:
        credential = self._credential(device_index)
        with self._connected_client(credential) as client:
            return parse_status(client.status(), device_id=device_id, include_raw=include_raw)

    def info(self, device_index: int = 0, include_raw: bool = False) -> GateInfo:
        credential = self._credential(device_index)
        with self._connected_client(credential) as client:
            return parse_info(client.info(), include_raw=include_raw)

    def command(
        self,
        action: GateCommand | str,
        device_index: int = 0,
        device_id: int = 1,
        include_raw: bool = False,
    ) -> dict[str, object]:
        credential = self._credential(device_index)
        with self._connected_client(credential) as client:
            response = client.change(device_id=device_id, t4_action=action)
            code, info = parse_nhk_error(response)
            if code:
                raise RuntimeError(f"NHK command failed with code {code}: {info or ''}".rstrip())
            status_error = None
            try:
                status = parse_status(client.status(), device_id=device_id, include_raw=include_raw)
                status_data = status.as_dict(include_raw=include_raw)
            except NHKError as exc:
                status_data = None
                status_error = str(exc)
            return {
                "ok": True,
                "action": action,
                "response_xml": response if include_raw else None,
                "status": status_data,
                "status_error": status_error,
            }

    def _credential(self, index: int) -> AccessoryCredential:
        if index < 0 or index >= len(self.credentials):
            raise IndexError(f"Device index {index} is out of range")
        return self.credentials[index]

    def _connected_client(self, credential: AccessoryCredential) -> "_ConnectedClient":
        return _ConnectedClient(
            credential=credential,
            host=self.host,
            port=self.port,
            timeout=self.timeout,
        )


class _ConnectedClient:
    def __init__(
        self,
        credential: AccessoryCredential,
        host: str,
        port: int,
        timeout: float,
    ) -> None:
        self.credential = credential
        self.host = host
        self.port = port
        self.timeout = timeout
        self.client: NHKClient | None = None

    def __enter__(self) -> NHKClient:
        self.client = NHKClient(self.host, self.port, timeout=self.timeout)
        self.client.open()
        self._connect_with_retry(self.client)
        return self.client

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client:
            self.client.close()

    def _connect_with_retry(self, client: NHKClient, attempts: int = 4) -> None:
        last_exc: NHKError | None = None
        for attempt in range(1, attempts + 1):
            try:
                client.connect_session(
                    username=self.credential.nhk_username,
                    app_udid=self.credential.nhk_controller_id,
                    target=self.credential.device_id,
                    pairing_password=self.credential.nhk_password,
                    gw_id=self.credential.cloud_id or "",
                )
                return
            except NHKError as exc:
                last_exc = exc
                if "Empty NHK response" not in str(exc) or attempt >= attempts:
                    raise
                client.close()
                time.sleep(0.5)
                client.open()
        if last_exc:
            raise last_exc


def parse_status(xml: str, device_id: int = 1, include_raw: bool = False) -> GateStatus:
    root = _parse_xml(xml)
    device = _find_device(root, device_id)
    return GateStatus(
        status=_child_text(device, "DoorStatus"),
        obstruct=_child_text(device, "Obstruct"),
        device_event=_last_event(device),
        interface_event=_interface_last_event(root),
        timestamp=_first_text(root, "Date"),
        raw_xml=xml if include_raw else None,
    )


def parse_info(xml: str, include_raw: bool = False) -> GateInfo:
    root = _parse_xml(xml)
    device = _first_element(root, "Device")
    return GateInfo(
        type=_maybe_child_text(device, "Type"),
        manufacturer=_maybe_child_text(device, "Manuf"),
        product=_maybe_child_text(device, "Prod"),
        description=_maybe_child_text(device, "Desc"),
        version_hardware=_maybe_child_text(device, "VersionHW"),
        version_firmware=_maybe_child_text(device, "VersionFW"),
        serial=_maybe_child_text(device, "SerialNr"),
        raw_xml=xml if include_raw else None,
    )


def _parse_xml(xml: str) -> ET.Element:
    try:
        return ET.fromstring(xml)
    except ET.ParseError as exc:
        raise RuntimeError(f"Could not parse NHK XML: {xml[:300]}") from exc


def _find_device(root: ET.Element, device_id: int) -> ET.Element:
    target = str(device_id)
    for child in root.iter():
        if _tag(child) == "Device" and (child.get("id") == target or child.get("id") is None):
            return child
    raise RuntimeError(f"Device id {device_id} not found in NHK response")


def _first_element(root: ET.Element, name: str) -> ET.Element | None:
    for child in root.iter():
        if _tag(child) == name:
            return child
    return None


def _child_text(root: ET.Element, name: str, default: str = "unknown") -> str:
    value = _maybe_child_text(root, name)
    return value if value is not None else default


def _maybe_child_text(root: ET.Element | None, name: str) -> str | None:
    if root is None:
        return None
    for child in root.iter():
        if _tag(child) == name:
            return (child.text or "").strip() or None
    return None


def _first_text(root: ET.Element, name: str, default: str = "") -> str:
    value = _maybe_child_text(root, name)
    return value if value is not None else default


def _last_event(root: ET.Element | None) -> str:
    if root is None:
        return "unknown"
    for child in root.iter():
        if _tag(child) == "LastEvent":
            return (child.text or "").strip() or "unknown"
    return "unknown"


def _interface_last_event(root: ET.Element) -> str:
    interface = _first_element(root, "Interface")
    return _last_event(interface)


def _tag(element: ET.Element) -> str:
    return element.tag.split("}", 1)[-1]
