"""Config flow for Ista integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_DOWNLOAD_INVOICES,
    CONF_HEATING_PRICE,
    CONF_HOT_WATER_PRICE,
    CONF_INVOICES_PATH,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_DOWNLOAD_INVOICES,
    DEFAULT_HEATING_PRICE,
    DEFAULT_HOT_WATER_PRICE,
    DEFAULT_INVOICES_PATH,
    DEFAULT_SCAN_INTERVAL_HOURS,
    DOMAIN,
)
from .ista_client import IstaAuthError, IstaClient, IstaConnectionError

_LOGGER = logging.getLogger(__name__)


async def validate_credentials(hass: HomeAssistant, username: str, password: str) -> None:
    """Validate user credentials by attempting to log in."""
    client = IstaClient(username=username, password=password)
    await hass.async_add_executor_job(client.login)


class IstaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ista."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step where user inputs email and password."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                await validate_credentials(self.hass, username, password)
            except IstaAuthError:
                errors["base"] = "invalid_auth"
            except IstaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during Ista validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Ista ({username})",
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                    },
                    options={
                        CONF_SCAN_INTERVAL: user_input.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
                        ),
                        CONF_DOWNLOAD_INVOICES: DEFAULT_DOWNLOAD_INVOICES,
                        CONF_INVOICES_PATH: DEFAULT_INVOICES_PATH,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.EMAIL,
                        autocomplete="email",
                    )
                ),
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD,
                        autocomplete="current-password",
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_HOURS
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1,
                        max=48,
                        step=1,
                        unit_of_measurement="horas",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication with new password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors: Dict[str, str] = {}
        reauth_entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])

        if user_input is not None and reauth_entry:
            username = reauth_entry.data[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            try:
                await validate_credentials(self.hass, username, password)
            except IstaAuthError:
                errors["base"] = "invalid_auth"
            except IstaConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during Ista reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_PASSWORD: password,
                    },
                )
                await self.hass.config_entries.async_reload(reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                            autocomplete="current-password",
                        )
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return IstaOptionsFlowHandler(config_entry)


class IstaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Ista."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_HOURS
        )
        current_download = self.config_entry.options.get(
            CONF_DOWNLOAD_INVOICES, DEFAULT_DOWNLOAD_INVOICES
        )
        current_path = self.config_entry.options.get(
            CONF_INVOICES_PATH, DEFAULT_INVOICES_PATH
        )
        current_hw_price = self.config_entry.options.get(
            CONF_HOT_WATER_PRICE, DEFAULT_HOT_WATER_PRICE
        )
        current_heating_price = self.config_entry.options.get(
            CONF_HEATING_PRICE, DEFAULT_HEATING_PRICE
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=48,
                            step=1,
                            unit_of_measurement="horas",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_DOWNLOAD_INVOICES, default=current_download
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_INVOICES_PATH, default=current_path
                    ): selector.TextSelector(),
                    vol.Optional(
                        CONF_HOT_WATER_PRICE, default=float(current_hw_price)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.0,
                            max=1000.0,
                            step=0.01,
                            unit_of_measurement="€/m³",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(
                        CONF_HEATING_PRICE, default=float(current_heating_price)
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.0,
                            max=1000.0,
                            step=0.001,
                            unit_of_measurement="€/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )
