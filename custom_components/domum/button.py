"""Boutons : lancer une sauvegarde, couper toutes les sessions du bastion."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import DomumError
from .coordinator import DomumConfigEntry
from .entity import DomumEntity, DomumItemEntity, add_items


class BackupRunButton(DomumItemEntity, ButtonEntity):
    collection = "backups"
    _attr_translation_key = "backup_run"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "run")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.run_backup(self.item_id)
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()


class BastionKillButton(DomumEntity, ButtonEntity):
    _attr_translation_key = "bastion_kill"

    def __init__(self, coordinator):
        super().__init__(coordinator, "bastion_kill")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.kill_sessions()
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("bastion", "write"):
        async_add_entities([BastionKillButton(coordinator)])
    if coordinator.can("backup", "write"):
        add_items(entry, async_add_entities, "backups", lambda i: [BackupRunButton(coordinator, i)])
