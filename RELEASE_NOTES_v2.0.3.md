# Solis Cloud Monitoring v2.0.3

## Fixes

- Suppress the phantom `0.02 kW` standby reading when SolisCloud reports matching low AC/DC power without PV string generation.
- Keep legitimate low-light production when the DC and PV string values show real generation.
- Add regression coverage for both cases.
