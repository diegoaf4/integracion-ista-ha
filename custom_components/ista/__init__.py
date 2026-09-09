"""The Ista integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import os
import re

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_INVOICES_PATH,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_INVOICES_PATH,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
    SERVICE_DOWNLOAD_RECEIPT,
)
from .coordinator import IstaDataUpdateCoordinator, _save_pdf_to_disk
from .ista_client import IstaClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

SERVICE_DOWNLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional("receipt_id"): cv.string,
        vol.Optional("target_path"): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ista from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    scan_interval_hours = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
    )
    update_interval = timedelta(hours=scan_interval_hours)

    client = IstaClient(username=username, password=password)
    coordinator = IstaDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        update_interval=update_interval,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    # Register download service if not already registered
    if not hass.services.has_service(DOMAIN, SERVICE_DOWNLOAD_RECEIPT):
        async def handle_download_receipt(call: ServiceCall) -> None:
            """Service to download a receipt PDF on demand."""
            receipt_id = call.data.get("receipt_id")
            custom_target = call.data.get("target_path")

            # Use first coordinator available
            coordinators = list(hass.data.get(DOMAIN, {}).values())
            if not coordinators:
                _LOGGER.error("No active Ista coordinator found")
                return
            coord: IstaDataUpdateCoordinator = coordinators[0]

            if not receipt_id:
                receipts = coord.data.get("receipts", [])
                if receipts:
                    receipt_id = receipts[0].get("receipt_id")

            if not receipt_id:
                _LOGGER.error("No receipt ID specified or found in recent receipts")
                return

            download_dir = coord.entry.options.get(
                CONF_INVOICES_PATH, DEFAULT_INVOICES_PATH
            )
            target_path = custom_target or os.path.join(
                download_dir, f"factura_ista_{receipt_id}.pdf"
            )

            try:
                pdf_bytes = await hass.async_add_executor_job(
                    coord.client.download_receipt_pdf, receipt_id
                )
                await hass.async_add_executor_job(
                    _save_pdf_to_disk, target_path, pdf_bytes
                )
                _LOGGER.info("Saved receipt PDF to %s", target_path)
            except Exception as err:
                _LOGGER.error("Failed to download receipt via service: %s", err)

        hass.services.async_register(
            DOMAIN,
            SERVICE_DOWNLOAD_RECEIPT,
            handle_download_receipt,
            schema=SERVICE_DOWNLOAD_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove service if no entries remain
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_DOWNLOAD_RECEIPT)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
