"""Config flow for Solis Cloud Monitoring integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SolisCloudAPI, SolisCloudAPIError
from .const import (
    CONF_API_KEY,
    CONF_API_SECRET,
    CONF_INVERTER_SELECTION_CONFIGURED,
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
    
    return inverters


def _inverter_options(
    inverters: list[dict[str, Any]], saved_serials: list[str] | None = None
) -> list[selector.SelectOptionDict]:
    """Build stable serial-valued options with useful Solis metadata."""
    options: dict[str, str] = {}
    for inverter in inverters:
        serial = inverter["sn"]
        details = [
            detail
            for key in ("stationName", "name", "model")
            if inverter.get(key) not in (None, "")
            and (detail := str(inverter[key]).strip())
        ]
        label = " - ".join(dict.fromkeys([*details, serial]))
        options.setdefault(serial, label)

    for serial in saved_serials or []:
        options.setdefault(serial, serial)

    return [
        selector.SelectOptionDict(value=serial, label=label)
        for serial, label in options.items()
    ]


def _selection_error(selection: Any, available_serials: set[str]) -> str | None:
    """Return a local validation error for an invalid inverter selection."""
    if not isinstance(selection, list) or not selection:
        return "no_inverters_selected"
    if len(selection) > MAX_INVERTERS:
        return "too_many_inverters"
    if (
        any(
            not isinstance(serial, str) or serial not in available_serials
            for serial in selection
        )
        or len(selection) != len(set(selection))
    ):
        return "invalid_inverter_selection"
    return None


def _selection_schema(
    options: list[selector.SelectOptionDict], defaults: list[str]
) -> vol.Schema:
    """Return the native multi-select schema used by setup and reconfigure."""
    return vol.Schema(
        {
            vol.Required(CONF_INVERTER_SERIALS, default=defaults): (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            )
        }
    )


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

                self._credentials = {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_API_SECRET: user_input[CONF_API_SECRET],
                }
                self._inverters = inverters
                return await self.async_step_inverters()

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

    async def async_step_inverters(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose which discovered inverters this entry will poll."""
        options = _inverter_options(self._inverters)
        available_serials = {option["value"] for option in options}
        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input.get(CONF_INVERTER_SERIALS)
            if error := _selection_error(selection, available_serials):
                errors[CONF_INVERTER_SERIALS] = error
            else:
                return self.async_create_entry(
                    title="Solis Cloud Monitoring",
                    data={
                        **self._credentials,
                        CONF_INVERTER_SERIALS: selection,
                        CONF_INVERTER_SELECTION_CONFIGURED: True,
                    },
                )

        defaults = [option["value"] for option in options[:MAX_INVERTERS]]
        return self.async_show_form(
            step_id="inverters",
            data_schema=_selection_schema(options, defaults),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Choose inverters for an existing entry without exposing credentials."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if not hasattr(self, "_reconfigure_inverters"):
            try:
                self._reconfigure_inverters = await validate_api_credentials(
                    self.hass,
                    entry.data[CONF_API_KEY],
                    entry.data[CONF_API_SECRET],
                )
            except SolisCloudAPIError as err:
                _LOGGER.error("Failed to discover inverters for reconfiguration")
                errors["base"] = (
                    "invalid_auth" if "Z0001" in str(err) else "cannot_connect"
                )
            except Exception:
                _LOGGER.exception("Unexpected error during inverter reconfiguration")
                errors["base"] = "unknown"

        options = _inverter_options(
            getattr(self, "_reconfigure_inverters", []),
            entry.data[CONF_INVERTER_SERIALS],
        )
        available_serials = {option["value"] for option in options}

        if user_input is not None and not errors:
            selection = user_input.get(CONF_INVERTER_SERIALS)
            if error := _selection_error(selection, available_serials):
                errors[CONF_INVERTER_SERIALS] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        **entry.data,
                        CONF_INVERTER_SERIALS: selection,
                        CONF_INVERTER_SELECTION_CONFIGURED: True,
                    },
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_selection_schema(options, entry.data[CONF_INVERTER_SERIALS]),
            errors=errors,
        )
