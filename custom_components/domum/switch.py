"""Interrupteurs : un par alias exposé (jeton avec écriture sur les alias)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DomumError
from .coordinator import DomumConfigEntry
from .entity import DomumItemEntity, add_items


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


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("alias", "write"):
        add_items(entry, async_add_entities, "aliases", lambda i: [AliasSwitch(coordinator, i)])
