# Solis Cloud Monitoring v2.0.4

## Fix

- Suppress the observed nighttime standby payload where SolisCloud reports `20 W` AC, `26 W` DC, and `22 W` of PV-string noise.
- Keep genuine low-light generation when DC/PV evidence rises above the 30 W standby range.
- Add a regression test for the field values seen in production.
