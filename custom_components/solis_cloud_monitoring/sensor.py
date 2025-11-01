"""Sensor platform for Solis Cloud Monitoring."""
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
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
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


# Define all sensor types
SENSOR_TYPES: tuple[SolisSensorEntityDescription, ...] = (
    # Power Sensors
    SolisSensorEntityDescription(
        key="current_power",
        translation_key="current_power",
        name="Current Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _coerce_float(data.get("pac")),
    ),
    SolisSensorEntityDescription(
        key="dc_power",
        translation_key="dc_power",
        name="DC Power",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _coerce_float(data.get("dcPac")),
    ),
    # Energy Sensors
    SolisSensorEntityDescription(
        key="energy_today",
        translation_key="energy_today",
        name="Energy Today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("eToday")),
    ),
    SolisSensorEntityDescription(
        key="energy_month",
        translation_key="energy_month",
        name="Energy This Month",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("eMonth")),
    ),
    SolisSensorEntityDescription(
        key="energy_year",
        translation_key="energy_year",
        name="Energy This Year",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _coerce_float(data.get("eYear")),
    ),
    SolisSensorEntityDescription(
        key="energy_total",
        translation_key="energy_total",
        name="Total Energy",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda data: _coerce_float(data.get("eTotal")),
    ),
    # PV String Monitoring
    SolisSensorEntityDescription(
        key="pv1_voltage",
        translation_key="pv1_voltage",
        name="PV String 1 Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("uPv1")),
    ),
    SolisSensorEntityDescription(
        key="pv1_current",
        translation_key="pv1_current",
        name="PV String 1 Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("iPv1")),
    ),
    SolisSensorEntityDescription(
        key="pv1_power",
        translation_key="pv1_power",
        name="PV String 1 Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _coerce_float(data.get("pow1")),
    ),
    # Grid Monitoring
    SolisSensorEntityDescription(
        key="grid_voltage",
        translation_key="grid_voltage",
        name="Grid Voltage",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("uAc1")),
    ),
    SolisSensorEntityDescription(
        key="grid_current",
        translation_key="grid_current",
        name="Grid Current",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("iAc1")),
    ),
    SolisSensorEntityDescription(
        key="grid_frequency",
        translation_key="grid_frequency",
        name="Grid Frequency",
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _coerce_float(data.get("fac")),
    ),
    # Status and Diagnostics
    SolisSensorEntityDescription(
        key="inverter_temperature",
        translation_key="inverter_temperature",
        name="Inverter Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _coerce_float(data.get("inverterTemperature")),
    ),
    SolisSensorEntityDescription(
        key="daily_runtime",
        translation_key="daily_runtime",
        name="Generation Hours Today",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
        value_fn=lambda data: _coerce_float(data.get("fullHour")),
    ),
    SolisSensorEntityDescription(
        key="inverter_state",
        translation_key="inverter_state",
        name="Inverter Status",
        device_class=SensorDeviceClass.ENUM,
        options=["offline", "standby", "generating"],
        value_fn=lambda data: {
            "1": "offline",
            "2": "standby",
            "3": "generating",
        }.get(str(data.get("currentState")), "offline"),
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
    
    # Create sensors for each inverter
    for serial in coordinator.inverter_serials:
        for description in SENSOR_TYPES:
            entities.append(
                SolisCloudSensor(
                    coordinator,
                    description,
                    serial,
                )
            )

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
        
        # Use last 4 digits of serial for entity ID
        serial_suffix = serial_number[-4:]
        
        # Set unique ID
        self._attr_unique_id = f"{serial_number}_{description.key}"
        
        # Set entity ID with readable format
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
        """Return True if entity is available."""
        return (
            self.coordinator.last_update_success
            and self._serial_number in self.coordinator.data
        )
