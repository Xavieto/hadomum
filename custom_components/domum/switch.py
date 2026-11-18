"""Interrupteurs : alias exposés, enfants (trois chacun), applications des listes de blocage."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DomumError
from .const import (
    CONF_PUNISH_MINUTES,
    CONF_PUNISH_MODE,
    DEFAULT_PUNISH_MINUTES,
    DEFAULT_PUNISH_MODE,
)
from .coordinator import DomumConfigEntry
from .entity import DomumFamilyEntity, DomumItemEntity, add_items


class AliasSwitch(DomumItemEntity, SwitchEntity):
    collection = "aliases"
    _attr_translation_key = "alias"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "switch")

    @property
    def is_on(self) -> bool:
        return bool((self.item or {}).get("active"))

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        return {"destination": item.get("destination"), "description": item.get("description")}

    async def _set(self, active: bool) -> None:
        try:
            await self.coordinator.client.set_alias(self.item_id, active)
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class BlocklistAppSwitch(DomumItemEntity, SwitchEntity):
    """Application des listes de blocage (Domum #238) : Bastion, UniFi ou Reverse Proxy.

    Seules les applications que Domum autorise pour Home Assistant sont dans l'état.
    """

    collection = "blocklists.apps"
    _attr_translation_key = "blocklist_app"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "switch")

    @property
    def is_on(self) -> bool:
        return bool((self.item or {}).get("enabled"))

    async def _set(self, enabled: bool) -> None:
        try:
            await self.coordinator.client.set_blocklist_app(self.item_id, enabled)
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class FamilySwitch(DomumFamilyEntity, SwitchEntity):
    """Internet (pause), punition (durée et mode des options) ou mode vacances d'un enfant."""

    def __init__(self, coordinator, item, kind):
        self._kind = kind
        self._attr_translation_key = f"family_{kind}"
        super().__init__(coordinator, item, kind)

    @property
    def is_on(self) -> bool:
        item = self.item or {}
        if self._kind == "internet":
            return not item.get("paused")
        return bool(item.get("punished" if self._kind == "punish" else "vacation"))

    @property
    def extra_state_attributes(self) -> dict:
        if self._kind != "punish":
            return {}
        item = self.item or {}
        return {"punish_until": item.get("punish_until"), "punish_mode": item.get("punish_mode")}

    async def _call(self, action) -> None:
        try:
            await action
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()

    async def _set(self, on: bool) -> None:
        client = self.coordinator.client
        if self._kind == "internet":
            await self._call(client.family_pause(self.item_id, not on))
        elif self._kind == "vacation":
            await self._call(client.family_vacation(self.item_id, on))
        elif on:
            options = self.coordinator.config_entry.options
            await self._call(
                client.family_punish(
                    self.item_id,
                    options.get(CONF_PUNISH_MODE, DEFAULT_PUNISH_MODE),
                    options.get(CONF_PUNISH_MINUTES, DEFAULT_PUNISH_MINUTES),
                )
            )
        else:
            await self._call(client.family_lift(self.item_id))

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("alias", "write"):
        add_items(entry, async_add_entities, "aliases", lambda i: [AliasSwitch(coordinator, i)])
    if coordinator.can("blocklists", "write"):
        add_items(
            entry,
            async_add_entities,
            "blocklists.apps",
            lambda i: [BlocklistAppSwitch(coordinator, i)],
        )
    if coordinator.can("family", "write"):
        add_items(
            entry,
            async_add_entities,
            "family",
            lambda i: [FamilySwitch(coordinator, i, k) for k in ("internet", "punish", "vacation")],
        )
