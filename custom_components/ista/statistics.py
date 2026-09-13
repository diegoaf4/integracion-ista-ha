"""Historical statistics importer for Ista integration."""
from __future__ import annotations

from datetime import datetime
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

try:
    from homeassistant.const import UnitOfEnergy, UnitOfVolume
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import dt as dt_util
except ImportError:
    class UnitOfVolume:  # type: ignore[no-redef]
        CUBIC_METERS = "m³"

    class UnitOfEnergy:  # type: ignore[no-redef]
        KILO_WATT_HOUR = "kWh"

    HomeAssistant = Any  # type: ignore[misc, assignment]
    er = Any  # type: ignore[assignment]

    class dt_util:  # type: ignore[no-redef]
        @staticmethod
        def as_utc(dt: datetime) -> datetime:
            from datetime import timezone
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        @staticmethod
        def get_time_zone(tz_str: str):
            from datetime import timezone
            return timezone.utc

try:
    from .const import DOMAIN
except ImportError:
    DOMAIN = "ista"

if TYPE_CHECKING:
    from .coordinator import IstaDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Spanish month mapping for flexible parsing
SPANISH_MONTHS = {
    "enero": 1,
    "ene": 1,
    "febrero": 2,
    "feb": 2,
    "marzo": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "mayo": 5,
    "may": 5,
    "junio": 6,
    "jun": 6,
    "julio": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "septiembre": 9,
    "sep": 9,
    "setiembre": 9,
    "octubre": 10,
    "oct": 10,
    "noviembre": 11,
    "nov": 11,
    "diciembre": 12,
    "dic": 12,
}


def parse_flexible_date(date_str: Optional[str], tz=None) -> Optional[datetime]:
    """Parse flexible date string from Ista into a timezone-aware datetime at midnight."""
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)

    standard_formats = [
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%Y/%m/%d",
        "%d.%m.%Y",
    ]

    for fmt in standard_formats:
        try:
            dt_naive = datetime.strptime(cleaned, fmt)
            if tz:
                return dt_naive.replace(tzinfo=tz)
            return dt_util.as_utc(dt_naive)
        except ValueError:
            continue

    # Try month/year like "01/2026" or "01-2026"
    m_my = re.match(r"^(\d{1,2})[/.-](\d{4})$", cleaned)
    if m_my:
        month = int(m_my.group(1))
        year = int(m_my.group(2))
        if 1 <= month <= 12:
            dt_naive = datetime(year, month, 1)
            if tz:
                return dt_naive.replace(tzinfo=tz)
            return dt_util.as_utc(dt_naive)

    # Try Spanish month names like "Enero 2026" or "15 Enero 2026"
    for m_name, m_num in SPANISH_MONTHS.items():
        if m_name in cleaned:
            m_day = re.search(r"\b(\d{1,2})\b", cleaned)
            m_year = re.search(r"\b(20\d{2})\b", cleaned)
            year = int(m_year.group(1)) if m_year else datetime.now().year
            day = int(m_day.group(1)) if m_day else 1
            try:
                dt_naive = datetime(year, m_num, min(day, 28))
                if tz:
                    return dt_naive.replace(tzinfo=tz)
                return dt_util.as_utc(dt_naive)
            except ValueError:
                pass

    return None


def extract_historical_datapoints(
    group_data: Dict[str, Any], tz=None
) -> List[Tuple[datetime, float, float]]:
    """Extract and combine historical readings into a chronologically sorted series with accumulated consumption.

    Returns: List of (datetime, reading_state, cumulative_consumption_sum).
    """
    # 1. Extract and sort monthly history
    monthly_rows = group_data.get("monthly_history", [])
    parsed_monthly: List[Tuple[datetime, Dict[str, Any]]] = []
    for row in monthly_rows:
        if not isinstance(row, dict):
            continue
        reading = row.get("current_reading")
        date_str = row.get("date")
        if reading is not None and date_str:
            dt = parse_flexible_date(date_str, tz=tz)
            if dt:
                parsed_monthly.append((dt, row))

    parsed_monthly.sort(key=lambda item: item[0])

    series: List[Tuple[datetime, float, float]] = []
    accumulated_sum = 0.0
    last_reading: Optional[float] = None
    last_dt: Optional[datetime] = None

    for dt, r in parsed_monthly:
        curr_r = float(r["current_reading"])
        prev_r = float(r["previous_reading"]) if r.get("previous_reading") is not None else curr_r
        # If Ista gives consumption, use it; otherwise compute positive delta
        if r.get("consumption") is not None and float(r["consumption"]) >= 0:
            consumption = float(r["consumption"])
        else:
            consumption = max(0.0, curr_r - prev_r)

        accumulated_sum += consumption
        series.append((dt, curr_r, round(accumulated_sum, 3)))
        last_reading = curr_r
        last_dt = dt

    # 2. Extract and incorporate daily radio readings (listaLecturasRadio)
    daily_readings = group_data.get("daily_readings", {})
    sorted_daily: List[Tuple[datetime, float]] = []
    if isinstance(daily_readings, dict):
        for date_str, reading in daily_readings.items():
            if reading is not None:
                dt = parse_flexible_date(date_str, tz=tz)
                if dt:
                    sorted_daily.append((dt, float(reading)))

    sorted_daily.sort(key=lambda item: item[0])

    for dt, reading in sorted_daily:
        if last_dt is None or dt > last_dt:
            delta = max(0.0, reading - (last_reading if last_reading is not None else reading))
            accumulated_sum += delta
            series.append((dt, reading, round(accumulated_sum, 3)))
            last_reading = reading
            last_dt = dt

    # 3. Extract latest current reading if available and newer than all previous points
    current_reading = group_data.get("current_reading")
    current_date_str = group_data.get("current_reading_date")
    if current_reading is not None and current_date_str:
        dt = parse_flexible_date(current_date_str, tz=tz)
        if dt and (last_dt is None or dt > last_dt):
            curr_val = float(current_reading)
            delta = max(0.0, curr_val - (last_reading if last_reading is not None else curr_val))
            accumulated_sum += delta
            series.append((dt, curr_val, round(accumulated_sum, 3)))

    return series


def extract_historical_cost_datapoints(
    receipts: List[Dict[str, Any]], target_group: str, tz=None
) -> List[Tuple[datetime, float, float]]:
    """Extract and combine historical invoice amounts into a cumulative cost series.

    Returns: List of (dt, invoice_amount, cumulative_sum).
    """
    filtered_items: List[Tuple[datetime, float]] = []

    for r in receipts:
        if not isinstance(r, dict):
            continue
        rec_type = r.get("type", "").lower()
        if target_group == "hot_water":
            if not any(k in rec_type for k in ("agua", "acs")):
                continue
        elif target_group == "heating":
            if not any(k in rec_type for k in ("optosonic", "calefacc", "calor")):
                continue

        amount = r.get("amount")
        date_str = r.get("date")
        if amount is not None and float(amount) > 0 and date_str:
            dt = parse_flexible_date(date_str, tz=tz)
            if dt:
                filtered_items.append((dt, float(amount)))

    if not filtered_items:
        return []

    # Sort chronologically by date ascending
    sorted_items = sorted(filtered_items, key=lambda item: item[0])

    # Calculate cumulative sum
    series: List[Tuple[datetime, float, float]] = []
    accumulated = 0.0

    for dt, amount in sorted_items:
        accumulated += amount
        series.append((dt, round(amount, 2), round(accumulated, 2)))

    return series


async def async_import_ista_statistics(
    hass: HomeAssistant,
    coordinator: IstaDataUpdateCoordinator,
    target_group: Optional[str] = None,
    clear_existing: bool = True,
) -> Dict[str, int]:
    """Import historical readings and invoice costs from Ista into Home Assistant recorder statistics."""
    if "recorder" not in hass.config.components:
        _LOGGER.warning("El componente 'recorder' no está disponible. No se pueden importar estadísticas.")
        return {}

    try:
        from homeassistant.components.recorder import get_instance
        from homeassistant.components.recorder.models import (
            StatisticData,
            StatisticMetaData,
        )
        from homeassistant.components.recorder.statistics import async_import_statistics
    except ImportError as err:
        _LOGGER.error("No se pudo cargar el módulo de estadísticas de recorder: %s", err)
        return {}

    ent_reg = er.async_get(hass)
    subscriber = (
        coordinator.data.get("account", {}).get("subscriber_number")
        or coordinator.entry.entry_id
    )

    tz = dt_util.get_time_zone(hass.config.time_zone)
    results: Dict[str, int] = {}

    # 1. Fetch all historical receipts across all pages if possible and sync with coordinator
    all_receipts = []
    try:
        all_receipts = await hass.async_add_executor_job(coordinator.client.fetch_all_receipts)
        if all_receipts:
            await coordinator.async_update_all_receipts(all_receipts)
    except Exception as err:
        _LOGGER.warning("No se pudo obtener la paginación completa de facturas, usando recibos en caché: %s", err)
        all_receipts = getattr(coordinator, "_all_receipts", []) or coordinator.data.get("receipts", [])

    # 2. Import consumption physical readings (m³ and kWh)
    targets = []
    if target_group in ("hot_water", None):
        targets.append(
            (
                "hot_water",
                "hot_water_current_reading",
                UnitOfVolume.CUBIC_METERS,
                "Agua Caliente Lectura Actual",
            )
        )
    if target_group in ("heating", None):
        targets.append(
            (
                "heating",
                "heating_current_reading",
                UnitOfEnergy.KILO_WATT_HOUR,
                "Calefacción Lectura Actual",
            )
        )

    for group_key, sensor_key, unit, default_name in targets:
        group_data = coordinator.data.get(group_key, {})
        datapoints = extract_historical_datapoints(group_data, tz=tz)

        if not datapoints:
            _LOGGER.info("No se encontraron lecturas históricas para %s en Ista", group_key)
            results[group_key] = 0
            continue

        unique_id = f"{subscriber}_{sensor_key}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)

        if not entity_id:
            _LOGGER.warning(
                "No se encontró la entidad para %s (unique_id=%s) en el registro de entidades. Asegúrate de que la integración está cargada.",
                group_key,
                unique_id,
            )
            results[group_key] = 0
            continue

        if clear_existing:
            try:
                get_instance(hass).async_clear_statistics([entity_id])
                _LOGGER.info("Estadísticas previas eliminadas para %s", entity_id)
            except Exception as err:
                _LOGGER.debug("No se pudieron limpiar estadísticas previas de %s: %s", entity_id, err)

        stats: List[StatisticData] = []
        for dt, reading, cumulative_sum in datapoints:
            dt_utc = dt_util.as_utc(dt)
            stats.append(
                StatisticData(
                    start=dt_utc,
                    state=round(reading, 3),
                    sum=round(cumulative_sum, 3),
                )
            )

        metadata_kwargs: Dict[str, Any] = {
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_of_measurement": unit,
        }
        try:
            from homeassistant.components.recorder.models import StatisticMeanType
            metadata_kwargs["mean_type"] = StatisticMeanType.NONE
        except (ImportError, AttributeError):
            metadata_kwargs["mean_type"] = 0

        metadata = StatisticMetaData(**metadata_kwargs)

        try:
            async_import_statistics(hass, metadata, stats)
            _LOGGER.info(
                "Importadas con éxito %d lecturas históricas en la estadística de %s (%s)",
                len(stats),
                entity_id,
                group_key,
            )
            results[group_key] = len(stats)
        except Exception as err:
            _LOGGER.error(
                "Error al importar estadísticas históricas para %s: %s",
                entity_id,
                err,
            )
            results[group_key] = 0

    # 3. Import invoice cost statistics (€)
    cost_targets = []
    if target_group in ("hot_water", None):
        cost_targets.append(
            (
                "hot_water",
                "hot_water_total_cost",
                "€",
                "Agua Caliente Coste Facturado Acumulado",
            )
        )
    if target_group in ("heating", None):
        cost_targets.append(
            (
                "heating",
                "heating_total_cost",
                "€",
                "Calefacción Coste Facturado Acumulado",
            )
        )

    for group_key, sensor_key, unit, default_name in cost_targets:
        cost_datapoints = extract_historical_cost_datapoints(all_receipts, group_key, tz=tz)
        if not cost_datapoints:
            _LOGGER.info("No se encontraron facturas históricas para el coste de %s", group_key)
            continue

        unique_id = f"{subscriber}_{sensor_key}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        if not entity_id:
            _LOGGER.warning("No se encontró la entidad de coste %s (%s) en el registro", sensor_key, unique_id)
            continue

        if clear_existing:
            try:
                get_instance(hass).async_clear_statistics([entity_id])
                _LOGGER.info("Estadísticas de coste previas eliminadas para %s", entity_id)
            except Exception as err:
                _LOGGER.debug("No se pudieron limpiar estadísticas de coste previas de %s: %s", entity_id, err)

        cost_stats: List[StatisticData] = []
        for dt, amount, cumulative_cost in cost_datapoints:
            dt_utc = dt_util.as_utc(dt)
            cost_stats.append(
                StatisticData(
                    start=dt_utc,
                    state=cumulative_cost,
                    sum=cumulative_cost,
                )
            )

        cost_metadata_kwargs: Dict[str, Any] = {
            "has_mean": False,
            "has_sum": True,
            "name": None,
            "source": "recorder",
            "statistic_id": entity_id,
            "unit_of_measurement": unit,
        }
        try:
            from homeassistant.components.recorder.models import StatisticMeanType
            cost_metadata_kwargs["mean_type"] = StatisticMeanType.NONE
        except (ImportError, AttributeError):
            cost_metadata_kwargs["mean_type"] = 0

        metadata = StatisticMetaData(**cost_metadata_kwargs)

        try:
            async_import_statistics(hass, metadata, cost_stats)
            _LOGGER.info(
                "Importadas con éxito %d facturas históricas en la estadística de coste de %s (%s)",
                len(cost_stats),
                entity_id,
                group_key,
            )
            results[f"{group_key}_cost"] = len(cost_stats)
        except Exception as err:
            _LOGGER.error(
                "Error al importar estadísticas de coste para %s: %s",
                entity_id,
                err,
            )

    return results

