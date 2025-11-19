# Solis Cloud Monitoring

Home Assistant integration for Solis Cloud string inverters. It polls the Solis Cloud v2 API on a fixed schedule and exposes production and diagnostic telemetry as sensors. Tested with an S6-GR1P5K-S (model 0115) inverter running on a Solis Cloud account with API access enabled.

I built this because I could not find a maintained Solis Cloud API integration for my own Luminous-badged hardware. If you are using a different Solis OEM brand, please open a GitHub issue with an API payload sample and I will gladly look at adding support.

I have been building this integration in my spare time, so if it helped you, please consider supporting my work:

<p>
	<a href="https://www.buymeacoffee.com/trusmith" target="_blank" rel="noreferrer">
		<img src="https://img.shields.io/badge/Buy%20Me%20A%20Coffee-donate-FFDD00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=000" alt="Buy Me A Coffee" />
	</a>
	<a href="https://paypal.me/johnlazarus1" target="_blank" rel="noreferrer">
		<img src="https://img.shields.io/badge/PayPal-donate-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate via PayPal" />
	</a>
	<a href="https://github.com/sponsors/john-lazarus" target="_blank" rel="noreferrer">
		<img src="https://img.shields.io/badge/Sponsor-GitHub-%23EA4AAA?style=for-the-badge&logo=github&logoColor=white" alt="Sponsor on GitHub" />
	</a>
</p>

## Features
- Polls the Solis Cloud `inverterDetail` endpoint every 60 seconds
- Discovers up to five inverters linked to the API user automatically
- Provides ready-to-use energy, power, PV string, grid, and diagnostic sensors
- Creates Home Assistant devices populated with model, firmware, and serial metadata
- Validated against S6-GR1P5K-S hardware; open an issue with an API data dump if you need support for additional models.

## Requirements
- Please make sure you run Home Assistant 2024.8 or newer.
- Solis Cloud API key and secret with access to the target station (see API access prerequisites below).
- Reliable internet access from the Home Assistant host.

## Installation

### HACS (recommended)

<a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=john-lazarus&repository=HomeAssistant-SolisCloudMonitoring&category=integration" target="_blank"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Open this repository in HACS" width="260"></a>

1. In HACS, please open `Integrations` → `+ Explore & Add Integrations`.
2. Search for **Solis Cloud Monitoring**, open the entry, and click `Download`.
3. Restart Home Assistant to load the integration.

### Manual copy
1. Please copy `custom_components/solis_cloud_monitoring` into `/config/custom_components/` on your Home Assistant instance.
2. Restart Home Assistant.

## Configuration
1. Please go to Settings → Devices & Services → Add Integration.
2. Search for **Solis Cloud Monitoring**.
3. Enter your Solis Cloud API key and API secret.
4. Complete the flow once the inverters attached to the account are validated.

All detected inverters are monitored. The update interval is fixed at 60 seconds, which keeps requests within the Solis Cloud limit for up to five inverters.

## API access prerequisites
- Please enable API access on your Solis Cloud account at https://www.soliscloud.com/.
- Submit a ticket at https://solis-service.solisinverters.com/en/support/tickets/new using an account on the Solis Support Center (separate from the Solis Cloud login).
- After approval you receive an API key, secret, and base URL. The integration currently expects `https://www.soliscloud.com:13333/`; if your account is provisioned on a different host, please open an issue and include the URL so compatibility can be added.

## Luminous-branded inverters
- Many Luminous grid-tied systems are white-labeled Solis units. Please use the global Solis Cloud portal (not the Luminous app) at https://www.soliscloud.com/ to register your logger stick and station.
- Bind the data-logger serial number (on the Wi-Fi/LAN stick) to the station after the plant shows up in Solis Cloud. The logger SN—not the inverter SN—is what ties the plant to your account.
- Once the station reports live data, please submit the API access request using the Solis Support Center account and mention that you are operating Luminous hardware on the Solis Cloud backend.
- Enter the granted API key/secret into the Home Assistant config flow. All sensors are surfaced using the Solis serials even if the casing says Luminous.
- Disclaimer: these steps reflect personal experience only. Luminous and Solis support teams might refuse API access or change the workflow, so please proceed at your own risk and confirm that doing so does not impact your warranty or support agreements.

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
