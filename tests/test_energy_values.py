"""Regression tests for Solis energy value handling."""
from __future__ import annotations

import importlib
import sys
import types
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _install_homeassistant_stubs() -> None:
    def module(name: str) -> types.ModuleType:
        mod = types.ModuleType(name)
        sys.modules[name] = mod
        return mod

    module("homeassistant")
    module("homeassistant.components")
    sensor_mod = module("homeassistant.components.sensor")

    @dataclass(frozen=True, kw_only=True)
    class SensorEntityDescription:
        key: str
        translation_key: str | None = None
        name: str | None = None
        native_unit_of_measurement: str | None = None
        device_class: str | None = None
        state_class: str | None = None
        suggested_display_precision: int | None = None
        entity_category: str | None = None
        options: list[str] | None = None

    class _Values:
        def __getattr__(self, name: str) -> str:
            return name.lower()

    class SensorEntity:
        pass

    sensor_mod.SensorDeviceClass = _Values()
    sensor_mod.SensorEntity = SensorEntity
    sensor_mod.SensorEntityDescription = SensorEntityDescription
    sensor_mod.SensorStateClass = _Values()

    config_entries_mod = module("homeassistant.config_entries")
    config_entries_mod.ConfigEntry = object

    const_mod = module("homeassistant.const")
    const_mod.PERCENTAGE = "%"
    const_mod.Platform = _Values()
    const_mod.UnitOfElectricCurrent = _Values()
    const_mod.UnitOfElectricPotential = _Values()
    const_mod.UnitOfEnergy = _Values()
    const_mod.UnitOfFrequency = _Values()
    const_mod.UnitOfPower = _Values()
    const_mod.UnitOfTemperature = _Values()
    const_mod.UnitOfTime = _Values()

    core_mod = module("homeassistant.core")
    core_mod.HomeAssistant = object

    helpers_mod = module("homeassistant.helpers")
    helpers_mod.__path__ = []

    entity_mod = module("homeassistant.helpers.entity")
    entity_mod.EntityCategory = _Values()

    entity_platform_mod = module("homeassistant.helpers.entity_platform")
    entity_platform_mod.AddEntitiesCallback = Any

    typing_mod = module("homeassistant.helpers.typing")
    typing_mod.StateType = Any

    update_mod = module("homeassistant.helpers.update_coordinator")

    class CoordinatorEntity:
        def __init__(self, coordinator: Any) -> None:
            self.coordinator = coordinator

        def __class_getitem__(cls, item: Any) -> type:
            return cls

    class DataUpdateCoordinator:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def __class_getitem__(cls, item: Any) -> type:
            return cls

    update_mod.CoordinatorEntity = CoordinatorEntity
    update_mod.DataUpdateCoordinator = DataUpdateCoordinator
    update_mod.UpdateFailed = Exception

    aiohttp_mod = module("aiohttp")
    aiohttp_mod.ClientSession = object
    aiohttp_mod.ClientError = Exception


_install_homeassistant_stubs()

# Avoid executing the Home Assistant integration package __init__ during unit tests.
pkg = types.ModuleType("custom_components.solis_cloud_monitoring")
pkg.__path__ = [
    str(Path(__file__).resolve().parents[1] / "custom_components" / "solis_cloud_monitoring")
]
sys.modules["custom_components.solis_cloud_monitoring"] = pkg

sensor = importlib.import_module("custom_components.solis_cloud_monitoring.sensor")


def value_for(key: str, data: dict[str, Any]) -> Any:
    for description in sensor.SENSOR_TYPES:
        if description.key == key:
            return description.value_fn(data)
    raise AssertionError(f"No sensor description for {key}")


class EnergyValueTests(unittest.TestCase):
    def test_ac_power_suppresses_002_kw_standby_noise(self) -> None:
        value = value_for(
            "inverter_ac_power",
            {
                "pac": "0.02",
                "pacStr": "kW",
                "dcPac": "0.02",
                "dcPacStr": "kW",
                "pow1": "0",
            },
        )

        self.assertEqual(value, 0.0)

    def test_ac_power_suppresses_observed_night_pv_noise(self) -> None:
        value = value_for(
            "inverter_ac_power",
            {
                "pac": "0.02",
                "pacStr": "kW",
                "dcPac": "0.026",
                "dcPacStr": "kW",
                "pow1": "22",
            },
        )

        self.assertEqual(value, 0.0)

    def test_ac_power_keeps_real_low_generation(self) -> None:
        value = value_for(
            "inverter_ac_power",
            {
                "pac": "0.02",
                "pacStr": "kW",
                "dcPac": "0.05",
                "dcPacStr": "kW",
                "pow1": "50",
            },
        )

        self.assertEqual(value, 20.0)
    def test_today_generation_is_unavailable_for_stale_morning_no_generation_reading(self) -> None:
        value = value_for(
            "inverter_generation_today_energy",
            {
                "eToday": "12.34",
                "eTodayStr": "kWh",
                "pac": "20",
                "pacStr": "W",
                "dcPac": "0",
                "dcPacStr": "W",
                "pow1": "0",
            },
        )

        self.assertIsNone(value)

    def test_today_generation_is_kept_when_power_shows_real_generation(self) -> None:
        value = value_for(
            "inverter_generation_today_energy",
            {
                "eToday": "0.25",
                "eTodayStr": "kWh",
                "pac": "120",
                "pacStr": "W",
                "dcPac": "130",
                "dcPacStr": "W",
                "pow1": "130",
            },
        )

        self.assertEqual(value, 0.25)

    def test_year_generation_missing_unit_is_not_assumed_to_be_mwh(self) -> None:
        self.assertEqual(
            value_for("inverter_generation_year_energy", {"eYear": "1234"}),
            1234.0,
        )

    def test_total_generation_missing_unit_is_not_assumed_to_be_mwh(self) -> None:
        self.assertEqual(
            value_for("inverter_generation_total_energy", {"eTotal": "9876"}),
            9876.0,
        )

    def test_total_generation_explicit_mwh_still_converts_to_kwh(self) -> None:
        self.assertEqual(
            value_for(
                "inverter_generation_total_energy",
                {"eTotal": "9.876", "eTotalStr": "MWh"},
            ),
            9876.0,
        )


if __name__ == "__main__":
    unittest.main()
