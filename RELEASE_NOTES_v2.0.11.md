# Solis Cloud Monitoring v2.0.11

- Fix duplicate and simultaneous setup attempts showing an unexpected error instead of the normal Home Assistant message. These checks now happen before contacting SolisCloud, with a further check before saving the entry.
- Distinguish API access errors, timeouts, server errors, rate limiting, empty accounts and malformed responses during setup and reconfiguration.
- Stop including raw SolisCloud response bodies in API error messages. Validate inverter and station detail responses before passing them to the coordinator.
- Add API boundary tests and config-flow regressions using real Home Assistant helpers.

Update through HACS and restart Home Assistant. Existing credentials, inverter selections and entity IDs are unchanged. There is no storage migration or manual cleanup required.

This release fixes error handling. It does not claim to fix upstream HTTP 502s, DNS failures, or logger disconnections. Polling frequency and the bounded stale-data policy are unchanged. The integration remains cloud-based and read-only.
