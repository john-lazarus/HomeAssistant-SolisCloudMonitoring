"""API client for Solis Cloud."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_INVERTER_DETAIL,
    API_INVERTER_LIST,
    API_STATION_DETAIL,
)

_LOGGER = logging.getLogger(__name__)


class SolisCloudAPIError(Exception):
    """A safe error message plus structured details for the config flow.

    Do not include response bodies, credentials or account identifiers in the
    message. The coordinator and config flow may log it at warning/error level.
    """

    def __init__(
        self,
        message: str,
        *,
        error_key: str = "cannot_connect",
        http_status: int | None = None,
        api_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error_key = error_key
        self.http_status = http_status
        self.api_code = api_code


class SolisCloudAPI:
    """Solis Cloud API client."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        session: aiohttp.ClientSession,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._session = session

    def _generate_headers(self, body: str, endpoint: str) -> dict[str, str]:
        """Generate authentication headers according to the Solis API spec."""
        content_md5 = base64.b64encode(
            hashlib.md5(body.encode("utf-8")).digest()
        ).decode("utf-8")
        content_type = "application/json"
        date = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        string_to_sign = f"POST\n{content_md5}\n{content_type}\n{date}\n{endpoint}"
        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")
        return {
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": f"API {self._api_key}:{signature}",
        }

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> Any:
        """Read a cloud endpoint without retrying or logging its response body."""
        url = f"{API_BASE_URL}{endpoint}"
        body = json.dumps(payload)
        headers = self._generate_headers(body, endpoint)

        try:
            async with asyncio.timeout(30):
                async with self._session.post(
                    url, headers=headers, data=body
                ) as response:
                    status = response.status
                    if status != 200:
                        if status in (401, 403):
                            error_key = "invalid_auth"
                        elif status == 429:
                            error_key = "rate_limited"
                        elif 500 <= status < 600:
                            error_key = "server_error"
                        else:
                            error_key = "cannot_connect"
                        raise SolisCloudAPIError(
                            f"SolisCloud HTTP {status}",
                            error_key=error_key,
                            http_status=status,
                        )

                    result = json.loads(await response.text())
                    if not isinstance(result, dict):
                        raise SolisCloudAPIError(
                            "Invalid API response", error_key="invalid_response"
                        )

                    # Accept the API's string codes and integer zero, but not a
                    # missing code, boolean or arbitrary object as success.
                    raw_code = result.get("code")
                    if type(raw_code) not in (str, int):
                        raise SolisCloudAPIError(
                            "Missing or invalid API status", error_key="invalid_response"
                        )
                    code = str(raw_code)
                    if code != "0":
                        # Only retain a small status-code shape. Solis messages
                        # and unexpected status strings may echo sensitive data.
                        safe_code = code if re.fullmatch(r"[A-Z][0-9]{4}|[0-9]{1,4}", code) else None
                        detail = f" {safe_code}" if safe_code is not None else ""
                        raise SolisCloudAPIError(
                            f"SolisCloud API error{detail}",
                            error_key="invalid_auth" if code == "Z0001" else "api_error",
                            http_status=status,
                            api_code=safe_code,
                        )
                    return result.get("data")

        except TimeoutError as err:
            raise SolisCloudAPIError(
                "SolisCloud request timed out after 30 seconds", error_key="timeout"
            ) from err
        except aiohttp.ClientError as err:
            # The original exception may contain a URL or response headers.
            raise SolisCloudAPIError(
                f"Could not reach SolisCloud ({type(err).__name__})"
            ) from err
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            raise SolisCloudAPIError(
                "Invalid JSON response from SolisCloud", error_key="invalid_response"
            ) from err

    async def get_inverter_list(self) -> list[dict[str, Any]]:
        """Return unique inverter records with nonempty, stripped serials."""
        data = await self._request(API_INVERTER_LIST, {"pageSize": "100"})
        if not isinstance(data, dict) or not isinstance(data.get("page"), dict):
            raise SolisCloudAPIError(
                "Invalid inverter list response", error_key="invalid_response"
            )
        records = data["page"].get("records")
        if not isinstance(records, list):
            raise SolisCloudAPIError(
                "Invalid inverter list response", error_key="invalid_response"
            )
        if not records:
            raise SolisCloudAPIError(
                "No inverters found on this account", error_key="no_inverters"
            )

        inverters: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                raise SolisCloudAPIError(
                    "Invalid inverter record", error_key="invalid_response"
                )
            serial = record.get("sn")
            if not isinstance(serial, str) or not serial.strip():
                raise SolisCloudAPIError(
                    "Invalid inverter serial", error_key="invalid_response"
                )
            serial = serial.strip()
            inverters.setdefault(serial, {**record, "sn": serial})

        _LOGGER.debug("Found %d inverter(s)", len(inverters))
        return list(inverters.values())

    async def get_inverter_details(self, serial_number: str) -> dict[str, Any]:
        """Get validated inverter data from the cloud."""
        data = await self._request(API_INVERTER_DETAIL, {"sn": serial_number})
        if not isinstance(data, dict) or not data:
            raise SolisCloudAPIError(
                "Invalid or empty inverter details", error_key="invalid_response"
            )
        _LOGGER.debug("Retrieved details for inverter %s", serial_number)
        return data

    async def get_station_details(self, station_id: str) -> dict[str, Any]:
        """Get validated station data for grid/load energy fallbacks."""
        data = await self._request(API_STATION_DETAIL, {"id": station_id})
        if not isinstance(data, dict) or not data:
            raise SolisCloudAPIError(
                "Invalid or empty station details", error_key="invalid_response"
            )
        _LOGGER.debug("Retrieved station details for station %s", station_id)
        return data
