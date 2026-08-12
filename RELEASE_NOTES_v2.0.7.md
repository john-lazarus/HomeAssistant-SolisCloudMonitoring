# Solis Cloud Monitoring v2.0.7

## Fixes

- Keep today's final generation total available while the collector transitions offline after sunset.
- Limit stale previous-day generation filtering to the morning inverter wake-up window.
- Add regression coverage for both the morning stale value and evening final total.