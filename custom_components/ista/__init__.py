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
    SERVICE_IMPORT_HISTORY,
)
from .coordinator import IstaDataUpdateCoordinator, _save_pdf_to_disk
from .ista_client import IstaClient

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

SERVICE_DOWNLOAD_SCHEMA = vol.Schema(
    {
        vol.Optional("receipt_id"): cv.string,
        vol.Optional("target_path"): cv.string,
        vol.Optional("invoice_type", default="latest"): cv.string,
        vol.Optional("type"): cv.string,
        vol.Optional("tipo"): cv.string,
    }
)

SERVICE_IMPORT_SCHEMA = vol.Schema(
    {
        vol.Optional("device_group"): vol.In(["hot_water", "heating"]),
        vol.Optional("clear_existing", default=True): cv.boolean,
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

    # Register download service
    async def handle_download_receipt(call: ServiceCall) -> dict[str, Any] | None:
        """Service to download a receipt PDF on demand."""
        receipt_id = call.data.get("receipt_id")
        custom_target = call.data.get("target_path")
        inv_type = (
            call.data.get("invoice_type")
            or call.data.get("type")
            or call.data.get("tipo")
            or "latest"
        )

        # Use first coordinator available
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            _LOGGER.error("No active Ista coordinator found")
            return None
        coord: IstaDataUpdateCoordinator = coordinators[0]

        selected_receipt = coord.get_receipt(
            invoice_type=inv_type,
            receipt_id=receipt_id,
        )

        if not selected_receipt or not selected_receipt.get("receipt_id"):
            _LOGGER.error(
                "No se encontró ninguna factura para descargar (tipo=%s, receipt_id=%s)",
                inv_type,
                receipt_id,
            )
            return None

        target_receipt_id = selected_receipt["receipt_id"]
        rec_date = selected_receipt.get("date", "desconocida")
        rec_type = selected_receipt.get("type", "recibo")
        rec_amount = selected_receipt.get("amount")

        download_dir = coord.entry.options.get(
            CONF_INVOICES_PATH, DEFAULT_INVOICES_PATH
        )
        safe_date = str(rec_date).replace("/", "-")
        safe_type = re.sub(r"[^\w\s-]", "", str(rec_type)).strip().replace(" ", "_").lower()
        safe_id = re.sub(r"[^\w-]", "", str(target_receipt_id))[:10]
        default_filename = f"factura_ista_{safe_date}_{safe_type}_{safe_id}.pdf"

        target_path = custom_target or os.path.join(download_dir, default_filename)

        try:
            pdf_bytes = await hass.async_add_executor_job(
                coord.client.download_receipt_pdf, target_receipt_id
            )
            await hass.async_add_executor_job(
                _save_pdf_to_disk, target_path, pdf_bytes
            )
            _LOGGER.info(
                "Factura guardada correctamente en %s (tipo=%s, fecha=%s, importe=%s €)",
                target_path,
                rec_type,
                rec_date,
                rec_amount,
            )
            return {
                "receipt_id": target_receipt_id,
                "target_path": target_path,
                "date": rec_date,
                "type": rec_type,
                "amount": rec_amount,
            }
        except Exception as err:
            _LOGGER.error("Error al descargar la factura %s: %s", target_receipt_id, err)
            raise

    register_kwargs = {
        "schema": SERVICE_DOWNLOAD_SCHEMA,
    }
    try:
        from homeassistant.core import SupportsResponse
        register_kwargs["supports_response"] = SupportsResponse.OPTIONAL
    except (ImportError, AttributeError):
        pass

    hass.services.async_register(
        DOMAIN,
        SERVICE_DOWNLOAD_RECEIPT,
        handle_download_receipt,
        **register_kwargs,
    )

    # Register import history service
    async def handle_import_history(call: ServiceCall) -> None:
        """Service to import historical readings into recorder statistics."""
        device_group = call.data.get("device_group")
        clear_existing = call.data.get("clear_existing", True)
        coordinators = list(hass.data.get(DOMAIN, {}).values())
        if not coordinators:
            _LOGGER.error("No active Ista coordinator found for history import")
            return

        from .statistics import async_import_ista_statistics

        for coord in coordinators:
            res = await async_import_ista_statistics(
                hass, coord, target_group=device_group, clear_existing=clear_existing
            )
            _LOGGER.info("Resultado importación histórico Ista: %s", res)

    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_HISTORY,
        handle_import_history,
        schema=SERVICE_IMPORT_SCHEMA,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    # Remove services if no entries remain
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_DOWNLOAD_RECEIPT)
        hass.services.async_remove(DOMAIN, SERVICE_IMPORT_HISTORY)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
