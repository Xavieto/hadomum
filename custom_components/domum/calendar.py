"""Calendrier « Domum » : sauvegardes, mises à jour planifiées et plages de maintenance."""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import DomumError
from .coordinator import DomumConfigEntry
from .entity import DomumEntity

SPAN = timedelta(days=31)  # période maximale d'une requête à Domum
KINDS = {"backup": "Sauvegarde", "update": "Mise à jour", "maintenance": "Maintenance"}


def _event(data: dict) -> CalendarEvent:
    servers = ", ".join(data.get("servers") or [])
    clash = " (chevauchement)" if data.get("clash") else ""
    return CalendarEvent(
        start=dt_util.parse_datetime(data["start"]),
        end=dt_util.parse_datetime(data["end"]),
        summary=f"{KINDS.get(data['kind'], data['kind'])} : {data['title']}{clash}",
        description=servers or None,
    )


class DomumCalendar(DomumEntity, CalendarEntity):
    _attr_translation_key = "planning"

    def __init__(self, coordinator):
        super().__init__(coordinator, "planning")
        self._next: CalendarEvent | None = None

    @property
    def event(self) -> CalendarEvent | None:
        return self._next

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        events: list[CalendarEvent] = []
        start = start_date
        while start < end_date:
            end = min(start + SPAN, end_date)
            try:
                found = await self.coordinator.client.calendar(start.isoformat(), end.isoformat())
            except DomumError as exc:
                raise HomeAssistantError(str(exc)) from exc
            events += [_event(item) for item in found]
            start = end
        return events

    async def async_update(self) -> None:
        now = dt_util.now()
        try:
            upcoming = await self.async_get_events(self.hass, now, now + timedelta(days=7))
        except HomeAssistantError:
            return
        self._next = min(upcoming, key=lambda e: e.start, default=None)


async def async_setup_entry(
    hass: HomeAssistant, entry: DomumConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    if coordinator.can("planning"):
        async_add_entities([DomumCalendar(coordinator)], update_before_add=True)
