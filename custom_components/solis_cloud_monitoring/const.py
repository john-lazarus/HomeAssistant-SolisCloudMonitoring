"""Constants for the Solis Cloud Monitoring integration."""
from datetime import timedelta
from typing import Final

DOMAIN: Final = "solis_cloud_monitoring"

# Configuration
CONF_API_KEY: Final = "api_key"
CONF_API_SECRET: Final = "api_secret"
CONF_INVERTER_SERIALS: Final = "inverter_serials"

# API
API_BASE_URL: Final = "https://www.soliscloud.com:13333"
API_INVERTER_LIST: Final = "/v1/api/inverterList"
API_INVERTER_DETAIL: Final = "/v1/api/inverterDetail"

# Limits
MAX_INVERTERS: Final = 5
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=60)
MIN_SCAN_INTERVAL: Final = timedelta(seconds=30)
MAX_SCAN_INTERVAL: Final = timedelta(seconds=300)

# Device info
MANUFACTURER: Final = "Solis"
MODEL_PREFIX: Final = "S6-GR"

# Attribution
ATTRIBUTION: Final = "Data provided by Solis Cloud API"
