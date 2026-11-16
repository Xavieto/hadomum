"""Snippets de Domum (#231) : un bouton par snippet exposé, lancé depuis Home Assistant."""

import pytest
from homeassistant.exceptions import HomeAssistantError

from .conftest import API, state

SNIPPETS = [
    {
        "id": "s1",
        "name": "Redémarrer Traefik",
        "description": "",
        "targets": ["VPS"],
        "running": False,
        "last_status": None,
        "last_at": None,
    }
]


def with_snippets(items=None, scopes=None):
    return state(
        scopes=scopes or {"snippets": "write"}, snippets=SNIPPETS if items is None else items
    )


async def _setup(hass, aioclient_mock, entry, data):
    aioclient_mock.get(f"{API}/state", json=data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_each_exposed_snippet_gets_a_button_that_runs_it(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_snippets())
    entity = "button.domum_snippet_redemarrer_traefik_run"
    assert hass.states.get(entity) is not None
    aioclient_mock.post(f"{API}/snippets/s1/run", status=202, json={"batch_id": "b1"})
    await hass.services.async_call("button", "press", {"entity_id": entity}, blocking=True)
    assert aioclient_mock.mock_calls[-2][1].path.endswith("/snippets/s1/run")


async def test_a_refused_snippet_is_reported(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_snippets())
    aioclient_mock.post(
        f"{API}/snippets/s1/run",
        status=409,
        json={"detail": "Ce snippet ne vise aucun serveur géré"},
    )
    with pytest.raises(HomeAssistantError, match="aucun serveur"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.domum_snippet_redemarrer_traefik_run"},
            blocking=True,
        )


async def test_read_only_tokens_get_no_snippet_button(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, with_snippets(scopes={"snippets": "read"}))
    assert hass.states.get("button.domum_snippet_redemarrer_traefik_run") is None
