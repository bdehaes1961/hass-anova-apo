"""Config flow for the Anova Precision Oven integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import AnovaApoApi, InvalidAuth, NoDevicesFound
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_ACCESS_TOKEN): str})


class AnovaApoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Anova Precision Oven config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            token = user_input[CONF_ACCESS_TOKEN].strip()
            api = AnovaApoApi(async_get_clientsession(self.hass), token)
            try:
                devices = await api.async_validate()
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoDevicesFound:
                errors["base"] = "no_devices"
            except Exception:  # noqa: BLE001
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(token[-24:])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Anova Precision Oven ({len(devices)})",
                    data={CONF_ACCESS_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with a new token."""
        return await self.async_step_user(user_input)
