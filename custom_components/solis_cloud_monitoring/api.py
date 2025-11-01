"""API client for Solis Cloud."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any

import aiohttp

from .const import API_BASE_URL, API_INVERTER_DETAIL, API_INVERTER_LIST

_LOGGER = logging.getLogger(__name__)


class SolisCloudAPIError(Exception):
    """Exception raised for Solis Cloud API errors."""


class SolisCloudAPI:
    """Solis Cloud API client."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client.
        
        Args:
            api_key: Solis Cloud API key
            api_secret: Solis Cloud API secret
            session: aiohttp client session
        """
        self._api_key = api_key
        self._api_secret = api_secret
        self._session = session

    def _generate_headers(self, body: str, endpoint: str) -> dict[str, str]:
        """Generate authentication headers for API request.
        
        Args:
            body: JSON request body
            endpoint: API endpoint path
            
        Returns:
            Dictionary of HTTP headers
        """
        # MD5 hash of request body
        content_md5 = base64.b64encode(
            hashlib.md5(body.encode("utf-8")).digest()
        ).decode("utf-8")

        content_type = "application/json"
        date = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")

        # Create signature string per Solis API spec
        string_to_sign = f"POST\n{content_md5}\n{content_type}\n{date}\n{endpoint}"

        # HMAC-SHA1 signature
        signature = base64.b64encode(
            hmac.new(
                self._api_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha1,
            ).digest()
        ).decode("utf-8")

        authorization = f"API {self._api_key}:{signature}"

        return {
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": authorization,
        }

    async def _request(
        self, endpoint: str, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Make authenticated API request.
        
        Args:
            endpoint: API endpoint path
            payload: Request payload
            
        Returns:
            Response data or None on error
            
        Raises:
            SolisCloudAPIError: On API or network errors
        """
        url = f"{API_BASE_URL}{endpoint}"
        body = json.dumps(payload)
        headers = self._generate_headers(body, endpoint)

        try:
            async with asyncio.timeout(30):
                async with self._session.post(
                    url, headers=headers, data=body
                ) as response:
                    response_text = await response.text()

                    if response.status != 200:
                        raise SolisCloudAPIError(
                            f"HTTP {response.status}: {response_text}"
                        )

                    result = json.loads(response_text)

                    # Check API response code
                    if result.get("code") != "0":
                        error_msg = result.get("msg", "Unknown error")
                        raise SolisCloudAPIError(
                            f"API error {result.get('code')}: {error_msg}"
                        )

                    return result.get("data")

        except TimeoutError as err:
            raise SolisCloudAPIError(f"Timeout connecting to {url}") from err
        except aiohttp.ClientError as err:
            raise SolisCloudAPIError(f"Connection error: {err}") from err
        except json.JSONDecodeError as err:
            raise SolisCloudAPIError(f"Invalid JSON response: {err}") from err

    async def get_inverter_list(self) -> list[dict[str, Any]]:
        """Get list of all inverters on the account.
        
        Returns:
            List of inverter information dictionaries
            
        Raises:
            SolisCloudAPIError: On API or network errors
        """
        data = await self._request(API_INVERTER_LIST, {"pageSize": "100"})

        if not data or "page" not in data or "records" not in data["page"]:
            raise SolisCloudAPIError("Invalid inverter list response")

        inverters = data["page"]["records"]
        _LOGGER.debug("Found %d inverter(s)", len(inverters))
        return inverters

    async def get_inverter_details(self, serial_number: str) -> dict[str, Any]:
        """Get detailed information for a specific inverter.
        
        Args:
            serial_number: Inverter serial number
            
        Returns:
            Inverter details dictionary
            
        Raises:
            SolisCloudAPIError: On API or network errors
        """
        data = await self._request(API_INVERTER_DETAIL, {"sn": serial_number})

        if not data:
            raise SolisCloudAPIError(
                f"No data returned for inverter {serial_number}"
            )

        _LOGGER.debug("Retrieved details for inverter %s", serial_number)
        return data
