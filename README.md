# Solis Cloud Monitoring

Home Assistant integration for Solis Cloud string inverters. It polls the Solis Cloud v2 API on a fixed schedule and exposes production and diagnostic telemetry as sensors. Tested with an S6-GR1P5K-S (model 0115) inverter running on a Solis Cloud account with API access enabled.

## Features
- Polls the Solis Cloud `inverterDetail` endpoint every 60 seconds
- Discovers up to five inverters linked to the API user automatically
- Provides ready-to-use energy, power, PV string, grid, and diagnostic sensors
- Creates Home Assistant devices populated with model, firmware, and serial metadata
- Validated against S6-GR1P5K-S hardware; open an issue with an API data dump if you need support for additional models.

## Requirements
- Home Assistant 2024.8 or newer
- Solis Cloud API key and secret with access to the target station (see API access prerequisites below)
- Reliable internet access from the Home Assistant host

## Installation

### HACS (recommended)
1. In HACS, open `Integrations` → overflow menu → `Custom repositories`.
2. Add `https://github.com/john-lazarus/HomeAssistant-SolisCloudMonitoring` as type `Integration`.
3. Install **Solis Cloud Monitoring** from the HACS integration catalog.
4. Restart Home Assistant.

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
- You must enable API access on your Solis Cloud account at https://www.soliscloud.com/.
- Submit a ticket at https://solis-service.solisinverters.com/en/support/tickets/new using an account on the Solis Support Center (separate from the Solis Cloud login).
- After approval you receive an API key, secret, and base URL. The integration currently expects `https://www.soliscloud.com:13333/`; if your account is provisioned on a different host, open an issue and include the URL so compatibility can be added.

## Entity naming
Sensors follow the pattern `sensor.solis_<last4serial>_<sensor_key>`, for example `sensor.solis_7177_current_power`. Each inverter appears as a separate device with manufacturer and firmware details.

## Available sensors
- `current_power` kW (AC output)
- `dc_power` kW (DC input)
- `energy_today`, `energy_month` kWh
- `energy_year`, `energy_total` MWh
- `pv1_voltage` V, `pv1_current` A, `pv1_power` W
- `grid_voltage` V, `grid_current` A, `grid_frequency` Hz
- `inverter_temperature` °C
- `daily_runtime` hours
- `inverter_state` enum (offline, standby, generating)

## Energy Dashboard
Add `sensor.solis_<serial>_energy_today` to the Solar Production slot. The sensor already exposes the proper device and state classes for the Energy Dashboard.

## Troubleshooting
- `invalid_auth`: API key or secret rejected. Regenerate the credentials in Solis Cloud if needed.
- `cannot_connect`: Home Assistant could not reach the API. Check connectivity and review the HA logs.
- Empty inverter list: The API key must have access to a station with at least one active inverter.
- HTTP 429: Solis Cloud rate limit reached. Remove unused inverters or fork the integration to increase the poll interval.

## Support
Report issues at the GitHub repository and include debug logs from `custom_components.solis_cloud_monitoring` when filing a ticket. For new inverter models, attach a sanitized dump from `testing/solis_api_tester.py` so entity support can be assessed.

If this project helped you, please consider supporting my work:

<a href="https://www.buymeacoffee.com/trusmith" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" height="60" width="217"></a>
