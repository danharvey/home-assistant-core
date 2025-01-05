"""The Fever Smart Bluetooth integration."""
from collections.abc import Callable
from logging import Logger
from typing import Any

from pyfeversmart import FeverSmartAdvParser

from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
)
from homeassistant.components.bluetooth.api import (
    async_register_callback,
    async_track_unavailable,
)
from homeassistant.components.bluetooth.match import BluetoothCallbackMatcher
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback


class FeverSmartPassiveBluetoothProcessorCoordinator(
    PassiveBluetoothProcessorCoordinator
):
    """Define a FeverSmart Bluetooth Passive Update Processor Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: Logger,
        address: str,
        mode: BluetoothScanningMode,
        update_method: Callable[[BluetoothServiceInfoBleak], Any],
        # device_data: FeverSmartAdvParser,
        # discovered_device_classes: set[str],
        # entry: ConfigEntry,
        connectable: bool = False,
    ) -> None:
        """Initialize the FeverSmart Bluetooth Passive Update Processor Coordinator."""
        super().__init__(hass, logger, address, mode, update_method, connectable)
        # self.discovered_device_classes = discovered_device_classes
        # self.device_data = device_data
        # self.entry = entry

    @callback
    def _async_start(self) -> None:
        """Start the callbacks."""
        self._on_stop.append(
            async_register_callback(
                self.hass,
                self._async_handle_bluetooth_event,
                BluetoothCallbackMatcher(
                    manufacturer_id=8199,
                    # manufacturer_data_start=, limit to device_id here...
                    connectable=False,
                ),
                self.mode,
            )
        )
        self._on_stop.append(
            async_track_unavailable(
                self.hass,
                self._async_handle_unavailable,
                self.address,
                self.connectable,
            )
        )


class FeverSmartPassiveBluetoothDataProcessor(PassiveBluetoothDataProcessor):
    """Define a FeverSmart Bluetooth Passive Update Data Processor."""

    coordinator: FeverSmartPassiveBluetoothProcessorCoordinator
