"""Data update coordinator for Solis Cloud Monitoring."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SolisCloudAPI, SolisCloudAPIError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _merge_station_detail(
    inverter_data: dict[str, Any], station_data: dict[str, Any] | None
) -> dict[str, Any]:
    """Return inverter detail plus namespaced station-level Solis fields.

    hultenvp/solis-sensor reads both inverterDetail and stationDetail. Keep
    inverterDetail authoritative and add station fields under a prefix so same
    named keys cannot silently overwrite inverter telemetry.
    """
    merged = dict(inverter_data)
    if not station_data:
        return merged

    for key, value in station_data.items():
        if value not in (None, ""):
            merged[f"station_{key}"] = value
    return merged


class SolisCloudDataUpdateCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Class to manage fetching Solis Cloud data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SolisCloudAPI,
        inverter_serials: list[str],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = api
        self.inverter_serials = inverter_serials

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from Solis Cloud API."""
        data: dict[str, dict[str, Any]] = {}
        station_cache: dict[str, dict[str, Any] | None] = {}

        try:
            for serial in self.inverter_serials:
                try:
                    inverter_data = await self.api.get_inverter_details(serial)
                    station_data = None
                    station_id = inverter_data.get("stationId")
                    if station_id not in (None, ""):
                        station_id = str(station_id)
                        if station_id not in station_cache:
                            try:
                                station_cache[station_id] = (
                                    await self.api.get_station_details(station_id)
                                )
                            except SolisCloudAPIError as err:
                                station_cache[station_id] = None
                                _LOGGER.debug(
                                    "Failed to update station %s details: %s",
                                    station_id,
                                    err,
                                )
                        station_data = station_cache[station_id]

                    inverter_data = _merge_station_detail(inverter_data, station_data)
                    data[serial] = inverter_data

                    pac_value = inverter_data.get("pac")
                    try:
                        pac_float = (
                            float(pac_value) if pac_value not in (None, "") else None
                        )
                    except (TypeError, ValueError):
                        pac_float = None

                    if pac_float is not None:
                        _LOGGER.debug(
                            "Updated data for inverter %s: power=%.2f kW",
                            serial,
                            pac_float,
                        )
                    else:
                        _LOGGER.debug("Updated data for inverter %s", serial)
                except SolisCloudAPIError as err:
                    _LOGGER.warning("Failed to update inverter %s: %s", serial, err)
                    continue

            if not data:
                raise UpdateFailed("Failed to fetch data for any inverter")

            return data

        except SolisCloudAPIError as err:
            raise UpdateFailed(
                f"Error communicating with Solis Cloud API: {err}"
            ) from err
