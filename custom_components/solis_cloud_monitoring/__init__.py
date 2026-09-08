"""The Solis Cloud Monitoring integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolisCloudAPI, SolisCloudAPIError
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_INVERTER_SERIALS,
    DOMAIN,
    MAX_INVERTERS,
)
from .coordinator import SolisCloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solis Cloud Monitoring from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    inverter_serials = entry.data[CONF_INVERTER_SERIALS]

    # Create API client
    session = async_get_clientsession(hass)
    api = SolisCloudAPI(api_key, api_secret, session)

    # Rediscover on setup/reload, retaining devices missing from this response.
    try:
        inverters = await api.get_inverter_list()
    except SolisCloudAPIError:
        _LOGGER.debug("Inverter discovery unavailable; retaining configured devices")
    else:
        discovered_serials = list(
            dict.fromkeys(inverter_serials + [inv["sn"] for inv in inverters])
        )
        if len(discovered_serials) > MAX_INVERTERS:
            _LOGGER.warning(
                "Inverter discovery exceeds the supported limit of %d; "
                "retaining configured devices",
                MAX_INVERTERS,
            )
        elif discovered_serials != inverter_serials:
            inverter_serials = discovered_serials
            hass.config_entries.async_update_entry(
                entry, data={**entry.data, CONF_INVERTER_SERIALS: inverter_serials}
            )

    # Create coordinator
    coordinator = SolisCloudDataUpdateCoordinator(
        hass,
        api,
        inverter_serials,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
