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
) -> List[Tuple[datetime, float]]:
    """Extract and combine historical readings into a chronologically sorted series."""
    datapoints_map: Dict[datetime, float] = {}

    # 1. Extract from monthly history
    monthly_rows = group_data.get("monthly_history", [])
    for row in monthly_rows:
        if not isinstance(row, dict):
            continue
        reading = row.get("current_reading")
        date_str = row.get("date")
        if reading is not None and date_str:
            dt = parse_flexible_date(date_str, tz=tz)
            if dt:
                datapoints_map[dt] = float(reading)

    # 2. Extract from daily radio readings (table listaLecturasRadio)
    daily_readings = group_data.get("daily_readings", {})
    if isinstance(daily_readings, dict):
        for date_str, reading in daily_readings.items():
            if reading is not None:
                dt = parse_flexible_date(date_str, tz=tz)
                if dt:
                    datapoints_map[dt] = float(reading)

    # 3. Extract latest current reading if available
    current_reading = group_data.get("current_reading")
    current_date_str = group_data.get("current_reading_date")
    if current_reading is not None and current_date_str:
        dt = parse_flexible_date(current_date_str, tz=tz)
        if dt:
            datapoints_map[dt] = float(current_reading)

    if not datapoints_map:
        return []

    # Sort chronologically
    sorted_items = sorted(datapoints_map.items(), key=lambda item: item[0])

    # Sanitize and keep non-decreasing values (TOTAL_INCREASING sensor requirement)
    cleaned_series: List[Tuple[datetime, float]] = []
    last_valid_reading = 0.0

    for dt, reading in sorted_items:
        if reading is None or reading <= 0:
            continue
        # Avoid anomalous drops if meter hasn't reset
        if reading < last_valid_reading:
            # Check if this might be a meter replacement or minor outlier
            # If reading is significantly lower (>10% drop), skip unless it's the start
            if last_valid_reading > 0 and (last_valid_reading - reading) > 0.5:
                _LOGGER.debug(
                    "Skipping non-monotonic reading on %s: %s (previous: %s)",
                    dt,
                    reading,
                    last_valid_reading,
                )
                continue

        cleaned_series.append((dt, reading))
        last_valid_reading = reading

    return cleaned_series


async def async_import_ista_statistics(
    hass: HomeAssistant,
    coordinator: IstaDataUpdateCoordinator,
    target_group: Optional[str] = None,
) -> Dict[str, int]:
    """Import historical readings from Ista into Home Assistant recorder statistics."""
    if "recorder" not in hass.config.components:
        _LOGGER.warning("El componente 'recorder' no está disponible. No se pueden importar estadísticas.")
        return {}

    try:
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

        stats: List[StatisticData] = []
        for dt, reading in datapoints:
            dt_utc = dt_util.as_utc(dt)
            # For TOTAL_INCREASING meters, state and sum track the cumulative reading
            stats.append(
                StatisticData(
                    start=dt_utc,
                    state=round(reading, 3),
                    sum=round(reading, 3),
                )
            )

        metadata = StatisticMetaData(
            has_mean=False,
            has_sum=True,
            name=None,
            source="recorder",
            statistic_id=entity_id,
            unit_of_measurement=unit,
        )

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

    return results
