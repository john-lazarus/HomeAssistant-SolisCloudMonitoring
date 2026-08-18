import asyncio
import base64
import hashlib
import hmac
import json
import sys
import types
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Minimal Home Assistant stubs so we can unit-test the integration helpers
# without installing a full Home Assistant runtime.
ha = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
sensor_mod = types.ModuleType("homeassistant.components.sensor")


class _SensorDeviceClass:
    POWER = "power"
    ENERGY = "energy"
    VOLTAGE = "voltage"
    CURRENT = "current"
    BATTERY = "battery"
    TEMPERATURE = "temperature"
    FREQUENCY = "frequency"
    DURATION = "duration"
    ENUM = "enum"


class _SensorStateClass:
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


class _SensorEntity:
    pass


@dataclass(frozen=True, kw_only=True)
class _SensorEntityDescription:
    key: str
    translation_key: str | None = None
    name: str | None = None
    native_unit_of_measurement: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    suggested_display_precision: int | None = None
    options: list[str] | None = None
    entity_category: str | None = None


sensor_mod.SensorDeviceClass = _SensorDeviceClass
sensor_mod.SensorStateClass = _SensorStateClass
sensor_mod.SensorEntity = _SensorEntity
sensor_mod.SensorEntityDescription = _SensorEntityDescription
config_entries = types.ModuleType("homeassistant.config_entries")
config_entries.ConfigEntry = object
const_mod = types.ModuleType("homeassistant.const")
const_mod.PERCENTAGE = "%"
const_mod.Platform = type("Platform", (), {"SENSOR": "sensor"})
for name, vals in {
    "UnitOfElectricCurrent": {"AMPERE": "A"},
    "UnitOfElectricPotential": {"VOLT": "V"},
    "UnitOfEnergy": {"KILO_WATT_HOUR": "kWh"},
    "UnitOfFrequency": {"HERTZ": "Hz"},
    "UnitOfPower": {"WATT": "W"},
    "UnitOfTemperature": {"CELSIUS": "°C"},
    "UnitOfTime": {"HOURS": "h"},
}.items():
    setattr(const_mod, name, type(name, (), vals))
core_mod = types.ModuleType("homeassistant.core")
core_mod.HomeAssistant = object
entity_mod = types.ModuleType("homeassistant.helpers.entity")
entity_mod.EntityCategory = type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic"})
platform_mod = types.ModuleType("homeassistant.helpers.entity_platform")
platform_mod.AddEntitiesCallback = object
typing_mod = types.ModuleType("homeassistant.helpers.typing")
typing_mod.StateType = object
update_mod = types.ModuleType("homeassistant.helpers.update_coordinator")


class _CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator=None):
        self.coordinator = coordinator


class _DataUpdateCoordinator:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, name=None, update_interval=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval


class _UpdateFailed(Exception):
    pass


update_mod.CoordinatorEntity = _CoordinatorEntity
update_mod.DataUpdateCoordinator = _DataUpdateCoordinator
update_mod.UpdateFailed = _UpdateFailed
helpers = types.ModuleType("homeassistant.helpers")
util_mod = types.ModuleType("homeassistant.util")
util_mod.__path__ = []
dt_util_mod = types.ModuleType("homeassistant.util.dt")
dt_util_mod.now = datetime.now
util_mod.dt = dt_util_mod
aiohttp_client_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
aiohttp_client_mod.async_get_clientsession = lambda hass: None
sys.modules.update(
    {
        "homeassistant": ha,
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensor_mod,
        "homeassistant.config_entries": config_entries,
        "homeassistant.const": const_mod,
        "homeassistant.core": core_mod,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.aiohttp_client": aiohttp_client_mod,
        "homeassistant.helpers.entity": entity_mod,
        "homeassistant.helpers.entity_platform": platform_mod,
        "homeassistant.helpers.typing": typing_mod,
        "homeassistant.helpers.update_coordinator": update_mod,
        "homeassistant.util": util_mod,
        "homeassistant.util.dt": dt_util_mod,
    }
)

from custom_components.solis_cloud_monitoring.api import SolisCloudAPI, SolisCloudAPIError
from custom_components.solis_cloud_monitoring.const import API_STATION_DETAIL
from custom_components.solis_cloud_monitoring.coordinator import (
    SolisCloudDataUpdateCoordinator,
    UpdateFailed,
    _merge_station_detail,
)
from custom_components.solis_cloud_monitoring.sensor import SENSOR_TYPES


def sensor_value(key, data):
    desc = next(s for s in SENSOR_TYPES if s.key == key)
    return desc.value_fn(data)


class _SequencedAPI:
    def __init__(self, responses):
        self.responses = responses

    async def get_inverter_details(self, serial):
        response = self.responses[serial].pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    async def get_station_details(self, station_id):
        raise AssertionError("Unexpected station detail request")


def test_inverter_detail_failure_retains_data_once_and_success_resets_grace():
    async def run_test():
        serial = "ABC"
        first = {"pac": "1.0"}
        recovered = {"pac": "2.0"}
        api = _SequencedAPI(
            {
                serial: [
                    first,
                    SolisCloudAPIError("temporary"),
                    SolisCloudAPIError("still failing"),
                    recovered,
                    SolisCloudAPIError("temporary again"),
                ]
            }
        )
        coordinator = SolisCloudDataUpdateCoordinator(object(), api, [serial])
        coordinator.data = {}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {serial: first}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {serial: first}

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {serial: recovered}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {serial: recovered}

    asyncio.run(run_test())


def test_inverter_detail_grace_is_per_serial():
    async def run_test():
        first_a = {"pac": "1.0"}
        fresh_a = {"pac": "1.4"}
        first_b = {"pac": "2.0"}
        second_b = {"pac": "2.2"}
        third_b = {"pac": "2.3"}
        api = _SequencedAPI(
            {
                "A": [
                    first_a,
                    SolisCloudAPIError("A temporary"),
                    SolisCloudAPIError("A still failing"),
                    fresh_a,
                    {"pac": "1.5"},
                ],
                "B": [
                    first_b,
                    second_b,
                    third_b,
                    SolisCloudAPIError("B temporary"),
                    SolisCloudAPIError("B still failing"),
                ],
            }
        )
        coordinator = SolisCloudDataUpdateCoordinator(object(), api, ["A", "B"])
        coordinator.data = {}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {"A": first_a, "B": first_b}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {"A": first_a, "B": second_b}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {"B": third_b}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {"A": fresh_a, "B": third_b}

        coordinator.data = await coordinator._async_update_data()
        assert coordinator.data == {"A": {"pac": "1.5"}}

    asyncio.run(run_test())


def test_station_detail_endpoint_is_available_and_uses_station_id():
    calls = []
    api = SolisCloudAPI("key", "secret", object())

    async def fake_request(endpoint, payload):
        calls.append((endpoint, payload))
        return {"stationName": "Home", "gridSellDayEnergy": "1.2"}

    api._request = fake_request
    result = asyncio.run(api.get_station_details("12345"))
    assert result["gridSellDayEnergy"] == "1.2"
    assert calls == [(API_STATION_DETAIL, {"id": "12345"})]


def test_station_detail_values_are_merged_without_clobbering_inverter_detail():
    inverter = {
        "sn": "ABC",
        "stationId": "123",
        "familyLoadPower": "2.2",
        "homeLoadTotalEnergy": "400",
    }
    station = {
        "familyLoadPower": "9.9",
        "homeLoadEnergy": "7.5",
        "gridPurchasedDayEnergy": "3.1",
        "gridSellYearEnergy": "123.4",
    }
    merged = _merge_station_detail(inverter, station)
    assert merged["familyLoadPower"] == "2.2"
    assert merged["station_homeLoadEnergy"] == "7.5"
    assert merged["station_gridPurchasedDayEnergy"] == "3.1"
    assert merged["station_gridSellYearEnergy"] == "123.4"


def test_station_detail_fallbacks_feed_daily_and_yearly_grid_load_sensors():
    data = {
        "type": "2",
        "station_homeLoadEnergy": "7.5",
        "station_gridPurchasedDayEnergy": "3.1",
        "station_gridSellYearEnergy": "123.4",
    }
    assert sensor_value("home_load_today_energy", data) == 7.5
    assert sensor_value("grid_import_today_energy", data) == 3.1
    assert sensor_value("grid_export_year_energy", data) == 123.4


def test_battery_power_gets_discharge_sign_from_storage_current():
    assert (
        sensor_value(
            "battery_power",
            {
                "type": "2",
                "batteryPower": "1.25",
                "batteryPowerStr": "kW",
                "storageBatteryCurrent": "-12",
            },
        )
        == -1250
    )
    assert (
        sensor_value(
            "battery_power",
            {
                "type": "2",
                "batteryPower": "1.25",
                "batteryPowerStr": "kW",
                "storageBatteryCurrent": "12",
            },
        )
        == 1250
    )


def test_pv_string_sensors_extend_to_pv24():
    assert sensor_value("pv24_voltage", {"uPv24": "620.5"}) == 620.5
    assert sensor_value("pv24_current", {"iPv24": "8.1"}) == 8.1
    assert sensor_value("pv24_power", {"Pow24": "5010"}) == 5010
