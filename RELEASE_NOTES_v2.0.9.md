# Solis Cloud Monitoring v2.0.9

## Fixes

- Reloading the integration discovers added inverters on the account, including those under another plant.
- Preserve saved devices when discovery fails, returns empty or invalid data, or omits an existing inverter.
- Keep the five-inverter limit without truncating the list or removing saved devices.
