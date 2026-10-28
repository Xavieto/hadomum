"""Boutons : lancer une sauvegarde, couper les sessions du bastion, purger le Multimédia."""

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


class MultimediaPurgeButton(DomumEntity, ButtonEntity):
    """Purge des épisodes vus (Domum #96), mêmes règles que la purge planifiée."""

    _attr_translation_key = "multimedia_purge"

    def __init__(self, coordinator):
        super().__init__(coordinator, "multimedia_purge")

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.purge_media()
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()


class ServerActionButton(DomumItemEntity, ButtonEntity):
    """Mise à jour ou redémarrage d'un serveur, si Domum le permet depuis Home Assistant."""

    collection = "updates"

    def __init__(self, coordinator, item, kind):
        self._kind = kind
        self._attr_translation_key = f"server_{kind}"
        super().__init__(coordinator, item, kind)

    async def async_press(self) -> None:
        try:
            await self.coordinator.client.server_action(self.item_id, self._kind)
        except DomumError as exc:
            raise HomeAssistantError(str(exc)) from exc
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("bastion", "write"):
        async_add_entities([BastionKillButton(coordinator)])
    if coordinator.can("multimedia", "write"):
        async_add_entities([MultimediaPurgeButton(coordinator)])
    if coordinator.can("updates", "write"):
        add_items(
            entry,
            async_add_entities,
            "updates",
            lambda i: [
                ServerActionButton(coordinator, i, kind)
                for kind, allowed in (("update", "can_update"), ("reboot", "can_reboot"))
                if i.get(allowed)
            ],
        )
    if coordinator.can("backup", "write"):
        add_items(entry, async_add_entities, "backups", lambda i: [BackupRunButton(coordinator, i)])
