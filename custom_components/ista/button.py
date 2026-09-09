"""Support for Ista button entities."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IstaDataUpdateCoordinator
from .statistics import async_import_ista_statistics

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ista button entities based on a config entry."""
    coordinator: IstaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([IstaImportHistoryButton(coordinator, entry)])


class IstaImportHistoryButton(
    CoordinatorEntity[IstaDataUpdateCoordinator], ButtonEntity
):
    """Button to import historical readings from Ista into Home Assistant statistics."""

    entity_description = ButtonEntityDescription(
        key="import_history",
        name="Importar Histórico de Lecturas",
        icon="mdi:database-import",
        translation_key="import_history",
    )

    def __init__(
        self, coordinator: IstaDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the button entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._subscriber = (
            coordinator.data.get("account", {}).get("subscriber_number")
            or entry.entry_id
        )
        self._attr_unique_id = f"{self._subscriber}_import_history"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the account device."""
        account_name = self.coordinator.data.get("account", {}).get("name")
        label = f" ({account_name})" if account_name else ""
        return DeviceInfo(
            identifiers={(DOMAIN, self._subscriber)},
            name=f"Ista Cuenta {self._subscriber}{label}",
            manufacturer="Ista",
            model="Oficina Virtual Abonado",
        )

    async def async_press(self) -> None:
        """Handle button press: import statistics."""
        _LOGGER.info("Iniciando importación manual de histórico de lecturas de Ista...")
        results = await async_import_ista_statistics(self.hass, self.coordinator)
        total_imported = sum(results.values())
        _LOGGER.info(
            "Importación completada: %d registros importados (%s)",
            total_imported,
            results,
        )
