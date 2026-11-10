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
    ATTR_CHILD,
    ATTR_CONFIG_ENTRY,
    ATTR_DESTINATION,
    ATTR_DOMAIN,
    ATTR_EVENT,
    ATTR_MINUTES,
    ATTR_MODE,
    CONF_PUNISH_MINUTES,
    CONF_PUNISH_MODE,
    DEFAULT_PUNISH_MINUTES,
    DEFAULT_PUNISH_MODE,
    DOMAIN,
    PUNISH_MODES,
    SERVICE_ADD_TIME,
    SERVICE_FAMILY_EVENT,
    SERVICE_GENERATE_ALIAS,
    SERVICE_LIFT_PUNISHMENT,
    SERVICE_PUNISH,
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

CHILD_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY): cv.string, vol.Required(ATTR_CHILD): cv.string}
)
ADD_TIME_SCHEMA = CHILD_SCHEMA.extend({vol.Required(ATTR_MINUTES): vol.All(int, vol.Range(min=1))})
PUNISH_SCHEMA = CHILD_SCHEMA.extend(
    {
        vol.Optional(ATTR_MINUTES): vol.All(int, vol.Range(min=1)),
        vol.Optional(ATTR_MODE): vol.In(PUNISH_MODES),
    }
)
EVENT_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY): cv.string, vol.Required(ATTR_EVENT): cv.string}
)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> DomumCoordinator:
    entries = [
        entry
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
        if ATTR_CONFIG_ENTRY not in call.data or entry.entry_id == call.data[ATTR_CONFIG_ENTRY]
    ]
    if len(entries) != 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="choose_entry")
    return entries[0].runtime_data


def _family_coordinator(hass: HomeAssistant, call: ServiceCall) -> DomumCoordinator:
    coordinator = _coordinator(hass, call)
    if not coordinator.can("family", "write"):
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_family_write")
    return coordinator


def _child_id(coordinator: DomumCoordinator, call: ServiceCall) -> str:
    """Identifiant d'un enfant désigné par son identifiant ou son prénom (casse ignorée)."""
    wanted = call.data[ATTR_CHILD].strip().casefold()
    for child_id, child in coordinator.items("family").items():
        if wanted in (child_id.casefold(), str(child.get("name", "")).casefold()):
            return child_id
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="unknown_child",
        translation_placeholders={"child": call.data[ATTR_CHILD]},
    )


async def _family_action(coordinator: DomumCoordinator, action) -> None:
    try:
        await action
    except DomumError as exc:
        raise HomeAssistantError(str(exc)) from exc
    await coordinator.async_request_refresh()


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Services ``domum.generate_alias`` et du module Famille."""

    async def add_time(call: ServiceCall) -> None:
        coordinator = _family_coordinator(hass, call)
        child = _child_id(coordinator, call)
        await _family_action(
            coordinator, coordinator.client.family_bonus(child, call.data[ATTR_MINUTES])
        )

    async def punish(call: ServiceCall) -> None:
        coordinator = _family_coordinator(hass, call)
        child = _child_id(coordinator, call)
        options = coordinator.config_entry.options
        await _family_action(
            coordinator,
            coordinator.client.family_punish(
                child,
                call.data.get(ATTR_MODE, options.get(CONF_PUNISH_MODE, DEFAULT_PUNISH_MODE)),
                call.data.get(
                    ATTR_MINUTES, options.get(CONF_PUNISH_MINUTES, DEFAULT_PUNISH_MINUTES)
                ),
            ),
        )

    async def lift(call: ServiceCall) -> None:
        coordinator = _family_coordinator(hass, call)
        child = _child_id(coordinator, call)
        await _family_action(coordinator, coordinator.client.family_lift(child))

    async def family_event(call: ServiceCall) -> ServiceResponse:
        coordinator = _family_coordinator(hass, call)
        try:
            touched = await coordinator.client.family_event(call.data[ATTR_EVENT])
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await coordinator.async_request_refresh()
        return {"persons": touched["persons"]}

    for name, handler, schema in (
        (SERVICE_ADD_TIME, add_time, ADD_TIME_SCHEMA),
        (SERVICE_PUNISH, punish, PUNISH_SCHEMA),
        (SERVICE_LIFT_PUNISHMENT, lift, CHILD_SCHEMA),
    ):
        hass.services.async_register(DOMAIN, name, handler, schema=schema)
    hass.services.async_register(
        DOMAIN,
        SERVICE_FAMILY_EVENT,
        family_event,
        schema=EVENT_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )

    async def generate(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
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
