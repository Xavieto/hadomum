"""Capteurs : sauvegardes, bastion, métriques et systèmes de fichiers supervisés, mises à jour."""

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


class MonitoringMetricSensor(DomumItemEntity, SensorEntity):
    """Charge, mémoire ou système de fichiers le plus plein d'un serveur supervisé."""

    collection = "monitoring.servers"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, item, metric):
        self._metric = metric
        self._attr_translation_key = f"monitoring_{metric}"
        if metric != "load":
            self._attr_native_unit_of_measurement = "%"
        super().__init__(coordinator, item, metric)

    @property
    def native_value(self) -> float | None:
        metrics = ((self.item or {}).get("data") or {}).get("metrics")
        if not metrics:
            return None
        if self._metric == "load":
            return metrics["load"][0]
        if self._metric == "memory":
            return metrics["memory"]
        return max((fs["used"] for fs in metrics["filesystems"]), default=None)


class FilesystemSensor(DomumItemEntity, SensorEntity):
    """Utilisation d'un système de fichiers d'un serveur supervisé (Domum 2.8.1).

    La saturation reste visible même quand Domum n'alerte pas pour ce point de montage.
    """

    collection = "monitoring.filesystems"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"
    _attr_translation_key = "monitoring_filesystem"

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "usage")

    @property
    def native_value(self) -> int | None:
        return (self.item or {}).get("used")

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        return {
            "server_id": item.get("server_id"),
            "mount": item.get("mount"),
            "size_kb": item.get("size_kb"),
            "threshold": item.get("limit"),
            "alert": item.get("alert"),
            "saturated": item.get("over"),
            "present": item.get("present"),
        }


class UpdatesPackagesSensor(DomumItemEntity, SensorEntity):
    collection = "updates"
    _attr_translation_key = "updates_packages"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, item):
        super().__init__(coordinator, item, "packages")

    @property
    def native_value(self) -> int | None:
        return (self.item or {}).get("packages")

    @property
    def extra_state_attributes(self) -> dict:
        item = self.item or {}
        return {"fixable": item.get("fixable"), "scanned_at": item.get("scanned_at")}


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("bastion"):
        async_add_entities([BastionSessionsSensor(coordinator)])
    add_items(
        entry,
        async_add_entities,
        "monitoring.servers",
        lambda item: [
            MonitoringMetricSensor(coordinator, item, metric)
            for metric in ("load", "memory", "disk")
        ],
    )
    add_items(
        entry,
        async_add_entities,
        "monitoring.filesystems",
        lambda item: [FilesystemSensor(coordinator, item)],
    )
    add_items(
        entry, async_add_entities, "updates", lambda i: [UpdatesPackagesSensor(coordinator, i)]
    )
    add_items(
        entry,
        async_add_entities,
        "backups",
        lambda item: [
            BackupStateSensor(coordinator, item),
            BackupLastSuccessSensor(coordinator, item),
        ],
    )
