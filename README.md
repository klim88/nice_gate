# Nice Gate for Home Assistant

Home Assistant custom integration for Nice MyNice / IT4WIFI gates.

This integration connects Nice MyNice / IT4WIFI gates to Home Assistant, creates a gate entity, exposes live status, and provides optional action buttons and Yandex-friendly switch entities.

Version `0.4.0` adds local LAN control for IT4WIFI modules. MyNice cloud is still used to authenticate and read NHK credentials, but gate status and commands can run directly against the IT4WIFI module inside your local network.

## Features

- Gate `cover` entity with open, close and stop.
- Live status polling: `open`, `closed`, `opening`, `closing`, `stopped`.
- Connection modes:
  - `cloud`: original MyNice/NHK relay behavior.
  - `local_first`: use the local IT4WIFI address first, then fall back to cloud if local access fails.
  - `local_only`: use only the local IT4WIFI address for gate communication.
- Optional `button` entities for Nice T4 actions.
- Optional Yandex-friendly `switch` entities per action.
- `device_tracker` entity for the gate location on Home Assistant maps, when the controller reports coordinates.
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

## Local IT4WIFI Mode

Open:

```text
Settings -> Devices & services -> Nice Gate -> Configure -> Connection mode
```

Available modes:

- `Cloud only`: always use the MyNice/NHK relay.
- `Local first, cloud fallback`: use the LAN IT4WIFI address first, then try cloud if the local path fails.
- `Local only`: use the LAN IT4WIFI address only for gate communication.

For local modes, set:

- Local host: the IT4WIFI IP address or hostname, for example `192.168.1.50`.
- Local port: usually `443`.

Notes:

- The integration still uses the MyNice account during setup/session creation to obtain NHK credentials.
- Once a Home Assistant session is running, `local_first` and `local_only` can send status and commands directly over LAN.
- If Home Assistant is restarted while the Internet is unavailable, the integration may not be able to create a fresh session until MyNice credentials can be read again.
- `local_first` is recommended because it keeps local control as the primary path while preserving cloud fallback.

## Entities

By default the integration creates:

- one `cover` entity for the gate;
- one `device_tracker` entity for the gate location, if coordinates are available from the Nice status response;
- `button` entities for step, partial openings and experimental lighting;
- services for all known primary Nice T4 actions;
- live status polling every 30 seconds.

The main gate entity includes diagnostic attributes such as:

- `raw_status`
- `transport`: `local` or `cloud`
- `connection_mode`: configured connection mode
- `last_status_error`

## Home Assistant Map

The integration reads the location reported by the Nice controller and exposes it as a `device_tracker` entity.
Home Assistant's standard Map dashboard can display this entity as a marker. The marker is informational; gate control remains on the main `cover` entity.

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
- Local host examples use documentation-only private IP addresses and are not hardcoded defaults.
