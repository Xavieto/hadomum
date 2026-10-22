"""Capteurs binaires : sauvegarde en problème, bastion en marche, alias actif (lecture seule)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DomumConfigEntry
from .entity import DomumEntity, DomumItemEntity, add_items


class BackupProblemSensor(DomumItemEntity, BinarySensorEntity):
    collection = "backups"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "backup_problem"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "problem")

    @property
    def is_on(self) -> bool:
        return (self.item or {}).get("state") in ("failed", "late", "partial", "interrupted")


class BastionRunningSensor(DomumEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "bastion_running"

    def __init__(self, coordinator):
        super().__init__(coordinator, "bastion_running")

    @property
    def available(self) -> bool:
        return super().available and "bastion" in self.coordinator.data

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("bastion", {}).get("alive"))


class AliasActiveSensor(DomumItemEntity, BinarySensorEntity):
    """Alias en lecture seule (jeton sans écriture sur les alias)."""

    collection = "aliases"
    _attr_translation_key = "alias_active"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "active")

    @property
    def is_on(self) -> bool:
        return bool((self.item or {}).get("active"))


class MonitoringProblemSensor(DomumItemEntity, BinarySensorEntity):
    """Anomalie de supervision d'un serveur ou d'un contrôle HTTP."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "monitoring_problem"

    def __init__(self, coordinator, item, collection):
        self.collection = collection
        super().__init__(coordinator, item, "problem")

    @property
    def is_on(self) -> bool:
        return (self.item or {}).get("status") == "alert"

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        return {"message": item.get("message"), "checked_at": item.get("checked_at")}


class UpdatesFlagSensor(DomumItemEntity, BinarySensorEntity):
    """Faille critique ou haute corrigeable non corrigée, redémarrage requis."""

    collection = "updates"

    def __init__(self, coordinator, item, key, device_class):
        self._key = key
        self._attr_translation_key = key
        self._attr_device_class = device_class
        super().__init__(coordinator, item, key)

    @property
    def is_on(self) -> bool:
        return bool((self.item or {}).get(self._key))


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("bastion"):
        async_add_entities([BastionRunningSensor(coordinator)])
    add_items(entry, async_add_entities, "backups", lambda i: [BackupProblemSensor(coordinator, i)])
    for collection in ("monitoring.servers", "monitoring.checks"):
        add_items(
            entry,
            async_add_entities,
            collection,
            lambda i, c=collection: [MonitoringProblemSensor(coordinator, i, c)],
        )
    add_items(
        entry,
        async_add_entities,
        "updates",
        lambda i: [
            UpdatesFlagSensor(coordinator, i, "critical_fixable", BinarySensorDeviceClass.SAFETY),
            UpdatesFlagSensor(coordinator, i, "high_fixable", BinarySensorDeviceClass.SAFETY),
            UpdatesFlagSensor(coordinator, i, "reboot_required", BinarySensorDeviceClass.UPDATE),
        ],
    )
    if not coordinator.can("alias", "write"):
        add_items(
            entry, async_add_entities, "aliases", lambda i: [AliasActiveSensor(coordinator, i)]
        )
