# Solis Cloud Monitoring v2.0.1

Small telemetry coverage update for v2.

## Changes

- Adds stationDetail fallback polling for station-level grid/load energy values.
- Keeps inverterDetail values authoritative by namespacing station-level fields internally.
- Adds PV string entities through PV24 for larger multi-string inverters.
- Makes battery power directional when battery current is available.
- Adds month/year grid import/export energy sensors.
- Adds focused tests for SolisCloud field mappings and unit fallbacks.

## Positioning

v2 stays deliberately lightweight: telemetry only, modern Home Assistant entity patterns, clear names, and no inverter-control surface.
