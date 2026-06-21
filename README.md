# Solis Cloud Monitoring

Home Assistant custom integration for Solis Cloud inverter telemetry.

## Important: v2.0.0 is a breaking hygiene release

Version 2.0.0 introduces a new, cleaner sensor model so the integration can support a wider range of Solis products over the long term: string/on-grid inverters, multi-PV-string systems, hybrid/storage models, and installations that expose battery/load/grid telemetry through SolisCloud.

If your current Home Assistant dashboards, automations, or Energy Dashboard configuration depend on v1 entity names, do **not** upgrade until you are ready to migrate. The v1.0.3 release remains available on GitHub for users who need the original entity model. Future enhancements and fixes will target v2.

## What changed in v2

The v1 integration used short, simple sensor keys such as `current_power`, `energy_total`, and `grid_voltage`. That worked for basic on-grid inverter monitoring, but it became ambiguous once hybrid/storage, PV2, load, and grid import/export support were requested.

v2 uses more explicit names:

- `inverter_ac_power` instead of generic `current_power`
- `inverter_generation_total_energy` instead of generic `energy_total`
- `grid_l1_voltage` instead of generic `grid_voltage`
- separate home/load/backup/grid import/export/battery sensors where SolisCloud exposes them

Unsupported model-specific values become unavailable/empty; they should not break existing production telemetry.

## Features

- Polls the Solis Cloud `/v1/api/inverterDetail` endpoint every 60 seconds, with `/v1/api/stationDetail` as a fallback source for station-level grid/load energy values.
- Discovers up to five inverters linked to the API user automatically.
- Supports clean v2 sensors for inverter production, PV strings, grid AC, battery/storage, load/backup, and grid import/export telemetry.
- Adds conservative night-noise handling for tiny phantom AC production values when PV/DC evidence indicates no generation.
- Creates Home Assistant devices populated with model, firmware, and serial metadata.

## Requirements

- Home Assistant 2024.8 or newer.
- Solis Cloud API key and secret with access to the target station.
- Reliable internet access from the Home Assistant host.

## Installation

### HACS recommended

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=john-lazarus&repository=HomeAssistant-SolisCloudMonitoring&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open this repository in HACS" width="260"></a>

1. In HACS, open `Integrations` → `+ Explore & Add Integrations`.
2. Search for **Solis Cloud Monitoring**, open the entry, and click `Download`.
3. Restart Home Assistant to load the integration.

### Manual copy

1. Copy `custom_components/solis_cloud_monitoring` into `/config/custom_components/` on your Home Assistant instance.
2. Restart Home Assistant.

## Configuration

1. Go to Settings → Devices & Services → Add Integration.
2. Search for **Solis Cloud Monitoring**.
3. Enter your Solis Cloud API key and API secret.
4. Complete the flow once the inverters attached to the account are validated.

All detected inverters are monitored. The update interval is fixed at 60 seconds, which keeps requests within the Solis Cloud limit for up to five inverters.

## API access prerequisites

- Enable API access on your Solis Cloud account at https://www.soliscloud.com/.
- Submit a ticket at https://solis-service.solisinverters.com/en/support/tickets/new using an account on the Solis Support Center.
- After approval you receive an API key, secret, and base URL. The integration currently expects `https://www.soliscloud.com:13333/`; if your account is provisioned on a different host, please open an issue and include the URL so compatibility can be added.

## Luminous-branded inverters

Many Luminous grid-tied systems are white-labeled Solis units. Use the global Solis Cloud portal, not the Luminous app, at https://www.soliscloud.com/ to register your logger stick and station.

Bind the data-logger serial number to the station after the plant appears in Solis Cloud. The logger SN, not the inverter SN, ties the plant to your account. Once the station reports live data, request API access through Solis Support and enter the granted API key/secret into the Home Assistant config flow.

Disclaimer: this reflects personal experience only. Luminous and Solis support teams may change the workflow or refuse API access.

## Entity naming

Sensors follow the pattern:

`sensor.solis_<last4serial>_<sensor_key>`

Example:

`sensor.solis_7177_inverter_ac_power`

Each inverter appears as a separate Home Assistant device with manufacturer, model, firmware, and serial metadata.

## v2 sensor model

### Inverter production

- `inverter_ac_power` W
- `inverter_dc_power` W
- `inverter_generation_today_energy` kWh
- `inverter_generation_month_energy` kWh
- `inverter_generation_year_energy` kWh
- `inverter_generation_total_energy` kWh
- `inverter_temperature` °C
- `inverter_daily_runtime` h
- `inverter_state` enum

### PV strings

- `pv1_voltage` V, `pv1_current` A, `pv1_power` W
- `pv2_voltage` V, `pv2_current` A, `pv2_power` W
- `pv3_*` through `pv24_*` are also created for larger multi-string inverters when SolisCloud reports those fields

### Grid AC

- `grid_l1_voltage` V, `grid_l1_current` A
- `grid_l2_voltage` V, `grid_l2_current` A
- `grid_l3_voltage` V, `grid_l3_current` A
- `grid_frequency` Hz
- `grid_active_power` W, when SolisCloud provides `pSum`/`psum`

### Battery / storage, supported models only

- `battery_soc` %
- `battery_soh` %
- `battery_power` W
- `battery_voltage` V
- `battery_current` A
- `battery_charge_today_energy` kWh
- `battery_charge_total_energy` kWh
- `battery_discharge_today_energy` kWh
- `battery_discharge_total_energy` kWh

### Load / backup, supported models only

- `home_load_power` W
- `total_load_power` W
- `bypass_load_power` W
- `home_load_today_energy` kWh
- `home_load_total_energy` kWh
- `backup_load_today_energy` kWh
- `backup_load_total_energy` kWh

### Grid import/export, supported models only

- `grid_import_today_energy` kWh
- `grid_import_month_energy` kWh
- `grid_import_year_energy` kWh
- `grid_import_total_energy` kWh
- `grid_export_today_energy` kWh
- `grid_export_month_energy` kWh
- `grid_export_year_energy` kWh
- `grid_export_total_energy` kWh

### Diagnostics

- `collector_state` enum

## Energy Dashboard guidance

For solar production, prefer the new total generation sensor where available:

`sensor.solis_<serial>_inverter_generation_total_energy`

For grid import/export or battery charge/discharge, prefer total lifetime energy sensors rather than daily counters when your inverter reports them.

Examples:

- Grid import: `grid_import_total_energy`
- Grid export: `grid_export_total_energy`
- Battery charge: `battery_charge_total_energy`
- Battery discharge: `battery_discharge_total_energy`

Daily counters are still exposed for visibility, but total counters are usually safer for long-term Home Assistant Energy Dashboard statistics.

## Migration from v1

v2 is intentionally breaking. Common replacements:

| v1 sensor key | v2 sensor key |
|---|---|
| `current_power` | `inverter_ac_power` |
| `dc_power` | `inverter_dc_power` |
| `energy_today` | `inverter_generation_today_energy` |
| `energy_month` | `inverter_generation_month_energy` |
| `energy_year` | `inverter_generation_year_energy` |
| `energy_total` | `inverter_generation_total_energy` |
| `grid_voltage` | `grid_l1_voltage` |
| `grid_current` | `grid_l1_current` |
| `grid_frequency` | `grid_frequency` |
| `daily_runtime` | `inverter_daily_runtime` |
| `inverter_state` | `inverter_state` |
| `inverter_temperature` | `inverter_temperature` |
| `pv1_voltage` | `pv1_voltage` |
| `pv1_current` | `pv1_current` |
| `pv1_power` | `pv1_power` |

If your dashboards or automations use v1 entity IDs, update them after installing v2.

## Troubleshooting and model support

Not every Solis inverter reports every field. On standard on-grid/string inverters, many battery/load/grid import/export sensors may remain unavailable. That is expected.

If a new sensor looks wrong or remains unavailable on a model that should support it, please open a GitHub issue or PR with:

- inverter model
- which sensor is wrong or unavailable
- expected value as shown in SolisCloud
- a sanitized `/v1/api/inverterDetail` payload if possible

Please redact serial numbers, station IDs, collector IDs, user IDs, location, API keys, signatures, and secrets, but leave telemetry field names and numeric values intact.

## Support

Report issues at the GitHub repository and include debug logs from `custom_components.solis_cloud_monitoring` when filing a ticket. For new inverter models, attach a sanitized dump from `testing/solis_api_tester.py` so entity support can be assessed.
