"""DataUpdateCoordinator for Ista integration."""
from __future__ import annotations

from datetime import timedelta
import logging
import os
import re
from typing import Any, Dict, List, Set

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DOWNLOAD_INVOICES,
    CONF_HEATING_PRICE,
    CONF_HOT_WATER_PRICE,
    CONF_INVOICES_PATH,
    DEFAULT_DOWNLOAD_INVOICES,
    DEFAULT_INVOICES_PATH,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_INVOICE,
)
from .ista_client import IstaAuthError, IstaClient, IstaConnectionError

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def _save_pdf_to_disk(target_path: str, content: bytes) -> None:
    """Save PDF bytes to disk synchronously in executor."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb") as f:
        f.write(content)


class IstaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Ista data from the portal and downloading new invoices."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: IstaClient,
        update_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.entry = entry
        self.client = client
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_invoices")
        self._seen_receipt_ids: Set[str] = set()
        self._store_loaded: bool = False

    async def _async_load_seen_receipts(self) -> None:
        """Load list of already seen/downloaded receipt IDs from persistent store."""
        if not self._store_loaded:
            stored_data = await self._store.async_load()
            if stored_data and isinstance(stored_data, dict):
                self._seen_receipt_ids = set(stored_data.get("seen_receipt_ids", []))
            self._store_loaded = True

    async def _async_save_seen_receipts(self) -> None:
        """Save list of seen receipt IDs to persistent store."""
        await self._store.async_save({"seen_receipt_ids": list(self._seen_receipt_ids)})

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Ista portal via executor and check for new invoices."""
        try:
            data = await self.hass.async_add_executor_job(self.client.fetch_data)
        except IstaAuthError as err:
            raise UpdateFailed(f"Authentication error with Ista portal: {err}") from err
        except IstaConnectionError as err:
            raise UpdateFailed(f"Connection error with Ista portal: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating Ista data: {err}") from err

        self._calculate_estimated_unbilled_costs(data)
        await self._process_new_invoices(data)
        return data

    def _calculate_estimated_unbilled_costs(self, data: Dict[str, Any]) -> None:
        """Calculate estimated cost of unbilled consumption for hot water and heating."""
        targets = [
            ("hot_water", CONF_HOT_WATER_PRICE),
            ("heating", CONF_HEATING_PRICE),
        ]

        for key, conf_price_key in targets:
            group_data = data.get(key, {})
            unbilled = group_data.get("unbilled_consumption")

            custom_price = self.entry.options.get(conf_price_key)
            if custom_price is not None and float(custom_price) > 0:
                unit_price = round(float(custom_price), 4)
                method = "manual_configurado"
            else:
                # Estimate unit price from latest invoice amount / last billed consumption
                latest_receipt = group_data.get("latest_receipt")
                last_billed_consumption = group_data.get("last_billed_consumption")
                amount = latest_receipt.get("amount") if isinstance(latest_receipt, dict) else None

                if (
                    amount is not None
                    and last_billed_consumption is not None
                    and float(last_billed_consumption) > 0
                ):
                    unit_price = round(float(amount) / float(last_billed_consumption), 4)
                    method = "automatico_ultima_factura"
                else:
                    unit_price = None
                    method = "desconocido"

            group_data["unit_price"] = unit_price
            group_data["calculation_method"] = method

            if unbilled is not None and unit_price is not None:
                estimated_cost = round(float(unbilled) * unit_price, 2)
                group_data["estimated_unbilled_cost"] = estimated_cost
            else:
                group_data["estimated_unbilled_cost"] = None


    async def _process_new_invoices(self, data: Dict[str, Any]) -> None:
        """Check for newly appeared invoices, download PDF if enabled, and fire event."""
        await self._async_load_seen_receipts()

        receipts: List[Dict[str, Any]] = data.get("receipts", [])
        if not receipts:
            return

        # First run ever: seed known receipts without downloading all past history
        if not self._seen_receipt_ids:
            for r in receipts:
                rec_id = r.get("receipt_id")
                if rec_id:
                    self._seen_receipt_ids.add(rec_id)
            await self._async_save_seen_receipts()
            _LOGGER.debug(
                "Initialized Ista seen receipts with %d existing invoices",
                len(self._seen_receipt_ids),
            )
            return

        should_download = self.entry.options.get(
            CONF_DOWNLOAD_INVOICES, DEFAULT_DOWNLOAD_INVOICES
        )
        download_dir = self.entry.options.get(
            CONF_INVOICES_PATH, DEFAULT_INVOICES_PATH
        )

        new_receipts_found = False

        for r in receipts:
            rec_id = r.get("receipt_id")
            if not rec_id or rec_id in self._seen_receipt_ids:
                continue

            new_receipts_found = True
            self._seen_receipt_ids.add(rec_id)

            date_str = r.get("date", "desconocida")
            eq_type = r.get("type", "recibo")
            amount = r.get("amount")

            # Clean filename: replace / with _ and remove invalid characters
            safe_date = date_str.replace("/", "-")
            safe_type = re.sub(r"[^\w\s-]", "", eq_type).strip().replace(" ", "_").lower()
            safe_id = re.sub(r"[^\w-]", "", rec_id)[:10]
            file_name = f"factura_ista_{safe_date}_{safe_type}_{safe_id}.pdf"
            target_path = os.path.join(download_dir, file_name)

            saved_file_path = None
            if should_download:
                try:
                    pdf_bytes = await self.hass.async_add_executor_job(
                        self.client.download_receipt_pdf, rec_id
                    )
                    await self.hass.async_add_executor_job(
                        _save_pdf_to_disk, target_path, pdf_bytes
                    )
                    saved_file_path = target_path
                    _LOGGER.info(
                        "Downloaded new Ista invoice PDF: %s (amount: %s €)",
                        target_path,
                        amount,
                    )
                except Exception as err:
                    _LOGGER.error("Failed to download PDF for invoice %s: %s", rec_id, err)

            # Fire Home Assistant event so automations (SMTP, FTP, Telegram) can act on it
            event_payload = {
                "receipt_id": rec_id,
                "date": date_str,
                "type": eq_type,
                "amount": amount,
                "file_path": saved_file_path,
                "file_name": file_name if saved_file_path else None,
                "url_path": (
                    f"/local/ista_facturas/{file_name}"
                    if saved_file_path and "www" in download_dir
                    else None
                ),
                "pdf_url": r.get("pdf_url"),
                "subscriber_number": data.get("account", {}).get("subscriber_number"),
                "subscriber_name": data.get("account", {}).get("name"),
            }

            self.hass.bus.async_fire(EVENT_NEW_INVOICE, event_payload)
            _LOGGER.info("Fired %s event for invoice %s", EVENT_NEW_INVOICE, rec_id)

        if new_receipts_found:
            await self._async_save_seen_receipts()
