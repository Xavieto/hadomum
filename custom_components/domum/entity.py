"""Entité de base : un appareil « Domum » par entrée de configuration."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DomumConfigEntry, DomumCoordinator


class DomumEntity(CoordinatorEntity[DomumCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: DomumCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Domum",
            manufacturer="Domum",
            sw_version=(coordinator.data or {}).get("version"),
            configuration_url=coordinator.client.url,
        )


class DomumItemEntity(DomumEntity):
    """Entité attachée à un élément d'une liste (sauvegarde, alias…)."""

    collection: str

    def __init__(self, coordinator: DomumCoordinator, item: dict, suffix: str) -> None:
        super().__init__(coordinator, f"{self.collection}_{item['id']}_{suffix}")
        self.item_id = item["id"]
        self._attr_translation_placeholders = {"name": item.get("name") or item.get("address")}

    @property
    def item(self) -> dict | None:
        return self.coordinator.items(self.collection).get(self.item_id)

    @property
    def available(self) -> bool:
        return super().available and self.item is not None


def add_items(
    entry: DomumConfigEntry,
    add: Callable[[Iterable[Entity]], None],
    collection: str,
    build: Callable[[dict], list[Entity]],
) -> None:
    """Crée les entités des éléments présents, puis de ceux qui apparaissent ensuite."""
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def discover() -> None:
        new = [item for key, item in coordinator.items(collection).items() if key not in known]
        known.update(item["id"] for item in new)
        entities = [entity for item in new for entity in build(item)]
        if entities:
            add(entities)

    discover()
    entry.async_on_unload(coordinator.async_add_listener(discover))
