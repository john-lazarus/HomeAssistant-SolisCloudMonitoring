# HACS Default Store Submission Checklist

Use this file when submitting the repository to the HACS default store.

## Repository details
- Name: `Solis Cloud Monitoring`
- Domain: `solis_cloud_monitoring`
- Version: `1.0.1`
- Minimum Home Assistant version: `2024.8.0`

## Release
1. Verify the latest tag matches the manifest version.
2. Publish a GitHub release pointing to tag `v1.0.1` with notes summarising features and requirements.

## HACS default repository PR
1. Fork [`hacs/default`](https://github.com/hacs/default).
2. Add the repository to `repositories.json` under `integration`:

```json
{
  "name": "Solis Cloud Monitoring",
  "owners": ["john-lazarus"],
  "repo": "john-lazarus/HomeAssistant-SolisCloudMonitoring"
}
```

3. Commit the change with message `Add Solis Cloud Monitoring integration`.
4. Open a pull request referencing the release link and Home Assistant compatibility.
5. Wait for the HACS bot checks; respond to feedback if necessary.

## Validation commands
Run the following locally before submitting:

```bash
# Validate JSON
python -m json.tool hacs.json
python -m json.tool custom_components/solis_cloud_monitoring/manifest.json

# Ensure no untracked files
git status -sb
```

## Contact
For questions provide details via the issue tracker or mention `@john-lazarus` in the PR discussion.
