"""DataUpdateCoordinator for Ista integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN
from .ista_client import IstaAuthError, IstaClient, IstaConnectionError

_LOGGER = logging.getLogger(__name__)


class IstaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Class to manage fetching Ista data from the portal."""

    def __init__(
        self,
        hass: HomeAssistant,
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
        self.client = client

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Ista portal via executor."""
        try:
            return await self.hass.async_add_executor_job(self.client.fetch_data)
        except IstaAuthError as err:
            raise UpdateFailed(f"Authentication error with Ista portal: {err}") from err
        except IstaConnectionError as err:
            raise UpdateFailed(f"Connection error with Ista portal: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error updating Ista data: {err}") from err
