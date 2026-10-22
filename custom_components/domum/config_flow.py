"""Assistant de configuration : adresse de Domum et jeton d'intégration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import DomumAuthError, DomumClient, DomumError
from .const import DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL, default="https://tools.roques.bzh"): str,
        vol.Required(CONF_API_TOKEN): str,
        vol.Required(CONF_VERIFY_SSL, default=True): bool,
    }
)


class DomumConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _check(self, url: str, token: str, verify: bool) -> tuple[dict | None, dict]:
        session = async_get_clientsession(self.hass, verify_ssl=verify)
        try:
            return await DomumClient(session, url, token).info(), {}
        except DomumAuthError:
            return None, {"base": "invalid_auth"}
        except DomumError:
            return None, {"base": "cannot_connect"}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            info, errors = await self._check(
                url, user_input[CONF_API_TOKEN], user_input[CONF_VERIFY_SSL]
            )
            if info is not None:
                await self.async_set_unique_id(f"{url}|{info['name']}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Domum ({info['name']})", data={**user_input, CONF_URL: url}
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            info, errors = await self._check(
                entry.data[CONF_URL],
                user_input[CONF_API_TOKEN],
                entry.data.get(CONF_VERIFY_SSL, True),
            )
            if info is not None:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_TOKEN: user_input[CONF_API_TOKEN]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
