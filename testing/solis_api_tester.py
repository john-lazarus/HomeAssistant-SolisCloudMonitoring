#!/usr/bin/env python3
"""
Solis Cloud API Tester
Tests various API endpoints to discover available monitoring data for your inverter.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

import aiohttp
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SolisCloudAPI:
    """Client for interacting with Solis Cloud API"""
    
    BASE_URL = "https://www.soliscloud.com:13333"
    
    # API Endpoints
    INVERTER_LIST_ENDPOINT = "/v1/api/inverterList"
    INVERTER_DETAIL_ENDPOINT = "/v1/api/inverterDetail"
    STATION_LIST_ENDPOINT = "/v1/api/stationList"
    STATION_DETAIL_ENDPOINT = "/v1/api/stationDetail"
    READ_ENDPOINT = "/v2/api/atRead"
    READ_BATCH_ENDPOINT = "/v2/api/atReadBatch"
    
    def __init__(self, api_key: str, api_secret: str, session: aiohttp.ClientSession):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = session
        
    def _generate_headers(self, body: str, endpoint: str) -> Dict[str, str]:
        """Generate authentication headers for API requests"""
        import hashlib
        import hmac
        import base64
        
        # Create MD5 hash of body
        content_md5 = base64.b64encode(hashlib.md5(body.encode('utf-8')).digest()).decode('utf-8')
        
        # Create signature
        content_type = "application/json"
        date = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
        
        # Authorization string per Solis API spec
        string_to_sign = f"POST\n{content_md5}\n{content_type}\n{date}\n{endpoint}"
        
        # HMAC-SHA1 signature
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()
        ).decode('utf-8')
        
        authorization = f"API {self.api_key}:{signature}"
        
        return {
            "Content-Type": content_type,
            "Content-MD5": content_md5,
            "Date": date,
            "Authorization": authorization
        }
    
    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make authenticated API request"""
        url = f"{self.BASE_URL}{endpoint}"
        body = json.dumps(payload)
        headers = self._generate_headers(body, endpoint)
        
        try:
            async with self.session.post(url, headers=headers, data=body, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    logger.error(f"HTTP error {response.status}: {response_text}")
                    return None
                
                result = json.loads(response_text)
                
                # Check API response code
                if result.get("code") != "0":
                    logger.error(f"API error - Code: {result.get('code')}, Message: {result.get('msg')}")
                    return None
                
                return result.get("data")
                
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return None
    
    async def get_inverter_list(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of all inverters on the account"""
        logger.info("Fetching inverter list...")
        data = await self._make_request(self.INVERTER_LIST_ENDPOINT, {"pageSize": "100"})
        
        if data and "page" in data and "records" in data["page"]:
            return data["page"]["records"]
        return None
    
    async def get_inverter_details(self, inverter_sn: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific inverter"""
        logger.info(f"Fetching details for inverter {inverter_sn}...")
        return await self._make_request(self.INVERTER_DETAIL_ENDPOINT, {"sn": inverter_sn})
    
    async def get_station_list(self) -> Optional[List[Dict[str, Any]]]:
        """Get list of all stations on the account"""
        logger.info("Fetching station list...")
        data = await self._make_request(self.STATION_LIST_ENDPOINT, {"pageSize": "100"})
        
        if data and "page" in data and "records" in data["page"]:
            return data["page"]["records"]
        return None
    
    async def get_station_detail(self, station_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific station"""
        logger.info(f"Fetching details for station {station_id}...")
        return await self._make_request(self.STATION_DETAIL_ENDPOINT, {"id": station_id})
    
    async def read_cid(self, inverter_sn: str, cid: int) -> Optional[str]:
        """Read a single CID (Control ID) value from the inverter"""
        logger.info(f"Reading CID {cid} from inverter {inverter_sn}...")
        data = await self._make_request(self.READ_ENDPOINT, {"inverterSn": inverter_sn, "cid": cid})
        
        if data and "msg" in data:
            return data["msg"]
        return None
    
    async def read_cids_batch(self, inverter_sn: str, cids: List[int]) -> Optional[Dict[int, str]]:
        """Read multiple CID values at once"""
        logger.info(f"Reading {len(cids)} CIDs from inverter {inverter_sn}...")
        data = await self._make_request(
            self.READ_BATCH_ENDPOINT, 
            {"inverterSn": inverter_sn, "cids": ",".join(map(str, cids))}
        )
        
        if data and isinstance(data, list):
            result = {}
            for outer_item in data:
                if isinstance(outer_item, list):
                    for item in outer_item:
                        if "cid" in item and "msg" in item:
                            result[int(item["cid"])] = item["msg"]
            return result
        return None


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_json(data: Any, indent: int = 2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def print_flat_stats(data: Dict[str, Any]) -> None:
    """Print every key/value pair available in the inverter payload."""
    print_section("ALL INVERTER FIELDS (SORTED)")
    for key in sorted(data.keys()):
        print(f"{key}: {data[key]}")


async def test_monitoring_endpoints(api: SolisCloudAPI, inverter_sn: Optional[str] = None):
    """Test and extract Home Assistant energy dashboard relevant data"""
    
    # Get Inverter List
    print_section("DETECTING INVERTER")
    inverters = await api.get_inverter_list()
    if inverters:
        if not inverter_sn and inverters:
            inverter_sn = inverters[0].get("sn")
        print(f"Found inverter: {inverter_sn}")
    else:
        print("No inverters found")
        return
    
    if not inverter_sn:
        print("No inverter serial number available")
        return
    
    # Get Inverter Details
    print_section("HOME ASSISTANT ENERGY DASHBOARD - SOLAR PRODUCTION SENSORS")
    inverter_details = await api.get_inverter_details(inverter_sn)
    
    if not inverter_details:
        print("Failed to fetch inverter details")
        return
    
    # Extract HA Energy Dashboard relevant data
    solar_data = {
        "device_info": {
            "model": inverter_details.get("model"),
            "machine": inverter_details.get("machine"),
            "serial_number": inverter_details.get("sn"),
            "firmware_version": inverter_details.get("version"),
        },
        "power_sensors": {
            "current_power": {
                "value": inverter_details.get("pac"),
                "unit": "kW",
                "description": "Current AC Power Output",
                "ha_device_class": "power",
                "ha_state_class": "measurement"
            },
            "dc_power": {
                "value": inverter_details.get("dcPac"),
                "unit": "kW", 
                "description": "Current DC Power Input",
                "ha_device_class": "power",
                "ha_state_class": "measurement"
            }
        },
        "energy_sensors": {
            "energy_today": {
                "value": inverter_details.get("eToday"),
                "unit": inverter_details.get("eTodayStr", "kWh"),
                "description": "Solar Production Today",
                "ha_device_class": "energy",
                "ha_state_class": "total_increasing"
            },
            "energy_month": {
                "value": inverter_details.get("eMonth"),
                "unit": inverter_details.get("eMonthStr", "kWh"),
                "description": "Solar Production This Month",
                "ha_device_class": "energy",
                "ha_state_class": "total_increasing"
            },
            "energy_year": {
                "value": inverter_details.get("eYear"),
                "unit": inverter_details.get("eYearStr", "MWh"),
                "description": "Solar Production This Year",
                "ha_device_class": "energy",
                "ha_state_class": "total_increasing"
            },
            "energy_total": {
                "value": inverter_details.get("eTotal"),
                "unit": inverter_details.get("eTotalStr", "MWh"),
                "description": "Total Solar Production (Lifetime)",
                "ha_device_class": "energy",
                "ha_state_class": "total_increasing"
            }
        },
        "string_monitoring": {
            "pv1_voltage": {
                "value": inverter_details.get("uPv1"),
                "unit": "V",
                "description": "PV String 1 Voltage",
                "ha_device_class": "voltage",
                "ha_state_class": "measurement"
            },
            "pv1_current": {
                "value": inverter_details.get("iPv1"),
                "unit": "A",
                "description": "PV String 1 Current",
                "ha_device_class": "current",
                "ha_state_class": "measurement"
            },
            "pv1_power": {
                "value": inverter_details.get("pow1"),
                "unit": "W",
                "description": "PV String 1 Power",
                "ha_device_class": "power",
                "ha_state_class": "measurement"
            }
        },
        "grid_monitoring": {
            "grid_voltage": {
                "value": inverter_details.get("uAc1"),
                "unit": "V",
                "description": "Grid Voltage",
                "ha_device_class": "voltage",
                "ha_state_class": "measurement"
            },
            "grid_current": {
                "value": inverter_details.get("iAc1"),
                "unit": "A",
                "description": "Grid Current",
                "ha_device_class": "current",
                "ha_state_class": "measurement"
            },
            "grid_frequency": {
                "value": inverter_details.get("fac"),
                "unit": "Hz",
                "description": "Grid Frequency",
                "ha_device_class": "frequency",
                "ha_state_class": "measurement"
            }
        },
        "status_sensors": {
            "inverter_state": {
                "value": inverter_details.get("currentState"),
                "description": "Inverter Status (1=Offline, 2=Standby, 3=Generating)",
                "ha_device_class": "enum"
            },
            "inverter_temperature": {
                "value": inverter_details.get("inverterTemperature"),
                "unit": "°C",
                "description": "Inverter Temperature",
                "ha_device_class": "temperature",
                "ha_state_class": "measurement"
            },
            "daily_runtime": {
                "value": inverter_details.get("fullHour"),
                "unit": "h",
                "description": "Generation Hours Today",
                "ha_device_class": "duration",
                "ha_state_class": "total_increasing"
            }
        }
    }
    
    # Display formatted output
    print("\nDEVICE INFORMATION:")
    for key, value in solar_data["device_info"].items():
        print(f"   {key.replace('_', ' ').title()}: {value}")
    
    print("\nPOWER SENSORS (Real-time):")
    for sensor_name, sensor_data in solar_data["power_sensors"].items():
        print(f"   {sensor_data['description']}: {sensor_data['value']} {sensor_data['unit']}")
    
    print("\nENERGY SENSORS (For HA Energy Dashboard):")
    for sensor_name, sensor_data in solar_data["energy_sensors"].items():
        print(f"   {sensor_data['description']}: {sensor_data['value']} {sensor_data['unit']}")
    
    print("\nPV STRING MONITORING:")
    for sensor_name, sensor_data in solar_data["string_monitoring"].items():
        print(f"   {sensor_data['description']}: {sensor_data['value']} {sensor_data['unit']}")
    
    print("\nGRID MONITORING:")
    for sensor_name, sensor_data in solar_data["grid_monitoring"].items():
        print(f"   {sensor_data['description']}: {sensor_data['value']} {sensor_data['unit']}")
    
    print("\nSTATUS & DIAGNOSTICS:")
    for sensor_name, sensor_data in solar_data["status_sensors"].items():
        unit = f" {sensor_data['unit']}" if 'unit' in sensor_data else ""
        print(f"   {sensor_data['description']}: {sensor_data['value']}{unit}")
    
    print_flat_stats(inverter_details)

    print("\n" + "=" * 80)
    print("HOME ASSISTANT INTEGRATION NOTES:")
    print("=" * 80)
    print("Primary sensor for Energy Dashboard: energy_today (kWh)")
    print("Configure as 'Solar Production' in HA Energy settings")
    print("All sensors include proper device_class and state_class for HA")
    print("Power sensors update in real-time, energy sensors accumulate")
    print("=" * 80)


async def main():
    """Main entry point"""
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("SOLIS_API_KEY")
    api_secret = os.getenv("SOLIS_API_SECRET")
    inverter_sn = os.getenv("SOLIS_INVERTER_SN")
    
    # Validate credentials
    if not api_key or not api_secret:
        print("ERROR: SOLIS_API_KEY and SOLIS_API_SECRET must be set in environment variables")
        print("\nCreate a .env file with:")
        print("SOLIS_API_KEY=your_key_here")
        print("SOLIS_API_SECRET=your_secret_here")
        print("SOLIS_INVERTER_SN=your_inverter_serial_number  # Optional")
        sys.exit(1)
    
    print("=" * 80)
    print("  SOLIS CLOUD -> HOME ASSISTANT ENERGY DASHBOARD")
    print("  Solar Production Sensor Configuration")
    print("=" * 80)
    
    async with aiohttp.ClientSession() as session:
        api = SolisCloudAPI(api_key, api_secret, session)
        await test_monitoring_endpoints(api, inverter_sn)
    
    print("\n" + "=" * 80)
    print("  SENSOR CONFIGURATION COMPLETE")
    print("=" * 80)
    print("\nReady to build Home Assistant custom integration with these sensors.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Testing interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)
