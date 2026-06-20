# Solis Cloud Monitoring v2.0.0

## Breaking hygiene release

This is a major v2 release with a new sensor model. It is intentionally breaking.

If your existing Home Assistant dashboards, automations, templates, or Energy Dashboard configuration depend on v1 entity names, do not upgrade until you are ready to migrate. v1.0.3 remains available for users who need the original entity model. Future enhancements and fixes will target v2.

## Why v2?

The original integration was built around a simple on-grid/string-inverter use case. Community PRs and the SolisCloud API V2.0.3 document made it clear that long-term support needs a cleaner model for:

- multi-PV-string systems
- hybrid/storage inverters
- battery telemetry
- home/backup/load telemetry
- grid import/export telemetry
- clearer Home Assistant Energy Dashboard mapping

v2 applies naming and unit hygiene now so future Solis support does not grow around ambiguous sensors.

## What is new

### Cleaner inverter production sensors

- `inverter_ac_power`
- `inverter_dc_power`
- `inverter_generation_today_energy`
- `inverter_generation_month_energy`
- `inverter_generation_year_energy`
- `inverter_generation_total_energy`
- `inverter_temperature`
- `inverter_daily_runtime`
- `inverter_state`

### PV String 2 support

- `pv2_voltage`
- `pv2_current`
- `pv2_power`

### Grid AC sensors

- `grid_l1_voltage/current`
- `grid_l2_voltage/current`
- `grid_l3_voltage/current`
- `grid_frequency`
- `grid_active_power`

### Battery/storage sensors for supported models

- `battery_soc`
- `battery_soh`
- `battery_power`
- `battery_voltage`
- `battery_current`
- battery charge/discharge today and total energy sensors

### Load/backup sensors for supported models

- `home_load_power`
- `total_load_power`
- `bypass_load_power`
- home load today/total energy
- backup load today/total energy

### Grid import/export sensors for supported models

- grid import today/total energy
- grid export today/total energy

## Existing values on unsupported models

Not every Solis model reports every field. Standard on-grid/string inverters may only populate inverter, PV, grid AC, and diagnostic sensors. Hybrid/storage/load sensors will only populate where SolisCloud returns those values.

Unsupported values should be unavailable/empty and should not break core inverter production monitoring.

## Night-time tiny production values

v2 includes conservative handling for tiny positive AC production values at night. If SolisCloud reports a very small positive `pac` value while PV/DC evidence also shows no generation, the integration reports inverter AC power as 0 W. This is intended to avoid phantom 0.02 kW production readings without hiding real low-light generation.

## Migration highlights

Common v1 to v2 replacements:

- `current_power` → `inverter_ac_power`
- `dc_power` → `inverter_dc_power`
- `energy_today` → `inverter_generation_today_energy`
- `energy_month` → `inverter_generation_month_energy`
- `energy_year` → `inverter_generation_year_energy`
- `energy_total` → `inverter_generation_total_energy`
- `grid_voltage` → `grid_l1_voltage`
- `grid_current` → `grid_l1_current`
- `daily_runtime` → `inverter_daily_runtime`

Some keys already had good names and remain conceptually the same, such as `pv1_power`, `grid_frequency`, `inverter_temperature`, and `inverter_state`.

## Please test and report

If a value looks wrong or a supported model does not populate a sensor, please open an issue or PR with:

- inverter model
- affected sensor
- expected value shown in SolisCloud
- a sanitized `/v1/api/inverterDetail` payload if possible

Please redact serial numbers, station IDs, collector IDs, user IDs, location, API keys, signatures, and secrets. Keep telemetry field names and numeric values intact.

## Thanks

Thanks to the contributors who opened PRs for PV2 and hybrid battery/load telemetry. Those reports helped shape this v2 sensor model.
