# Solis Cloud Monitoring v2.0.10

- Choose one to five inverters during setup, even when your SolisCloud account contains more.
- Change monitored inverters through Reconfigure without re-entering API credentials. The selection is preserved across reloads.
- Existing entries retain their discovery behaviour until you choose a selection; entity IDs are unchanged.

This fixes the account-size setup limit and unwanted-inverter polling in #23/#24. HTTP 502s and timeouts remain a separate investigation.
