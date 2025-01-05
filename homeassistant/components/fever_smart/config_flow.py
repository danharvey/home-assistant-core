"""Config flow for fever_smart integration."""
from __future__ import annotations

import logging
from typing import Any

from pyfeversmart import FeverSmartAdvParser
import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfo,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fever Smart."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovery_info: BluetoothServiceInfo | None = None
        self._discovered_device: FeverSmartAdvParser | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfo
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        device = FeverSmartAdvParser()
        if not device.supported(discovery_info):
            _LOGGER.info("In discovery flow: Not supported")
            return self.async_abort(reason="not_supported")

        _LOGGER.info(
            "In discovery flow for %s: %s",
            discovery_info.address,
            device.primary_device_id,
        )

        await self.async_set_unique_id(device.primary_device_id)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery."""
        _LOGGER.info("In confirm flow")
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None

        errors = {}

        if user_input is not None:
            key = user_input["key"]
            # TODO: Test decryption?
            return self._async_get_or_create_entry(key)

        discovery_info = self._discovery_info
        _LOGGER.info("In confirm flow: %s", device.title)
        title = device.title or device.get_device_name() or discovery_info.name
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=placeholders,
            data_schema=vol.Schema({vol.Required("key"): vol.All(str, vol.Strip)}),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user step to pick discovered device."""
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            self.context["title_placeholders"] = {
                "name": self._discovered_devices[address]
            }
            # TODO: Ask for key here too...
            return self._async_get_or_create_entry("0m0d3s2c")

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = FeverSmartAdvParser()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                    device.title or device.get_device_name() or discovery_info.name
                )

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )

    def _async_get_or_create_entry(self, key=None):
        data = {}

        if key:
            data["key"] = key

        if entry_id := self.context.get("entry_id"):
            entry = self.hass.config_entries.async_get_entry(entry_id)
            assert entry is not None

            self.hass.config_entries.async_update_entry(entry, data=data)

            # Reload the config entry to notify of updated config
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(entry.entry_id)
            )

            return self.async_abort(reason="reauth_successful")

        return self.async_create_entry(
            title=self.context["title_placeholders"]["name"],
            data=data,
        )
