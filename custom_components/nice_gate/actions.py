from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


CONF_ACTION_OPTIONS = "action_options"
CONF_ACTION_NAME = "name"
CONF_ACTION_DASHBOARD = "dashboard"
CONF_ACTION_YANDEX = "yandex"


@dataclass(frozen=True)
class NiceGateAction:
    key: str
    default_name: str
    icon: str
    dashboard_default: bool = False
    yandex_default: bool = False
    yandex_turn_off_action: str | None = "close"

    @property
    def service(self) -> str:
        return self.key.replace("-", "_")


ACTIONS: tuple[NiceGateAction, ...] = (
    NiceGateAction("open", "Открыть", "mdi:gate-open", yandex_turn_off_action="close"),
    NiceGateAction("close", "Закрыть", "mdi:gate", yandex_turn_off_action="open"),
    NiceGateAction("stop", "Стоп", "mdi:stop-circle-outline", yandex_turn_off_action=None),
    NiceGateAction("step", "Пошагово", "mdi:gesture-tap-button", dashboard_default=True),
    NiceGateAction("partial1", "Калитка", "mdi:walk", dashboard_default=True),
    NiceGateAction("partial2", "Калитка 2", "mdi:walk", dashboard_default=True),
    NiceGateAction("partial3", "Калитка 3", "mdi:walk", dashboard_default=True),
    NiceGateAction("light-on", "Свет вкл", "mdi:lightbulb-on", dashboard_default=True, yandex_turn_off_action="light-toggle"),
    NiceGateAction(
        "light-toggle",
        "Свет переключить",
        "mdi:lightbulb-auto",
        dashboard_default=True,
        yandex_turn_off_action="light-toggle",
    ),
    NiceGateAction("apartment-step", "Apartment step", "mdi:home-export-outline"),
    NiceGateAction("hp-step", "HP step", "mdi:gesture-tap-button"),
    NiceGateAction("open-block", "Open block", "mdi:lock-open-outline"),
    NiceGateAction("close-block", "Close block", "mdi:lock-outline"),
    NiceGateAction("block", "Block", "mdi:lock"),
    NiceGateAction("release", "Release", "mdi:lock-open-variant-outline"),
    NiceGateAction("master-step", "Master step", "mdi:gate-arrow-right"),
    NiceGateAction("master-open", "Master open", "mdi:gate-open"),
    NiceGateAction("master-close", "Master close", "mdi:gate"),
    NiceGateAction("slave-step", "Slave step", "mdi:gate-arrow-right"),
    NiceGateAction("slave-open", "Slave open", "mdi:gate-open"),
    NiceGateAction("slave-close", "Slave close", "mdi:gate"),
    NiceGateAction("release-open", "Release open", "mdi:lock-open-check-outline"),
    NiceGateAction("release-close", "Release close", "mdi:lock-check-outline"),
    NiceGateAction("bluebus-enable", "BlueBUS enable", "mdi:lan-connect"),
    NiceGateAction("bluebus-disable", "BlueBUS disable", "mdi:lan-disconnect"),
)

ACTION_BY_KEY = {action.key: action for action in ACTIONS}
ACTION_BY_SERVICE = {action.service: action for action in ACTIONS}


def normalize_action_options(options: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    raw_actions = {}
    if options:
        value = options.get(CONF_ACTION_OPTIONS)
        if isinstance(value, Mapping):
            raw_actions = value

    normalized: dict[str, dict[str, Any]] = {}
    for action in ACTIONS:
        raw = raw_actions.get(action.key, {})
        if not isinstance(raw, Mapping):
            raw = {}
        normalized[action.key] = {
            CONF_ACTION_NAME: str(raw.get(CONF_ACTION_NAME) or action.default_name),
            CONF_ACTION_DASHBOARD: bool(raw.get(CONF_ACTION_DASHBOARD, action.dashboard_default)),
            CONF_ACTION_YANDEX: bool(raw.get(CONF_ACTION_YANDEX, action.yandex_default)),
        }
    return normalized


def configured_name(options: Mapping[str, Any] | None, action: NiceGateAction) -> str:
    return normalize_action_options(options)[action.key][CONF_ACTION_NAME]


def dashboard_actions(options: Mapping[str, Any] | None) -> list[NiceGateAction]:
    config = normalize_action_options(options)
    return [action for action in ACTIONS if config[action.key][CONF_ACTION_DASHBOARD]]


def yandex_actions(options: Mapping[str, Any] | None) -> list[NiceGateAction]:
    config = normalize_action_options(options)
    return [action for action in ACTIONS if config[action.key][CONF_ACTION_YANDEX]]

