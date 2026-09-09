"""Support for Ista sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_BILLS_COUNT,
    ATTR_CALCULATION_METHOD,
    ATTR_DAILY_READINGS,
    ATTR_EQUIPMENT_TYPE,
    ATTR_ESTIMATED_UNBILLED_COST,
    ATTR_LAST_BILLED_DATE,
    ATTR_LAST_BILLED_READING,
    ATTR_MONTHLY_HISTORY,
    ATTR_PDF_URL,
    ATTR_PREVIOUS_BILLED_READING,
    ATTR_READING_DATE,
    ATTR_RECEIPT_ID,
    ATTR_SERIAL_NUMBER,
    ATTR_SUBSCRIBER_NAME,
    ATTR_SUBSCRIBER_NUMBER,
    ATTR_TOTAL_BILLED_COST,
    ATTR_UNBILLED_CONSUMPTION,
    ATTR_UNIT_PRICE,
    DOMAIN,
)
from .coordinator import IstaDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class IstaSensorEntityDescription(SensorEntityDescription):
    """Description of an Ista sensor."""

    device_group: str  # "hot_water", "heating", or "account"
    value_fn: Callable[[Dict[str, Any]], Any]
    extra_attributes_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None


SENSOR_DESCRIPTIONS: tuple[IstaSensorEntityDescription, ...] = (
    # --- AGUA CALIENTE (HOT WATER) ---
    IstaSensorEntityDescription(
        key="hot_water_current_reading",
        translation_key="hot_water_current_reading",
        name="Agua Caliente Lectura Actual",
        device_group="hot_water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        icon="mdi:water-boiler",
        value_fn=lambda data: data.get("hot_water", {}).get("current_reading"),
        extra_attributes_fn=lambda data: {
            ATTR_READING_DATE: data.get("hot_water", {}).get("current_reading_date"),
            ATTR_SERIAL_NUMBER: data.get("hot_water", {}).get("serial"),
            ATTR_DAILY_READINGS: data.get("hot_water", {}).get("daily_readings"),
        },
    ),
    IstaSensorEntityDescription(
        key="hot_water_last_billed_consumption",
        translation_key="hot_water_last_billed_consumption",
        name="Agua Caliente Último Consumo Facturado",
        device_group="hot_water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=1,
        icon="mdi:water-percent",
        value_fn=lambda data: data.get("hot_water", {}).get("last_billed_consumption"),
        extra_attributes_fn=lambda data: {
            ATTR_LAST_BILLED_DATE: data.get("hot_water", {}).get("last_billed_date"),
            ATTR_LAST_BILLED_READING: data.get("hot_water", {}).get("last_billed_reading"),
            ATTR_PREVIOUS_BILLED_READING: data.get("hot_water", {}).get("previous_billed_reading"),
            ATTR_SERIAL_NUMBER: data.get("hot_water", {}).get("serial"),
            ATTR_MONTHLY_HISTORY: data.get("hot_water", {}).get("monthly_history"),
        },
    ),
    IstaSensorEntityDescription(
        key="hot_water_unbilled_consumption",
        translation_key="hot_water_unbilled_consumption",
        name="Agua Caliente Consumo No Facturado",
        device_group="hot_water",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        suggested_display_precision=3,
        icon="mdi:water-sync",
        value_fn=lambda data: data.get("hot_water", {}).get("unbilled_consumption"),
        extra_attributes_fn=lambda data: {
            ATTR_READING_DATE: data.get("hot_water", {}).get("current_reading_date"),
            ATTR_LAST_BILLED_DATE: data.get("hot_water", {}).get("last_billed_date"),
        },
    ),
    IstaSensorEntityDescription(
        key="hot_water_estimated_unbilled_cost",
        translation_key="hot_water_estimated_unbilled_cost",
        name="Agua Caliente Coste Estimado No Facturado",
        device_group="hot_water",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-clock",
        value_fn=lambda data: data.get("hot_water", {}).get("estimated_unbilled_cost"),
        extra_attributes_fn=lambda data: {
            ATTR_UNIT_PRICE: data.get("hot_water", {}).get("unit_price"),
            ATTR_CALCULATION_METHOD: data.get("hot_water", {}).get("calculation_method"),
            ATTR_UNBILLED_CONSUMPTION: data.get("hot_water", {}).get("unbilled_consumption"),
        },
    ),
    IstaSensorEntityDescription(
        key="hot_water_total_cost",
        translation_key="hot_water_total_cost",
        name="Agua Caliente Coste Total Facturado",
        device_group="hot_water",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-check",
        value_fn=lambda data: data.get("hot_water", {}).get("total_billed_cost"),
        extra_attributes_fn=lambda data: {
            ATTR_BILLS_COUNT: data.get("hot_water", {}).get("bills_count"),
        },
    ),
    IstaSensorEntityDescription(
        key="hot_water_latest_receipt",
        translation_key="hot_water_latest_receipt",
        name="Agua Caliente Última Factura",
        device_group="hot_water",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-multiple",
        value_fn=lambda data: data.get("hot_water", {}).get("latest_receipt", {}).get("amount"),
        extra_attributes_fn=lambda data: {
            ATTR_LAST_BILLED_DATE: data.get("hot_water", {}).get("latest_receipt", {}).get("date"),
            ATTR_PDF_URL: data.get("hot_water", {}).get("latest_receipt", {}).get("pdf_url"),
            ATTR_RECEIPT_ID: data.get("hot_water", {}).get("latest_receipt", {}).get("receipt_id"),
            ATTR_EQUIPMENT_TYPE: data.get("hot_water", {}).get("latest_receipt", {}).get("type"),
        },
    ),
    # --- CALEFACCIÓN (HEATING / OPTOSONIC) ---
    IstaSensorEntityDescription(
        key="heating_current_reading",
        translation_key="heating_current_reading",
        name="Calefacción Lectura Actual",
        device_group="heating",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        icon="mdi:radiator",
        value_fn=lambda data: data.get("heating", {}).get("current_reading"),
        extra_attributes_fn=lambda data: {
            ATTR_READING_DATE: data.get("heating", {}).get("current_reading_date"),
            ATTR_SERIAL_NUMBER: data.get("heating", {}).get("serial"),
            ATTR_DAILY_READINGS: data.get("heating", {}).get("daily_readings"),
        },
    ),
    IstaSensorEntityDescription(
        key="heating_last_billed_consumption",
        translation_key="heating_last_billed_consumption",
        name="Calefacción Último Consumo Facturado",
        device_group="heating",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        icon="mdi:fire",
        value_fn=lambda data: data.get("heating", {}).get("last_billed_consumption"),
        extra_attributes_fn=lambda data: {
            ATTR_LAST_BILLED_DATE: data.get("heating", {}).get("last_billed_date"),
            ATTR_LAST_BILLED_READING: data.get("heating", {}).get("last_billed_reading"),
            ATTR_PREVIOUS_BILLED_READING: data.get("heating", {}).get("previous_billed_reading"),
            ATTR_SERIAL_NUMBER: data.get("heating", {}).get("serial"),
            ATTR_MONTHLY_HISTORY: data.get("heating", {}).get("monthly_history"),
        },
    ),
    IstaSensorEntityDescription(
        key="heating_unbilled_consumption",
        translation_key="heating_unbilled_consumption",
        name="Calefacción Consumo No Facturado",
        device_group="heating",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        icon="mdi:radiator-disabled",
        value_fn=lambda data: data.get("heating", {}).get("unbilled_consumption"),
        extra_attributes_fn=lambda data: {
            ATTR_READING_DATE: data.get("heating", {}).get("current_reading_date"),
            ATTR_LAST_BILLED_DATE: data.get("heating", {}).get("last_billed_date"),
        },
    ),
    IstaSensorEntityDescription(
        key="heating_estimated_unbilled_cost",
        translation_key="heating_estimated_unbilled_cost",
        name="Calefacción Coste Estimado No Facturado",
        device_group="heating",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-clock",
        value_fn=lambda data: data.get("heating", {}).get("estimated_unbilled_cost"),
        extra_attributes_fn=lambda data: {
            ATTR_UNIT_PRICE: data.get("heating", {}).get("unit_price"),
            ATTR_CALCULATION_METHOD: data.get("heating", {}).get("calculation_method"),
            ATTR_UNBILLED_CONSUMPTION: data.get("heating", {}).get("unbilled_consumption"),
        },
    ),
    IstaSensorEntityDescription(
        key="heating_total_cost",
        translation_key="heating_total_cost",
        name="Calefacción Coste Total Facturado",
        device_group="heating",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-check",
        value_fn=lambda data: data.get("heating", {}).get("total_billed_cost"),
        extra_attributes_fn=lambda data: {
            ATTR_BILLS_COUNT: data.get("heating", {}).get("bills_count"),
        },
    ),
    IstaSensorEntityDescription(
        key="heating_latest_receipt",
        translation_key="heating_latest_receipt",
        name="Calefacción Última Factura",
        device_group="heating",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:cash-multiple",
        value_fn=lambda data: data.get("heating", {}).get("latest_receipt", {}).get("amount"),
        extra_attributes_fn=lambda data: {
            ATTR_LAST_BILLED_DATE: data.get("heating", {}).get("latest_receipt", {}).get("date"),
            ATTR_PDF_URL: data.get("heating", {}).get("latest_receipt", {}).get("pdf_url"),
            ATTR_RECEIPT_ID: data.get("heating", {}).get("latest_receipt", {}).get("receipt_id"),
            ATTR_EQUIPMENT_TYPE: data.get("heating", {}).get("latest_receipt", {}).get("type"),
        },
    ),
    # --- CUENTA Y FACTURACIÓN GENERAL ---
    IstaSensorEntityDescription(
        key="latest_receipt_overall",
        translation_key="latest_receipt_overall",
        name="Última Factura Ista",
        device_group="account",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="€",
        suggested_display_precision=2,
        icon="mdi:receipt-text",
        value_fn=lambda data: data.get("receipts", [{}])[0].get("amount")
        if data.get("receipts")
        else None,
        extra_attributes_fn=lambda data: {
            ATTR_LAST_BILLED_DATE: data.get("receipts", [{}])[0].get("date")
            if data.get("receipts")
            else None,
            ATTR_EQUIPMENT_TYPE: data.get("receipts", [{}])[0].get("type")
            if data.get("receipts")
            else None,
            ATTR_PDF_URL: data.get("receipts", [{}])[0].get("pdf_url")
            if data.get("receipts")
            else None,
            ATTR_RECEIPT_ID: data.get("receipts", [{}])[0].get("receipt_id")
            if data.get("receipts")
            else None,
            ATTR_SUBSCRIBER_NUMBER: data.get("account", {}).get("subscriber_number"),
            ATTR_SUBSCRIBER_NAME: data.get("account", {}).get("name"),
        },
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ista sensor based on a config entry."""
    coordinator: IstaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        IstaSensorEntity(coordinator=coordinator, entry=entry, description=description)
        for description in SENSOR_DESCRIPTIONS
    ]

    async_add_entities(entities)


class IstaSensorEntity(CoordinatorEntity[IstaDataUpdateCoordinator], SensorEntity):
    """Representation of an Ista sensor entity."""

    entity_description: IstaSensorEntityDescription

    def __init__(
        self,
        coordinator: IstaDataUpdateCoordinator,
        entry: ConfigEntry,
        description: IstaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry

        subscriber = (
            coordinator.data.get("account", {}).get("subscriber_number")
            or entry.entry_id
        )
        self._attr_unique_id = f"{subscriber}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return device-specific attributes."""
        if not self.coordinator.data or not self.entity_description.extra_attributes_fn:
            return None
        return self.entity_description.extra_attributes_fn(self.coordinator.data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this sensor."""
        data = self.coordinator.data or {}
        account = data.get("account", {})
        subscriber = account.get("subscriber_number") or self._entry.entry_id
        subscriber_name = account.get("name") or "Abonado Ista"

        group = self.entity_description.device_group

        if group == "hot_water":
            hw_serial = data.get("hot_water", {}).get("serial") or "AguaCaliente"
            return DeviceInfo(
                identifiers={(DOMAIN, f"{subscriber}_hw_{hw_serial}")},
                name=f"Ista Contador Agua Caliente ({hw_serial})",
                manufacturer="Ista",
                model="Radio agua caliente",
                via_device=(DOMAIN, f"{subscriber}_account"),
            )

        if group == "heating":
            heat_serial = data.get("heating", {}).get("serial") or "Calefaccion"
            return DeviceInfo(
                identifiers={(DOMAIN, f"{subscriber}_heat_{heat_serial}")},
                name=f"Ista Contador Calefacción ({heat_serial})",
                manufacturer="Ista",
                model="Optosonic",
                via_device=(DOMAIN, f"{subscriber}_account"),
            )

        # Account device
        return DeviceInfo(
            identifiers={(DOMAIN, f"{subscriber}_account")},
            name=f"Ista Cuenta {subscriber}",
            manufacturer="Ista",
            model="Oficina Virtual GesCon",
            configuration_url="https://oficina.ista.es/GesCon/MainPageAbo.do",
        )
