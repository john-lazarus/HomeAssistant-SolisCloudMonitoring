"""Config flow for Solis Cloud Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolisCloudAPI, SolisCloudAPIError
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_INVERTER_SERIALS,
    DOMAIN,
    MAX_INVERTERS,
)

_LOGGER = logging.getLogger(__name__)


async def validate_api_credentials(
    hass: HomeAssistant, api_key: str, api_secret: str
) -> list[dict[str, Any]]:
    """Validate API credentials by fetching inverter list.
    
    Args:
        hass: Home Assistant instance
        api_key: Solis Cloud API key
        api_secret: Solis Cloud API secret
        
    Returns:
        List of inverters found
        
    Raises:
        SolisCloudAPIError: If credentials are invalid or connection fails
    """
    session = async_get_clientsession(hass)
    api = SolisCloudAPI(api_key, api_secret, session)
    
    inverters = await api.get_inverter_list()
    
    if not inverters:
        raise SolisCloudAPIError("No inverters found on this account")
    
    if len(inverters) > MAX_INVERTERS:
        raise SolisCloudAPIError(
            f"Too many inverters ({len(inverters)}). Maximum supported: {MAX_INVERTERS}"
        )
    
    return inverters


class SolisCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solis Cloud Monitoring."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                inverters = await validate_api_credentials(
                    self.hass,
                    user_input[CONF_API_KEY],
                    user_input[CONF_API_SECRET],
                )

                # Create unique ID from API key to prevent duplicates
                await self.async_set_unique_id(user_input[CONF_API_KEY])
                self._abort_if_unique_id_configured()

                # Store inverter serials for entry
                inverter_serials = [inv.get("sn") for inv in inverters if inv.get("sn")]
                
                return self.async_create_entry(
                    title="Solis Cloud Monitoring",
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_API_SECRET: user_input[CONF_API_SECRET],
                        CONF_INVERTER_SERIALS: inverter_serials,
                    },
                )

            except SolisCloudAPIError as err:
                _LOGGER.error("Failed to validate credentials: %s", err)
                if "Z0001" in str(err):
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during setup")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_API_SECRET): str,
                }
            ),
            errors=errors,
        )
