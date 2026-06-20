"""Sensor platform for Solis Cloud Monitoring v2."""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER
from .coordinator import SolisCloudDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SolisSensorEntityDescription(SensorEntityDescription):
    """Describes Solis sensor entity."""

    value_fn: Callable[[dict[str, Any]], StateType]


def _coerce_float(value: Any) -> float | None:
    """Convert API values to floats when possible."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_value(data: dict[str, Any], *keys: str) -> Any:
    """Return the first non-empty API value from a list of same-meaning keys."""
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def _first_float(data: dict[str, Any], *keys: str) -> float | None:
    """Return the first non-empty API value coerced to float."""
    return _coerce_float(_first_value(data, *keys))


def _unit(data: dict[str, Any], key: str, default: str) -> str:
    """Return an API unit string normalized for comparisons."""
    value = data.get(key)
    if value in (None, ""):
        return default
    return str(value).strip()


def _power_to_watts(
    data: dict[str, Any],
    value_key: str,
    unit_key: str | None = None,
    default_unit: str = "kW",
) -> float | None:
    """Read a Solis power field and normalize it to watts."""
    value = _coerce_float(data.get(value_key))
    if value is None:
        return None

    unit = _unit(data, unit_key, default_unit) if unit_key else default_unit
    unit_lower = unit.lower()

    if unit_lower in {"w", "watt", "watts"}:
        return value
    if unit_lower in {"kw", "kilowatt", "kilowatts"}:
        return value * 1000
    if unit_lower in {"mw", "megawatt", "megawatts"}:
        return value * 1_000_000

    # Unknown/missing units in Solis detail payloads are usually kW for these
    # aggregate live power fields. Prefer a stable value over guessing zero.
    if default_unit.lower() == "w":
        return value
    if default_unit.lower() == "mw":
        return value * 1_000_000
    return value * 1000


def _energy_to_kwh(
    data: dict[str, Any],
    value_key: str,
    unit_key: str | None = None,
    default_unit: str = "kWh",
) -> float | None:
    """Read a Solis energy field and normalize it to kWh."""
    value = _coerce_float(data.get(value_key))
    if value is None:
        return None

    unit = _unit(data, unit_key, default_unit) if unit_key else default_unit
    unit_lower = unit.lower().replace(" ", "")

    if unit_lower in {"wh", "watt-hour", "watthour"}:
        return value / 1000
    if unit_lower in {"kwh", "kilowatt-hour", "kilowatthour"}:
        return value
    if unit_lower in {"mwh", "megawatt-hour", "megawatthour"}:
        return value * 1000

    # Most Solis energy values in inverterDetail are kWh unless their *Str
    # field explicitly says MWh.
    if default_unit.lower() == "mwh":
        return value * 1000
    if default_unit.lower() == "wh":
        return value / 1000
    return value




def _hide_grid_only_zero(data: dict[str, Any], value: float | None) -> float | None:
    """Hide zero-valued hybrid/storage fields on explicit grid-only models.

    SolisCloud may include hybrid/storage keys with 0 values even for grid-only
    inverters. If the API explicitly identifies the inverter as type=1 (grid),
    a zero battery/load/import/export value is usually unsupported rather than
    meaningful telemetry. Non-zero values are still returned.
    """
    if value is None:
        return None
    if str(data.get("type")) == "1" and value == 0:
        return None
    return value


def _model_power_to_watts(
    data: dict[str, Any],
    value_key: str,
    unit_key: str | None = None,
    default_unit: str = "kW",
) -> float | None:
    """Return optional model-specific power, hiding unsupported grid-only zeros."""
    return _hide_grid_only_zero(
        data, _power_to_watts(data, value_key, unit_key, default_unit)
    )


def _model_energy_to_kwh(
    data: dict[str, Any],
    value_key: str,
    unit_key: str | None = None,
    default_unit: str = "kWh",
) -> float | None:
    """Return optional model-specific energy, hiding unsupported grid-only zeros."""
    return _hide_grid_only_zero(
        data, _energy_to_kwh(data, value_key, unit_key, default_unit)
    )


def _model_float(data: dict[str, Any], *keys: str) -> float | None:
    """Return optional model-specific float, hiding unsupported grid-only zeros."""
    return _hide_grid_only_zero(data, _fallback_float(data, *keys))

def _fallback_power_to_watts(
    data: dict[str, Any],
    candidates: tuple[tuple[str, str | None, str], ...],
) -> float | None:
    """Read the first available same-meaning power candidate as watts."""
    for value_key, unit_key, default_unit in candidates:
        if data.get(value_key) not in (None, ""):
            return _power_to_watts(data, value_key, unit_key, default_unit)
    return None


def _fallback_float(data: dict[str, Any], *keys: str) -> float | None:
    """Read first available numeric field from same-meaning candidates."""
    return _first_float(data, *keys)


def _total_pv_power_watts(data: dict[str, Any]) -> float:
    """Return summed PV string power in watts for all reported powN fields."""
    total = 0.0
    found = False
    for index in range(1, 33):
        value = _coerce_float(data.get(f"pow{index}"))
        if value is None:
            # Some Solis docs spell the table fields as Pow2/Pow32, though
            # examples use lower-case powN.
            value = _coerce_float(data.get(f"Pow{index}"))
        if value is not None:
            total += value
            found = True
    return total if found else 0.0


def _inverter_ac_power_watts(data: dict[str, Any]) -> float | None:
    """Return inverter AC power, with conservative night noise suppression."""
    pac_w = _power_to_watts(data, "pac", "pacStr", "kW")
    if pac_w is None:
        return None

    # SolisCloud can report tiny positive standby/noise values at night. Treat
    # <=30 W as zero only when DC/PV evidence also says there is no production.
    if 0 < pac_w <= 30:
        dc_w = _power_to_watts(data, "dcPac", "dcPacStr", "W")
        pv_w = _total_pv_power_watts(data)
        if (dc_w is None or abs(dc_w) <= 10) and abs(pv_w) <= 10:
            return 0.0

    return pac_w


def _inverter_state(data: dict[str, Any]) -> str:
    """Map Solis state fields to stable Home Assistant enum values."""
    raw = data.get("currentState", data.get("state"))
    if raw in (None, ""):
        return None
    return {
        "1": "offline",
        "2": "standby",
        "3": "generating",
    }.get(str(raw), "unknown")


SENSOR_TYPES: tuple[SolisSensorEntityDescription, ...] = (
    # Inverter production / diagnostics
    SolisSensorEntityDescription(
        key="inverter_ac_power",
        translation_key="inverter_ac_power",
        name="Inverter AC Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=_inverter_ac_power_watts,
    ),
    SolisSensorEntityDescription(
        key="inverter_dc_power",
        translation_key="inverter_dc_power",
        name="Inverter DC Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _power_to_watts(data, "dcPac", "dcPacStr", "W"),
    ),
    SolisSensorEntityDescription(
        key="inverter_generation_today_energy",
        translation_key="inverter_generation_today_energy",
        name="Inverter Generation Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _energy_to_kwh(data, "eToday", "eTodayStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="inverter_generation_month_energy",
        translation_key="inverter_generation_month_energy",
        name="Inverter Generation This Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _energy_to_kwh(data, "eMonth", "eMonthStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="inverter_generation_year_energy",
        translation_key="inverter_generation_year_energy",
        name="Inverter Generation This Year",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _energy_to_kwh(data, "eYear", "eYearStr", "MWh"),
    ),
    SolisSensorEntityDescription(
        key="inverter_generation_total_energy",
        translation_key="inverter_generation_total_energy",
        name="Inverter Generation Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _energy_to_kwh(data, "eTotal", "eTotalStr", "MWh"),
    ),
    SolisSensorEntityDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        name="Inverter Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "inverterTemperature"),
    ),
    SolisSensorEntityDescription(
        key="inverter_daily_runtime",
        translation_key="inverter_daily_runtime",
        name="Inverter Runtime Today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _fallback_float(data, "fullHour"),
    ),
    SolisSensorEntityDescription(
        key="inverter_state",
        translation_key="inverter_state",
        name="Inverter Status",
        device_class=SensorDeviceClass.ENUM,
        options=["offline", "standby", "generating", "unknown"],
        value_fn=_inverter_state,
    ),
    # PV string monitoring
    SolisSensorEntityDescription(
        key="pv1_voltage",
        translation_key="pv1_voltage",
        name="PV String 1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "uPv1"),
    ),
    SolisSensorEntityDescription(
        key="pv1_current",
        translation_key="pv1_current",
        name="PV String 1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "iPv1"),
    ),
    SolisSensorEntityDescription(
        key="pv1_power",
        translation_key="pv1_power",
        name="PV String 1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _fallback_float(data, "pow1", "Pow1"),
    ),
    SolisSensorEntityDescription(
        key="pv2_voltage",
        translation_key="pv2_voltage",
        name="PV String 2 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "uPv2"),
    ),
    SolisSensorEntityDescription(
        key="pv2_current",
        translation_key="pv2_current",
        name="PV String 2 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "iPv2"),
    ),
    SolisSensorEntityDescription(
        key="pv2_power",
        translation_key="pv2_power",
        name="PV String 2 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _fallback_float(data, "pow2", "Pow2"),
    ),
    # Grid AC / meter values exposed by inverterDetail
    SolisSensorEntityDescription(
        key="grid_l1_voltage",
        translation_key="grid_l1_voltage",
        name="Grid L1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "uAc1", "uA"),
    ),
    SolisSensorEntityDescription(
        key="grid_l1_current",
        translation_key="grid_l1_current",
        name="Grid L1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "iAc1", "iA"),
    ),
    SolisSensorEntityDescription(
        key="grid_l2_voltage",
        translation_key="grid_l2_voltage",
        name="Grid L2 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "uAc2", "uB"),
    ),
    SolisSensorEntityDescription(
        key="grid_l2_current",
        translation_key="grid_l2_current",
        name="Grid L2 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "iAc2", "iB"),
    ),
    SolisSensorEntityDescription(
        key="grid_l3_voltage",
        translation_key="grid_l3_voltage",
        name="Grid L3 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "uAc3", "uC"),
    ),
    SolisSensorEntityDescription(
        key="grid_l3_current",
        translation_key="grid_l3_current",
        name="Grid L3 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _fallback_float(data, "iAc3", "iC"),
    ),
    SolisSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _fallback_float(data, "fac", "fAc"),
    ),
    SolisSensorEntityDescription(
        key="grid_active_power",
        translation_key="grid_active_power",
        name="Grid Active Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _fallback_power_to_watts(
            data,
            (("pSum", "pSumStr", "kW"), ("psum", "psumStr", "kW")),
        ),
    ),
    # Battery / storage values exposed by inverterDetail on supported models
    SolisSensorEntityDescription(
        key="battery_soc",
        translation_key="battery_soc",
        name="Battery SOC",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_float(data, "batteryCapacitySoc"),
    ),
    SolisSensorEntityDescription(
        key="battery_soh",
        translation_key="battery_soh",
        name="Battery SOH",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_float(data, "batteryHealthSoh"),
    ),
    SolisSensorEntityDescription(
        key="battery_power",
        translation_key="battery_power",
        name="Battery Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_power_to_watts(data, "batteryPower", "batteryPowerStr", "kW"),
    ),
    SolisSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        name="Battery Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _model_float(data, "storageBatteryVoltage", "batteryVoltage"),
    ),
    SolisSensorEntityDescription(
        key="battery_current",
        translation_key="battery_current",
        name="Battery Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _model_float(data, "storageBatteryCurrent", "bstteryCurrent"),
    ),
    SolisSensorEntityDescription(
        key="battery_charge_today_energy",
        translation_key="battery_charge_today_energy",
        name="Battery Charge Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "batteryTodayChargeEnergy", "batteryTodayChargeEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="battery_charge_total_energy",
        translation_key="battery_charge_total_energy",
        name="Battery Charge Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "batteryTotalChargeEnergy", "batteryTotalChargeEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="battery_discharge_today_energy",
        translation_key="battery_discharge_today_energy",
        name="Battery Discharge Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "batteryTodayDischargeEnergy", "batteryTodayDischargeEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="battery_discharge_total_energy",
        translation_key="battery_discharge_total_energy",
        name="Battery Discharge Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "batteryTotalDischargeEnergy", "batteryTotalDischargeEnergyStr", "kWh"),
    ),
    # Load / backup values
    SolisSensorEntityDescription(
        key="home_load_power",
        translation_key="home_load_power",
        name="Home Load Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_power_to_watts(data, "familyLoadPower", "familyLoadPowerStr", "kW"),
    ),
    SolisSensorEntityDescription(
        key="total_load_power",
        translation_key="total_load_power",
        name="Total Load Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_power_to_watts(data, "totalLoadPower", "totalLoadPowerStr", "kW"),
    ),
    SolisSensorEntityDescription(
        key="bypass_load_power",
        translation_key="bypass_load_power",
        name="Bypass Load Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: _model_power_to_watts(data, "bypassLoadPower", "bypassLoadPowerStr", "kW"),
    ),
    SolisSensorEntityDescription(
        key="home_load_today_energy",
        translation_key="home_load_today_energy",
        name="Home Load Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "homeLoadTodayEnergy", "homeLoadTodayEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="home_load_total_energy",
        translation_key="home_load_total_energy",
        name="Home Load Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "homeLoadTotalEnergy", "homeLoadTotalEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="backup_load_today_energy",
        translation_key="backup_load_today_energy",
        name="Backup Load Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "backupTodayEnergy", "backupTodayEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="backup_load_total_energy",
        translation_key="backup_load_total_energy",
        name="Backup Load Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "backupTotalEnergy", "backupTotalEnergyStr", "kWh"),
    ),
    # Grid import/export energy
    SolisSensorEntityDescription(
        key="grid_import_today_energy",
        translation_key="grid_import_today_energy",
        name="Grid Import Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "gridPurchasedTodayEnergy", "gridPurchasedTodayEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="grid_import_total_energy",
        translation_key="grid_import_total_energy",
        name="Grid Import Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "gridPurchasedTotalEnergy", "gridPurchasedTotalEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="grid_export_today_energy",
        translation_key="grid_export_today_energy",
        name="Grid Export Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "gridSellTodayEnergy", "gridSellTodayEnergyStr", "kWh"),
    ),
    SolisSensorEntityDescription(
        key="grid_export_total_energy",
        translation_key="grid_export_total_energy",
        name="Grid Export Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _model_energy_to_kwh(data, "gridSellTotalEnergy", "gridSellTotalEnergyStr", "kWh"),
    ),
    # Diagnostics
    SolisSensorEntityDescription(
        key="collector_state",
        translation_key="collector_state",
        name="Collector State",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=["online", "offline", "unknown"],
        value_fn=lambda data: None if data.get("collectorState") in (None, "") else {"1": "online", "2": "offline"}.get(str(data.get("collectorState")), "unknown"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solis Cloud sensors from a config entry."""
    coordinator: SolisCloudDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SolisCloudSensor] = []
    for serial in coordinator.inverter_serials:
        for description in SENSOR_TYPES:
            entities.append(SolisCloudSensor(coordinator, description, serial))

    async_add_entities(entities)


class SolisCloudSensor(CoordinatorEntity[SolisCloudDataUpdateCoordinator], SensorEntity):
    """Representation of a Solis Cloud sensor."""

    entity_description: SolisSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolisCloudDataUpdateCoordinator,
        description: SolisSensorEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._serial_number = serial_number

        serial_suffix = serial_number[-4:]
        self._attr_unique_id = f"{serial_number}_{description.key}"
        self._attr_object_id = f"solis_{serial_suffix}_{description.key}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        if self._serial_number not in self.coordinator.data:
            return {}

        data = self.coordinator.data[self._serial_number]
        model = data.get("model", "Unknown")
        machine = data.get("machine", "Unknown")

        return {
            "identifiers": {(DOMAIN, self._serial_number)},
            "name": f"Solis Inverter {self._serial_number[-4:]}",
            "manufacturer": MANUFACTURER,
            "model": f"{machine} ({model})",
            "sw_version": data.get("version"),
            "serial_number": self._serial_number,
        }

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self._serial_number not in self.coordinator.data:
            return None

        data = self.coordinator.data[self._serial_number]
        return self.entity_description.value_fn(data)

    @property
    def available(self) -> bool:
        """Return True when this sensor has data for this inverter/model."""
        if not self.coordinator.last_update_success:
            return False
        if self._serial_number not in self.coordinator.data:
            return False
        return self.native_value is not None
