from __future__ import annotations

import base64
import hashlib
import html
import random
import re
import socket
import ssl
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


T4_ACTION_CODE = {
    "step": "MDAx",
    "step-by-step": "MDAx",
    "sbs": "MDAx",
    "stop": "MDAy",
    "stop-remote": "MDAy",
    "open": "MDAz",
    "open-remote": "MDAz",
    "close": "MDA0",
    "close-remote": "MDA0",
    "partial1": "MDA1",
    "partial2": "MDA2",
    "partial3": "MDA3",
    "apartment-step": "MDBi",
    "hp-step": "MDBj",
    "open-block": "MDBk",
    "close-block": "MDBl",
    "block": "MDBm",
    "release": "MDEw",
    "light-on": "MDEx",
    "light-toggle": "MDEy",
    "master-step": "MDEz",
    "master-open": "MDE0",
    "master-close": "MDE1",
    "slave-step": "MDE2",
    "slave-open": "MDE3",
    "slave-close": "MDE4",
    "release-open": "MDE5",
    "release-close": "MDFh",
    "bluebus-enable": "MDFi",
    "bluebus-disable": "MDFj",
}

STX = b"\x02"
ETX = b"\x03"
_GLOBAL_COUNTER = 1


class NHKError(RuntimeError):
    pass


@dataclass(frozen=True)
class NHKSession:
    session_id: int
    session_password: bytes
    username: str
    source: str
    target: str
    gw_id: str = ""


class NHKClient:
    def __init__(self, host: str, port: int, timeout: float = 12.0) -> None:
        self.host = host
        self.port = int(port)
        self.timeout = timeout
        self._sock: ssl.SSLSocket | None = None
        self._recv_buffer = b""
        self.session: NHKSession | None = None

    def __enter__(self) -> "NHKClient":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        raw = socket.create_connection((self.host, self.port), timeout=self.timeout)
        raw.settimeout(self.timeout)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self._sock = context.wrap_socket(raw, server_hostname=self.host)

    def close(self) -> None:
        if self._sock:
            self._sock.close()
            self._sock = None

    def connect_session(
        self,
        username: str,
        app_udid: str,
        target: str,
        pairing_password: str,
        gw_id: str = "",
    ) -> str:
        response, client_challenge = self.connect_exchange(
            username=username,
            app_udid=app_udid,
            target=target,
            gw_id=gw_id,
        )
        auth = _find_child(ET.fromstring(response), "Authentication")
        if auth is None:
            raise NHKError(f"CONNECT response has no Authentication: {response[:300]}")
        server_challenge = auth.attrib.get("sc")
        session_id = auth.attrib.get("id")
        if not server_challenge or not session_id:
            raise NHKError(f"CONNECT response missing sc/id: {response[:300]}")
        session_password = _sha256(
            _hex_to_bytes(pairing_password),
            _invert(_hex_to_bytes(server_challenge)),
            _invert(_hex_to_bytes(client_challenge)),
        )
        self.session = NHKSession(
            session_id=int(session_id),
            session_password=session_password,
            username=username,
            source=app_udid,
            target=target,
            gw_id=gw_id,
        )
        return response

    def connect_exchange(
        self,
        username: str,
        app_udid: str,
        target: str,
        gw_id: str = "",
    ) -> tuple[str, str]:
        client_challenge = _next_hex_int()
        msg_id = _next_msg_id(None)
        xml = build_connect_xml(
            msg_id=msg_id,
            username=username,
            app_udid=app_udid,
            target=target,
            gw_id=gw_id,
            client_challenge=client_challenge,
        )
        return self.send_xml(xml, None, expected_type="CONNECT"), client_challenge

    def info(self) -> str:
        return self._signed_request("INFO")

    def status(self) -> str:
        return self._signed_request("STATUS")

    def change(self, device_id: int, t4_action: str, normalize_action: bool = True) -> str:
        if not self.session:
            raise NHKError("NHK session is not open")
        if normalize_action:
            normalized = normalize_t4_action(t4_action)
            if normalized is None:
                raise NHKError(f"Unsupported T4 action: {t4_action!r}")
            t4_action = normalized
        return self._change_request(device_id=device_id, t4_action=t4_action)

    def _change_request(self, device_id: int, t4_action: str) -> str:
        if not self.session:
            raise NHKError("NHK session is not open")
        session = self.session
        msg_id = _next_msg_id(session.session_id)
        xml = build_change_xml(
            msg_id=msg_id,
            source=session.source,
            target=session.target,
            gw_id=session.gw_id,
            device_id=device_id,
            t4_action=t4_action,
        )
        return self.send_xml(xml, session.session_password, expected_type="CHANGE")

    def _signed_request(self, request_type: str) -> str:
        if not self.session:
            raise NHKError("NHK session is not open")
        session = self.session
        msg_id = _next_msg_id(session.session_id)
        xml = (
            f'<Request id="{msg_id}" protocolType="NHK" protocolVersion="1.0" '
            f'source="{_attr(session.source)}" target="{_attr(session.target)}" '
            f'type="{request_type}" gw="{_attr(session.gw_id)}">\n'
            f"<Sign></Sign>\n"
            f"</Request>"
        )
        return self.send_xml(xml, session.session_password, expected_type=request_type)

    def send_xml(
        self,
        xml: str,
        session_password: bytes | None,
        expected_type: str | None = None,
    ) -> str:
        if not self._sock:
            raise NHKError("Socket is not open")
        framed = format_message(xml, session_password).encode("utf-8")
        self._sock.sendall(framed)
        return self._recv_response(expected_type)

    def _recv_response(self, expected_type: str | None) -> str:
        deadline = time.monotonic() + self.timeout
        skipped: list[str] = []
        while time.monotonic() < deadline:
            message = self._recv_message(deadline)
            if expected_type is None:
                return message
            root_name, message_type = _root_name_and_type(message)
            if root_name == "Response" and message_type == expected_type:
                return message
            if root_name == "Event":
                skipped.append(message[:120])
                continue
            return message
        detail = f"; skipped events: {skipped}" if skipped else ""
        raise NHKError(f"Timed out waiting for NHK {expected_type} response{detail}")

    def _recv_message(self, deadline: float | None = None) -> str:
        if not self._sock:
            raise NHKError("Socket is not open")
        deadline = deadline or (time.monotonic() + self.timeout)
        previous_timeout = self._sock.gettimeout()
        while time.monotonic() < deadline:
            if ETX in self._recv_buffer:
                raw, self._recv_buffer = self._recv_buffer.split(ETX, 1)
                start = raw.find(STX)
                if start >= 0:
                    raw = raw[start + 1 :]
                text = raw.decode("utf-8", errors="replace").strip()
                if text:
                    return text
                continue
            remaining = max(0.1, deadline - time.monotonic())
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as exc:
                raise NHKError("Timed out waiting for NHK response") from exc
            finally:
                self._sock.settimeout(previous_timeout)
            if not chunk:
                break
            self._recv_buffer += chunk
        raise NHKError("Empty NHK response")


def normalize_t4_action(action: str) -> str | None:
    normalized = (action or "").strip().lower()
    if not normalized:
        return None
    return T4_ACTION_CODE.get(normalized) or action.strip()


def format_message(xml: str, session_password: bytes | None) -> str:
    normalized = html.unescape(xml)
    if "\r\n" not in normalized and "\n" in normalized:
        normalized = normalized.replace("\n", "\r\n")
    if session_password:
        normalized = _insert_signature(normalized, session_password)
    return "\x02" + normalized + "\x03"


def build_connect_xml(
    msg_id: int,
    username: str,
    app_udid: str,
    target: str,
    gw_id: str,
    client_challenge: str,
) -> str:
    # Attribute order and compact Authentication tag match the APK serializer.
    return (
        f'<Request gw="{_attr(gw_id)}" id="{msg_id}" protocolType="NHK" '
        f'protocolVersion="1.0" source="{_attr(app_udid)}" '
        f'target="{_attr(target)}" type="CONNECT">\n'
        f'<Authentication cc="{client_challenge}" username="{_attr(username)}"/>\n'
        f"</Request>"
    )


def build_change_xml(
    msg_id: int,
    source: str,
    target: str,
    gw_id: str,
    device_id: int,
    t4_action: str,
) -> str:
    return (
        f'<Request id="{msg_id}" protocolType="NHK" protocolVersion="1.0" '
        f'source="{_attr(source)}" target="{_attr(target)}" '
        f'type="CHANGE" gw="{_attr(gw_id)}">\n'
        f"<Devices>\n"
        f'<Device id="{int(device_id)}">\n'
        f"<Services>\n"
        f"<T4Action>{_attr(t4_action)}</T4Action>\n"
        f"</Services>\n"
        f"</Device>\n"
        f"</Devices>\n"
        f"<Sign></Sign>\n"
        f"</Request>"
    )


def parse_nhk_error(xml: str) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None, None
    for child in root.iter():
        if child.tag.split("}", 1)[-1] != "Error":
            continue
        code = None
        info = None
        for item in child:
            name = item.tag.split("}", 1)[-1]
            if name == "Code":
                code = (item.text or "").strip()
            elif name == "Info":
                info = (item.text or "").strip()
        return code, info
    return None, None


def _insert_signature(xml: str, session_password: bytes) -> str:
    for marker in ("<Sign></Sign>", "<Sign/>", "<Sign />"):
        index = xml.find(marker)
        if index > 0:
            prefix = xml[:index].encode("utf-8")
            signature = base64.b64encode(_sha256(_sha256(prefix), session_password)).decode("ascii")
            return xml.replace(marker, f"<Sign>{signature}</Sign>", 1)
    raise NHKError("Signed request has no empty Sign element")


def _next_msg_id(session_id: int | None) -> int:
    global _GLOBAL_COUNTER
    value = _GLOBAL_COUNTER
    _GLOBAL_COUNTER += 1
    if session_id is None:
        return value
    return (session_id & 255) | (value << 8)


def _next_hex_int() -> str:
    return f"{random.getrandbits(32):08X}"


def _sha256(*values: bytes) -> bytes:
    digest = hashlib.sha256()
    for value in values:
        digest.update(value)
    return digest.digest()


def _hex_to_bytes(value: str) -> bytes:
    compact = re.sub(r"[^0-9A-Fa-f]", "", value)
    if len(compact) % 2:
        compact = "0" + compact
    return bytes.fromhex(compact)


def _invert(value: bytes) -> bytes:
    return bytes(reversed(value))


def _attr(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _find_child(root: ET.Element, name: str) -> ET.Element | None:
    for child in root.iter():
        if child.tag.split("}", 1)[-1] == name:
            return child
    return None


def _root_name_and_type(xml: str) -> tuple[str | None, str | None]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None, None
    return root.tag.split("}", 1)[-1], root.attrib.get("type")
