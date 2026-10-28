"""Supervision, mises à jour et calendrier du planning."""

from datetime import timedelta

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.domum.calendar import _event

from .conftest import API, state

METRICS = {
    "load": [0.42, 0.3, 0.2],
    "cores": 2,
    "memory": 62.0,
    "filesystems": [{"mount": "/", "used": 81}, {"mount": "/data", "used": 40}],
}


def operations(**changes):
    scopes = changes.pop("scopes", {"monitoring": "read", "updates": "write", "planning": "read"})
    return state(
        scopes=scopes,
        monitoring={
            "servers": [
                {
                    "id": "s1",
                    "name": "VPS",
                    "status": "alert",
                    "message": "/ à 81 %",
                    "saturated": ["/data"],
                    "since": None,
                    "checked_at": None,
                    "data": {"metrics": METRICS},
                },
                {
                    "id": "s2",
                    "name": "HAOS",
                    "status": "ok",
                    "message": None,
                    "since": None,
                    "checked_at": None,
                    "data": {},
                },
                {
                    "id": "s3",
                    "name": "Vide",
                    "status": "ok",
                    "message": None,
                    "since": None,
                    "checked_at": None,
                    "data": {"metrics": {**METRICS, "filesystems": []}},
                },
            ],
            "filesystems": [
                {
                    "id": "s1-aaa",
                    "name": "VPS /data",
                    "server_id": "s1",
                    "mount": "/data",
                    "size_kb": 1000,
                    "used": 96,
                    "threshold": 95,
                    "limit": 95,
                    "alert": False,
                    "present": True,
                    "over": True,
                },
                {
                    "id": "s1-bbb",
                    "name": "VPS /media/usb",
                    "server_id": "s1",
                    "mount": "/media/usb",
                    "size_kb": None,
                    "used": None,
                    "threshold": None,
                    "limit": 90,
                    "alert": True,
                    "present": False,
                    "over": False,
                },
            ],
            "checks": [
                {
                    "id": "h1",
                    "name": "Cloud",
                    "status": "ok",
                    "message": None,
                    "since": None,
                    "checked_at": None,
                    "data": {},
                }
            ],
        },
        updates=[
            {
                "id": "s1",
                "name": "VPS",
                "critical_fixable": True,
                "high_fixable": False,
                "fixable": 3,
                "packages": 12,
                "reboot_required": True,
                "scanned_at": None,
                "running": False,
                "can_update": True,
                "can_reboot": False,
            },
        ],
        **changes,
    )


def calendar_events(start, end):
    now = dt_util.utcnow()
    return [
        {
            "kind": "backup",
            "title": "Domum",
            "start": (now + timedelta(hours=2)).isoformat(),
            "end": (now + timedelta(hours=3)).isoformat(),
            "servers": ["VPS"],
            "clash": True,
        },
        {
            "kind": "task",
            "title": "Purge CCTV",
            "start": (now + timedelta(hours=4)).isoformat(),
            "end": (now + timedelta(hours=5)).isoformat(),
            "servers": ["CCTV"],
            "clash": False,
        },
        {
            "kind": "maintenance",
            "title": "Maintenance",
            "start": (now + timedelta(hours=1)).isoformat(),
            "end": (now + timedelta(hours=2)).isoformat(),
            "servers": [],
            "clash": False,
        },
    ]


async def _setup(hass, aioclient_mock, entry, data=None, calendar=None):
    aioclient_mock.get(f"{API}/state", json=data or operations())
    aioclient_mock.get(
        f"{API}/calendar", json=calendar if calendar is not None else calendar_events(None, None)
    )
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_monitoring_and_updates_entities(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    assert hass.states.get("binary_sensor.domum_monitoring_vps_problem").state == "on"
    assert (
        hass.states.get("binary_sensor.domum_monitoring_vps_problem").attributes["message"]
        == "/ à 81 %"
    )
    assert hass.states.get("binary_sensor.domum_monitoring_cloud_problem").state == "off"
    assert hass.states.get("sensor.domum_monitoring_vps_load").state == "0.42"
    assert hass.states.get("sensor.domum_monitoring_vps_memory").state == "62.0"
    assert hass.states.get("sensor.domum_monitoring_vps_fullest_disk").state == "81"
    assert hass.states.get("sensor.domum_monitoring_haos_load").state == "unknown"
    assert hass.states.get("sensor.domum_monitoring_vide_fullest_disk").state == "unknown"
    assert hass.states.get("binary_sensor.domum_monitoring_vps_problem").attributes[
        "saturated"
    ] == ["/data"]
    assert (
        hass.states.get("binary_sensor.domum_monitoring_haos_problem").attributes["saturated"] == []
    )
    data = hass.states.get("sensor.domum_monitoring_vps_data_usage")
    assert data.state == "96" and data.attributes["unit_of_measurement"] == "%"
    assert data.attributes["saturated"] is True and data.attributes["alert"] is False
    assert data.attributes["threshold"] == 95 and data.attributes["mount"] == "/data"
    assert hass.states.get("sensor.domum_monitoring_vps_media_usb_usage").state == "unknown"
    assert hass.states.get("binary_sensor.domum_updates_vps_fixable_critical_flaw").state == "on"
    assert hass.states.get("binary_sensor.domum_updates_vps_fixable_high_flaw").state == "off"
    assert hass.states.get("binary_sensor.domum_updates_vps_reboot_required").state == "on"
    assert hass.states.get("sensor.domum_updates_vps_pending_packages").state == "12"
    assert hass.states.get("button.domum_updates_vps_update") is not None
    assert hass.states.get("button.domum_updates_vps_reboot") is None


async def test_server_actions(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    aioclient_mock.post(f"{API}/servers/s1/update", status=202, json={"id": "r1"})
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.domum_updates_vps_update"}, blocking=True
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/state", json=operations())
    aioclient_mock.post(
        f"{API}/servers/s1/update",
        status=403,
        json={"detail": "La mise à jour depuis Home Assistant n'est pas permise sur ce serveur"},
    )
    with pytest.raises(HomeAssistantError, match="pas permise"):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.domum_updates_vps_update"}, blocking=True
        )


async def test_read_only_updates_get_no_buttons(hass, aioclient_mock, entry):
    data = operations(scopes={"updates": "read"})
    await _setup(hass, aioclient_mock, entry, data)
    assert hass.states.get("button.domum_updates_vps_update") is None
    assert hass.states.get("calendar.domum_planning") is None


async def test_the_planning_calendar(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    calendar = hass.states.get("calendar.domum_planning")
    assert calendar.attributes["message"] == "Maintenance : Maintenance"
    now = dt_util.now()
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": "calendar.domum_planning",
            "start_date_time": now,
            "end_date_time": now + timedelta(days=40),
        },
        blocking=True,
        return_response=True,
    )
    events = response["calendar.domum_planning"]["events"]
    # Deux requêtes de 28 jours au plus : les évènements sont repris pour chaque période.
    assert len(events) == 6
    assert any(e["summary"] == "Tâche : Purge CCTV" for e in events)
    spans = [
        dt_util.parse_datetime(url.query["end"]) - dt_util.parse_datetime(url.query["start"])
        for method, url, *_ in aioclient_mock.mock_calls
        if url.path.endswith("/calendar")
    ]
    # Une heure de plus au changement d'heure : toujours sous la limite de 31 jours de Domum.
    assert max(spans) < timedelta(days=31)
    assert any(
        e["summary"] == "Sauvegarde : Domum (chevauchement)" and e["description"] == "VPS"
        for e in events
    )


async def test_calendar_errors(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{API}/state", json=operations())
    aioclient_mock.get(f"{API}/calendar", status=500, json={})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("calendar.domum_planning").state == "off"
    now = dt_util.now()
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "calendar",
            "get_events",
            {
                "entity_id": "calendar.domum_planning",
                "start_date_time": now,
                "end_date_time": now + timedelta(days=1),
            },
            blocking=True,
            return_response=True,
        )


def test_events_without_servers_have_no_description():
    now = dt_util.utcnow()
    event = _event(
        {
            "kind": "autre",
            "title": "X",
            "start": now.isoformat(),
            "end": now.isoformat(),
            "servers": [],
        }
    )
    assert (event.summary, event.description) == ("autre : X", None)


async def test_multimedia_latest_additions_and_purge(hass, aioclient_mock, entry):
    latest = [
        {
            "id": "n1",
            "title": "Frieren",
            "detail": "S02E05",
            "category": "Animes",
            "added_at": "2026-10-27T21:00:00+00:00",
        }
    ]
    data = operations(
        scopes={"multimedia": "write"},
        multimedia={"latest": latest, "purgeable": 3, "last_purge": None},
    )
    await _setup(hass, aioclient_mock, entry, data)
    sensor = hass.states.get("sensor.domum_multimedia_latest_additions")
    assert sensor.state == "1" and sensor.attributes["items"] == latest
    assert sensor.attributes["purgeable"] == 3
    aioclient_mock.post(f"{API}/multimedia/purge", status=202, json={"id": "p1"})
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.domum_multimedia_purge"}, blocking=True
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/state", json=data)
    aioclient_mock.post(
        f"{API}/multimedia/purge", status=409, json={"detail": "Une purge est déjà en cours"}
    )
    with pytest.raises(HomeAssistantError, match="déjà en cours"):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.domum_multimedia_purge"}, blocking=True
        )


async def test_multimedia_read_only_and_missing_data(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, operations(scopes={"multimedia": "read"}))
    assert hass.states.get("button.domum_multimedia_purge") is None
    assert hass.states.get("sensor.domum_multimedia_latest_additions").state == "unavailable"
