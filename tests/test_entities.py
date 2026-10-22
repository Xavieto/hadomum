"""Entités, actions et service de l'intégration."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from custom_components.domum.const import DOMAIN, SERVICE_GENERATE_ALIAS

from .conftest import API, state


async def _setup(hass, aioclient_mock, entry, data=None):
    aioclient_mock.get(f"{API}/state", json=data or state())
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_entities_follow_the_state_of_domum(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    assert entry.state is ConfigEntryState.LOADED
    critique = hass.states.get("sensor.domum_critique")
    assert critique.state == "success"
    assert critique.attributes["last_size"] == 734000000
    assert hass.states.get("sensor.domum_nextcloud").state == "failed"
    assert hass.states.get("sensor.domum_critique_last_success").state.startswith("2026-10-22")
    assert hass.states.get("binary_sensor.domum_nextcloud_problem").state == "on"
    assert hass.states.get("binary_sensor.domum_critique_problem").state == "off"
    assert hass.states.get("sensor.domum_bastion_active_sessions").state == "2"
    assert hass.states.get("binary_sensor.domum_bastion").state == "on"
    assert hass.states.get("switch.domum_achats_roques_bzh").state == "on"
    assert hass.states.get("button.domum_critique_run") is not None
    assert hass.states.get("button.domum_cut_bastion_sessions") is not None


async def test_new_items_get_entities_and_vanished_ones_become_unavailable(
    hass, aioclient_mock, entry
):
    await _setup(hass, aioclient_mock, entry)
    coordinator = entry.runtime_data
    data = state()
    data["backups"] = [{**data["backups"][0], "id": "b3", "name": "Immich", "state": "weird"}]
    coordinator.async_set_updated_data(data)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.domum_immich").state == "unknown"
    assert hass.states.get("sensor.domum_critique").state == "unavailable"


async def test_read_only_tokens_get_no_actions(hass, aioclient_mock, entry):
    data = state(scopes={"backup": "read", "alias": "read"})
    del data["bastion"]
    await _setup(hass, aioclient_mock, entry, data)
    assert hass.states.get("button.domum_critique_run") is None
    assert hass.states.get("switch.domum_achats_roques_bzh") is None
    assert hass.states.get("binary_sensor.domum_achats_roques_bzh").state == "on"
    assert hass.states.get("sensor.domum_bastion_active_sessions") is None


async def test_bastion_entities_become_unavailable_without_the_bastion(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    data = state()
    del data["bastion"]
    entry.runtime_data.async_set_updated_data(data)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.domum_bastion_active_sessions").state == "unavailable"
    assert hass.states.get("binary_sensor.domum_bastion").state == "unavailable"


async def test_buttons_and_switches_call_domum(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    aioclient_mock.post(f"{API}/backups/b1/run", json={"run_id": "r1", "job_id": "j1"})
    aioclient_mock.post(f"{API}/bastion/kill-all", json={"killed": 2})
    aioclient_mock.patch(f"{API}/aliases/a1", json={})
    await hass.services.async_call(
        "button", "press", {"entity_id": "button.domum_critique_run"}, blocking=True
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": "button.domum_cut_bastion_sessions"},
        blocking=True,
    )
    for service in ("turn_off", "turn_on"):
        await hass.services.async_call(
            "switch", service, {"entity_id": "switch.domum_achats_roques_bzh"}, blocking=True
        )
    calls = [(method, str(url)) for method, url, *_ in aioclient_mock.mock_calls]
    assert ("POST", f"{API}/backups/b1/run") in calls
    assert ("POST", f"{API}/bastion/kill-all") in calls
    bodies = [data for method, _, data, *_ in aioclient_mock.mock_calls if method == "PATCH"]
    assert bodies == [{"active": False}, {"active": True}]


async def test_domum_errors_are_reported_to_the_user(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    aioclient_mock.post(f"{API}/backups/b1/run", status=409, json={"detail": "Déjà en cours"})
    aioclient_mock.post(f"{API}/bastion/kill-all", status=403, json={})
    aioclient_mock.patch(f"{API}/aliases/a1", status=502, text="pas du JSON")
    with pytest.raises(HomeAssistantError, match="Déjà en cours"):
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.domum_critique_run"}, blocking=True
        )
    with pytest.raises(HomeAssistantError, match="HTTP 403"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.domum_cut_bastion_sessions"},
            blocking=True,
        )
    with pytest.raises(HomeAssistantError, match="HTTP 502"):
        await hass.services.async_call(
            "switch", "turn_off", {"entity_id": "switch.domum_achats_roques_bzh"}, blocking=True
        )


async def test_an_unreachable_domum_is_retried(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{API}/state", exc=TimeoutError())
    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_the_entry_unloads(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_an_alias_is_generated_and_returned(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    aioclient_mock.post(
        f"{API}/aliases/generate",
        status=201,
        json={"id": "a9", "address": "k3x9@roques.bzh", "destination": "moi@exemple.fr"},
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GENERATE_ALIAS,
        {"destination": "moi@exemple.fr"},
        blocking=True,
        return_response=True,
    )
    assert response == {"address": "k3x9@roques.bzh", "destination": "moi@exemple.fr"}
    body = [d for m, u, d, *_ in aioclient_mock.mock_calls if str(u).endswith("/generate")][0]
    assert body == {"destination": "moi@exemple.fr"}


async def test_alias_generation_errors(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GENERATE_ALIAS,
            {"config_entry_id": "inconnue"},
            blocking=True,
            return_response=True,
        )
    aioclient_mock.post(f"{API}/aliases/generate", status=422, json={"detail": "Précisez"})
    with pytest.raises(HomeAssistantError, match="Précisez"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GENERATE_ALIAS,
            {"config_entry_id": entry.entry_id},
            blocking=True,
            return_response=True,
        )
    entry.runtime_data.async_set_updated_data(state(scopes={"alias": "read"}))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, SERVICE_GENERATE_ALIAS, {}, blocking=True, return_response=True
        )


async def test_entities_are_attached_to_one_domum_device(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    registry = er.async_get(hass)
    devices = {e.device_id for e in er.async_entries_for_config_entry(registry, entry.entry_id)}
    assert len(devices) == 1
