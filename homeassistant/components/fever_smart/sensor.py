"""Platform for sensor integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sensor_state_data import (
    DeviceKey,
    SensorDescription,
    SensorDeviceClass as SSDSensorDeviceClass,
    SensorUpdate,
    Units,
)

from homeassistant import config_entries, const
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_CONNECTIONS,
    ATTR_IDENTIFIERS,
    ATTR_NAME,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import (
    FeverSmartPassiveBluetoothDataProcessor,
    FeverSmartPassiveBluetoothProcessorCoordinator,
)

if TYPE_CHECKING:
    # `sensor_state_data` is a second-party library (i.e. maintained by Home Assistant
    # core members) which is not strictly required by Home Assistant.
    # Therefore, we import it as a type hint only.
    from sensor_state_data import SensorDeviceInfo

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS = {
    (SSDSensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SSDSensorDeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        SSDSensorDeviceClass.SIGNAL_STRENGTH,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{SSDSensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
}


def _device_key_to_bluetooth_entity_key(
    device_key: DeviceKey,
) -> PassiveBluetoothEntityKey:
    """Convert a device key to an entity key."""
    return PassiveBluetoothEntityKey(device_key.key, device_key.device_id)


def _to_sensor_key(
    description: SensorDescription,
) -> tuple[SSDSensorDeviceClass, Units | None]:
    assert description.device_class is not None
    return (description.device_class, description.native_unit_of_measurement)


def sensor_device_info_to_hass_device_info(
    sensor_device_info: SensorDeviceInfo,
    device_id: str,
) -> DeviceInfo:
    """Convert a sensor_state_data sensor device info to a HA device info."""
    device_info = DeviceInfo()
    if sensor_device_info.name is not None:
        device_info[const.ATTR_NAME] = sensor_device_info.name
    if sensor_device_info.manufacturer is not None:
        device_info[const.ATTR_MANUFACTURER] = sensor_device_info.manufacturer
    if sensor_device_info.model is not None:
        device_info[const.ATTR_MODEL] = sensor_device_info.model
    if sensor_device_info.sw_version is not None:
        device_info[const.ATTR_SW_VERSION] = sensor_device_info.sw_version
    device_info[const.ATTR_IDENTIFIERS] = {DOMAIN, device_id}
    return device_info


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    return PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info, device_id)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            _device_key_to_bluetooth_entity_key(device_key): SENSOR_DESCRIPTIONS[
                _to_sensor_key(description)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if _to_sensor_key(description) in SENSOR_DESCRIPTIONS
        },
        entity_data={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            _device_key_to_bluetooth_entity_key(device_key): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fever Smart BLE sensors."""
    _LOGGER.info("Setting up fever smart sensor")
    coordinator: FeverSmartPassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = FeverSmartPassiveBluetoothDataProcessor(
        sensor_update_to_bluetooth_data_update
    )
    entry.async_on_unload(
        processor.async_add_entities_listener(
            FeverSmartBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class FeverSmartBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[PassiveBluetoothDataProcessor[float | int | None]],
    SensorEntity,
):
    """Representation of a Fever Smart BLE Sensor."""

    def __init__(
        self,
        processor: PassiveBluetoothDataProcessor,
        entity_key: PassiveBluetoothEntityKey,
        description: EntityDescription,
        context: Any = None,
    ) -> None:
        """Create the entity with a PassiveBluetoothDataProcessor."""
        super().__init__(processor, entity_key, description, context)
        device_id = entity_key.device_id
        key = entity_key.key
        self._attr_device_info = DeviceInfo(
            {ATTR_IDENTIFIERS: {(DOMAIN, f"{device_id}")}}
        )
        self._attr_unique_id = f"{device_id}-{key}"

        if ATTR_NAME not in self._attr_device_info:
            self._attr_device_info[ATTR_NAME] = device_id

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
