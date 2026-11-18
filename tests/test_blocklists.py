"""Listes de blocage de Domum (#238) : interrupteur par application autorisée, relevé, capteur."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from .conftest import API, state

BLOCKLISTS = {
    "retained": 2417,
    "networks": 2391,
    "generated_at": "2026-11-18T03:14:00+00:00",
    "errors": 0,
    "apps": [{"id": "bastion", "name": "Bastion", "enabled": True}],
}


def ours(hass, domain):
    """Entités des listes de blocage d'un domaine (switch, sensor, button)."""
    return [
        s
        for s in hass.states.async_all(domain)
        if any(word in s.entity_id for word in ("blocage", "blocklists", "bastion"))
    ]


def with_blocklists(level="write", data=None):
    return state(scopes={"blocklists": level}, blocklists=BLOCKLISTS if data is None else data)


async def _setup(hass, aioclient_mock, entry, data):
    aioclient_mock.get(f"{API}/state", json=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_each_authorized_application_gets_a_switch(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_blocklists())
    switch = ours(hass, "switch")[0]
    assert switch.state == "on"
    aioclient_mock.post(f"{API}/blocklists/apps/bastion", json=BLOCKLISTS)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
    )
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[-1][1].path.endswith("/blocklists/apps/bastion")
    assert posts[-1][2] == {"enabled": False}
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": switch.entity_id}, blocking=True
    )
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[-1][2] == {"enabled": True}


async def test_a_refused_application_change_is_reported(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_blocklists())
    switch = ours(hass, "switch")[0]
    aioclient_mock.post(
        f"{API}/blocklists/apps/bastion",
        status=403,
        json={"detail": "Application non pilotable depuis Home Assistant"},
    )
    with pytest.raises(HomeAssistantError, match="non pilotable"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": switch.entity_id}, blocking=True
        )


async def test_the_refresh_button_and_the_sensor(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_blocklists())
    sensor = ours(hass, "sensor")[0]
    assert sensor.state == "2417"
    assert sensor.attributes["networks"] == 2391 and sensor.attributes["errors"] == 0
    button = ours(hass, "button")[0]
    aioclient_mock.post(f"{API}/blocklists/refresh", status=202, json={"job_id": "j1"})
    await hass.services.async_call(
        "button", "press", {"entity_id": button.entity_id}, blocking=True
    )
    assert aioclient_mock.mock_calls[-2][1].path.endswith("/blocklists/refresh")
    aioclient_mock.clear_requests()
    aioclient_mock.post(f"{API}/blocklists/refresh", status=500, json={"detail": "Panne"})
    with pytest.raises(HomeAssistantError, match="Panne"):
        await hass.services.async_call(
            "button", "press", {"entity_id": button.entity_id}, blocking=True
        )


async def test_the_sensor_is_unavailable_without_data(hass, aioclient_mock, entry):
    data = with_blocklists(level="read")
    del data["blocklists"]
    await _setup(hass, aioclient_mock, entry, data)
    sensors = ours(hass, "sensor")
    assert sensors and sensors[0].state == "unavailable"
    assert not ours(hass, "switch") and not ours(hass, "button")
