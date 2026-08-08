# Solis Cloud Monitoring v2.0.6

## Fixes

- Keep today's generation available overnight when SolisCloud reports the collector offline.
- Report the inverter offline when `collectorState` is offline, even if `currentState` remains stale at `generating`.
- Preserve the stale morning energy guard while the collector is online.
- Add regressions using the reporter's day/night field values.
