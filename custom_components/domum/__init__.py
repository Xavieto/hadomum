"""Intégration Domum : état des sauvegardes, du bastion et des alias, actions du jeton."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import DomumClient, DomumError
from .const import (
    ATTR_CONFIG_ENTRY,
    ATTR_DESTINATION,
    ATTR_DOMAIN,
    DOMAIN,
    SERVICE_GENERATE_ALIAS,
)
from .coordinator import DomumConfigEntry, DomumCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.SWITCH,
]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

GENERATE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY): cv.string,
        vol.Optional(ATTR_DESTINATION): cv.string,
        vol.Optional(ATTR_DOMAIN): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Service ``domum.generate_alias`` : alias aléatoire actif, adresse renvoyée."""

    async def generate(call: ServiceCall) -> ServiceResponse:
        entries = [
            entry
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            if ATTR_CONFIG_ENTRY not in call.data or entry.entry_id == call.data[ATTR_CONFIG_ENTRY]
        ]
        if len(entries) != 1:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="choose_entry")
        coordinator: DomumCoordinator = entries[0].runtime_data
        if not coordinator.can("alias", "write"):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="no_alias_write"
            )
        try:
            created = await coordinator.client.generate_alias(
                call.data.get(ATTR_DESTINATION), call.data.get(ATTR_DOMAIN)
            )
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await coordinator.async_request_refresh()
        return {"address": created["address"], "destination": created["destination"]}

    hass.services.async_register(
        DOMAIN,
        SERVICE_GENERATE_ALIAS,
        generate,
        schema=GENERATE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DomumConfigEntry) -> bool:
    session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))
    client = DomumClient(session, entry.data[CONF_URL], entry.data[CONF_API_TOKEN])
    coordinator = DomumCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DomumConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
