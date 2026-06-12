# Nice Gate for Home Assistant

Home Assistant custom integration for Nice MyNice / IT4WIFI gates.

This integration connects to a Nice gate through the MyNice cloud/NHK proxy, creates a Home Assistant gate entity, exposes live status, and provides optional action buttons and Yandex-friendly switch entities.

## Features

- Gate `cover` entity with open, close and stop.
- Live status polling: `open`, `closed`, `opening`, `closing`, `stopped`.
- Optional `button` entities for Nice T4 actions.
- Optional Yandex-friendly `switch` entities per action.
- Config flow and options flow in the Home Assistant UI.
- YAML import for unattended setup.

## HACS Install

1. Open HACS.
2. Open the three-dot menu.
3. Select `Custom repositories`.
4. Add repository:

```text
https://github.com/klim88/nice_gate
```

5. Category: `Integration`.
6. Install `Nice Gate`.
7. Restart Home Assistant.
8. Add the integration:

```text
Settings -> Devices & services -> Add integration -> Nice Gate
```

Enter your MyNice email and password. If your account has more than one device, select the gate.

## Entities

By default the integration creates:

- one `cover` entity for the gate;
- `button` entities for step, partial openings and experimental lighting;
- services for all known primary Nice T4 actions;
- live status polling every 10 seconds.

## Action Settings

Open:

```text
Settings -> Devices & services -> Nice Gate -> Configure -> Action buttons
```

For each Nice action you can configure:

- display name;
- whether to create a Home Assistant `button` entity;
- whether to create a Yandex-friendly `switch` entity.

Extended T4 actions are available as services and can be enabled as entities only when needed.

## Yandex Smart Home / Alice

For Yandex/Alice, enable `Create Yandex-friendly switch entity` for the actions you want to expose.

Recommended actions:

- gate open/close through the main `cover` entity or a Yandex scenario;
- `partial1` as the default wicket/gate pedestrian action;
- `partial2` and `partial3` only if you need additional partial-opening widths;
- `step` only if you intentionally use step-by-step control.

An optional package example is included:

```text
examples/home_assistant/nice_gate_yandex_package.yaml
```

Use it only if you prefer template proxy switches/scenarios instead of the built-in optional switch entities.

## YAML Import

UI setup is recommended, but YAML import is supported.

Add credentials to `/config/secrets.yaml`:

```yaml
mynice_username: your@email
mynice_password: your-password
```

Add this to `/config/configuration.yaml`:

```yaml
nice_gate:
  username: !secret mynice_username
  password: !secret mynice_password
  # Optional. If omitted, the first gate from the account is used.
  device_id: "AA:BB:CC:DD:EE:FF"
```

After restart, Home Assistant imports this into a normal config entry.

## Services

The integration exposes services under the `nice_gate` domain, including:

- `nice_gate.open`
- `nice_gate.close`
- `nice_gate.stop`
- `nice_gate.step`
- `nice_gate.partial1`
- `nice_gate.partial2`
- `nice_gate.partial3`
- `nice_gate.light_on`
- `nice_gate.light_toggle`
- `nice_gate.master_open`
- `nice_gate.master_close`
- `nice_gate.bluebus_enable`
- `nice_gate.bluebus_disable`

Each service accepts an optional `device_id` field. If omitted, the first loaded Nice Gate entry is used.

## Security Notes

- No MyNice credentials are stored in this repository.
- Home Assistant stores credentials in its normal config entry storage or reads them from `secrets.yaml` during YAML import.
- Examples use placeholder device IDs only.
