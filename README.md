# Solis Cloud Monitoring

A Home Assistant integration for reading inverter data from Solis Cloud.

It polls Solis Cloud every 60 seconds and creates normal Home Assistant sensors for each inverter it finds. It is read-only: there are no inverter controls in this integration.

<p align="center">
  <a href="https://buymeacoffee.com/trusmith">
    <img src="https://cdn.buymeacoffee.com/buttons/v2/arial-orange.png" alt="Buy Me a Coffee" height="41">
  </a>
</p>

## Install with HACS

[![Open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=john-lazarus&repository=HomeAssistant-SolisCloudMonitoring&category=integration)

1. Open HACS in Home Assistant.
2. Go to **Integrations** and search for **Solis Cloud Monitoring**.
3. Download it and restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Search for **Solis Cloud Monitoring** and enter your Solis Cloud API details.

Manual installation is also possible. Copy `custom_components/solis_cloud_monitoring` into your Home Assistant `config/custom_components` directory, restart Home Assistant, and add the integration from Settings.

## Before setup

You need:

- Home Assistant 2024.8 or newer
- A Solis Cloud account with API access enabled
- The Solis Cloud API key and secret for the station you want to monitor

API access is not enabled on every Solis Cloud account by default. If you do not have credentials yet, request access through the [Solis Support Center](https://solis-service.solisinverters.com/en/support/tickets/new). The integration currently uses the standard Solis Cloud API endpoint at `https://www.soliscloud.com:13333/`.

## What it creates

The integration discovers the inverters linked to the API account and creates one Home Assistant device per inverter. It supports up to five inverters per account.

The exact sensors depend on what the inverter reports. Depending on the model, you may get:

- AC and DC power
- Generation today, this month, this year, and total
- PV string voltage, current, and power
- Grid voltage, current, frequency, and active power
- Battery state of charge, voltage, current, power, and charge/discharge energy
- Home, total, bypass, and backup load
- Grid import and export energy
- Inverter temperature, runtime, state, and logger/collector status

If Solis Cloud does not provide a value for a particular inverter, that sensor will be unavailable. That is normal and should not stop the rest of the device from updating.

For the Home Assistant Energy Dashboard, use the lifetime energy sensors when the inverter provides them. For example:

- `inverter_generation_total_energy`
- `grid_import_total_energy`
- `grid_export_total_energy`
- `battery_charge_total_energy`
- `battery_discharge_total_energy`

Entity IDs use the inverter's logger or serial suffix, for example:

```text
sensor.solis_7177_inverter_ac_power
```

## Updating from version 1

Version 2 uses more specific entity names. It is a breaking change for dashboards and automations that use the old names.

Common replacements include:

```text
current_power  → inverter_ac_power
energy_today   → inverter_generation_today_energy
energy_total   → inverter_generation_total_energy
grid_voltage   → grid_l1_voltage
```

Update any dashboards, automations, or Energy Dashboard settings that refer to the old entities before upgrading.

## Luminous-branded inverters

Some Luminous inverters use the Solis platform underneath. Use the global [Solis Cloud portal](https://www.soliscloud.com/), not the Luminous app, when registering the logger and requesting API access.

The logger serial number is what links the plant to the Solis Cloud account. It may be different from the inverter serial number.

## If something looks wrong

Please open an [issue](https://github.com/john-lazarus/HomeAssistant-SolisCloudMonitoring/issues) and include:

- Inverter model
- The affected entity name
- The value shown in Home Assistant and the value shown in Solis Cloud
- A redacted `inverterDetail` payload, if possible
- Relevant Home Assistant logs from `custom_components.solis_cloud_monitoring`

Please remove serial numbers, station IDs, logger IDs, user IDs, locations, API keys, signatures, and other credentials. Keep the field names and numeric telemetry values; those are what make the problem diagnosable.

## Links

- [Issues](https://github.com/john-lazarus/HomeAssistant-SolisCloudMonitoring/issues)
- [Releases](https://github.com/john-lazarus/HomeAssistant-SolisCloudMonitoring/releases)
- [Solis Cloud](https://www.soliscloud.com/)
