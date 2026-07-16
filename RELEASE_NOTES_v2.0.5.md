# Solis Cloud Monitoring v2.0.5

## Fix

- Expand the conservative standby ceiling from 30 W to 40 W for the synchronized nighttime sample reported by SolisCloud (`20 W` AC, `39 W` DC, `35 W` PV1).
- Keep genuine low-light generation when DC/PV evidence reaches 50 W.
- Add a regression test using the exact post-restart field values.
