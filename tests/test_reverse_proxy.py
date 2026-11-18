"""Reverse Proxy de Domum (#251) : un interrupteur par redirection et par flux autorisés."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from .conftest import API, state

PROXY = {
    "alive": True,
    "errors": 0,
    "routes": [{"id": "r1", "name": "nextcloud.example.org", "enabled": True}],
    "streams": [{"id": "s1", "name": "SSH", "enabled": False}],
}


async def _setup(hass, aioclient_mock, entry, level="write"):
    aioclient_mock.get(
        f"{API}/state", json=state(scopes={"reverse_proxy": level}, reverse_proxy=PROXY)
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def switches(hass):
    return {
        s.entity_id: s for s in hass.states.async_all("switch") if "reverse_proxy" in s.entity_id
    }


async def test_routes_and_streams_get_a_switch(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    found = switches(hass)
    assert len(found) == 2
    route = next(s for s in found.values() if s.state == "on")
    stream = next(s for s in found.values() if s.state == "off")
    aioclient_mock.post(f"{API}/reverse-proxy/routes/r1", json=PROXY)
    aioclient_mock.post(f"{API}/reverse-proxy/streams/s1", json=PROXY)
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": route.entity_id}, blocking=True
    )
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[-1][1].path.endswith("/reverse-proxy/routes/r1") and posts[-1][2] == {
        "enabled": False
    }
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": stream.entity_id}, blocking=True
    )
    posts = [c for c in aioclient_mock.mock_calls if c[0] == "POST"]
    assert posts[-1][1].path.endswith("/reverse-proxy/streams/s1") and posts[-1][2] == {
        "enabled": True
    }


async def test_a_refused_switch_is_reported(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    route = next(s for s in switches(hass).values() if s.state == "on")
    aioclient_mock.post(
        f"{API}/reverse-proxy/routes/r1",
        status=403,
        json={"detail": "Non pilotable depuis Home Assistant"},
    )
    with pytest.raises(HomeAssistantError, match="Non pilotable"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": route.entity_id}, blocking=True
        )


async def test_read_only_tokens_get_no_switch(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, level="read")
    assert switches(hass) == {}
