"""Capteurs : état et dernière réussite de chaque sauvegarde, sessions actives du bastion."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import BACKUP_STATES
from .coordinator import DomumConfigEntry
from .entity import DomumEntity, DomumItemEntity, add_items


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class BackupStateSensor(DomumItemEntity, SensorEntity):
    collection = "backups"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = BACKUP_STATES
    _attr_translation_key = "backup_state"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "state")

    @property
    def native_value(self) -> str | None:
        item = self.item or {}
        state = item.get("state")
        return state if state in BACKUP_STATES else None

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        return {
            key: item.get(key)
            for key in (
                "flux",
                "type",
                "enabled",
                "last_run_at",
                "last_status",
                "last_size",
                "last_duration",
                "next_run_at",
            )
        }


class BackupLastSuccessSensor(DomumItemEntity, SensorEntity):
    collection = "backups"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_translation_key = "backup_last_success"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "last_success")

    @property
    def native_value(self) -> datetime | None:
        return _time((self.item or {}).get("last_success_at"))


class BastionSessionsSensor(DomumEntity, SensorEntity):
    _attr_translation_key = "bastion_sessions"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator):
        super().__init__(coordinator, "bastion_sessions")

    @property
    def available(self) -> bool:
        return super().available and "bastion" in self.coordinator.data

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("bastion", {}).get("active_sessions")


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("bastion"):
        async_add_entities([BastionSessionsSensor(coordinator)])
    add_items(
        entry,
        async_add_entities,
        "backups",
        lambda item: [
            BackupStateSensor(coordinator, item),
            BackupLastSuccessSensor(coordinator, item),
        ],
    )
