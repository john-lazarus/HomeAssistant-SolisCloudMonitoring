# Solis Cloud Monitoring

Home Assistant integration for Solis Cloud string inverters. It polls the Solis Cloud v2 API on a fixed schedule and exposes production and diagnostic telemetry as sensors.

## Features
- Polls the Solis Cloud `inverterDetail` endpoint every 60 seconds
- Discovers up to five inverters linked to the API user automatically
- Provides ready-to-use energy, power, PV string, grid, and diagnostic sensors
- Creates Home Assistant devices populated with model, firmware, and serial metadata

## Requirements
- Home Assistant 2024.8 or newer
- Solis Cloud API key and secret with access to the target station
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
Report issues at the GitHub repository and include debug logs from `custom_components.solis_cloud_monitoring` when filing a ticket.
