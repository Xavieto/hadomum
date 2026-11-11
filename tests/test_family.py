"""Module Famille : entités par enfant, actions, options et services."""

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from custom_components.domum.const import DOMAIN

from .conftest import API, state


def child(**changes) -> dict:
    data = {
        "id": "c1",
        "name": "Alice",
        "state": "open",
        "online": True,
        "paused": False,
        "used_minutes": 45,
        "budget_minutes": 120,
        "remaining_minutes": 75,
        "bonus_minutes": 15,
        "punished": False,
        "punish_until": None,
        "punish_mode": "profile",
        "vacation": False,
    }
    data.update(changes)
    return data


def family(*children, scope="write", **changes):
    return state(scopes={"family": scope}, family=list(children) or [child()], **changes)


async def _setup(hass, aioclient_mock, entry, data=None):
    aioclient_mock.get(f"{API}/state", json=data or family())
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _posts(aioclient_mock):
    return [
        (str(url), data) for method, url, data, *_ in aioclient_mock.mock_calls if method == "POST"
    ]


async def test_each_child_gets_a_device_and_entities(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    assert hass.states.get("sensor.famille_alice_remaining_time").state == "75"
    assert (
        hass.states.get("sensor.famille_alice_remaining_time").attributes["budget_minutes"] == 120
    )
    assert hass.states.get("sensor.famille_alice_time_used").state == "45"
    assert hass.states.get("sensor.famille_alice_state").state == "open"
    assert hass.states.get("binary_sensor.famille_alice_online").state == "on"
    assert hass.states.get("switch.famille_alice_internet").state == "on"
    assert hass.states.get("switch.famille_alice_punishment").state == "off"
    assert hass.states.get("switch.famille_alice_vacation_mode").state == "off"
    for name in ("15_minutes", "30_minutes", "1_hour"):
        assert hass.states.get(f"button.famille_alice_add_{name}") is not None
    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, f"{entry.entry_id}_family_c1")}
    )
    assert device.name == "Famille - Alice"


async def test_states_without_budget_or_unknown(hass, aioclient_mock, entry):
    data = family(child(budget_minutes=None, remaining_minutes=None, state="weird", online=False))
    await _setup(hass, aioclient_mock, entry, data)
    assert hass.states.get("sensor.famille_alice_remaining_time").state == "unknown"
    assert hass.states.get("sensor.famille_alice_state").state == "unknown"
    assert hass.states.get("binary_sensor.famille_alice_online").state == "off"


async def test_paused_punished_and_vacation_children(hass, aioclient_mock, entry):
    data = family(
        child(
            state="punished",
            online=False,
            paused=True,
            punished=True,
            punish_until="2026-10-22T12:00:00+00:00",
            punish_mode="cut",
            vacation=True,
        )
    )
    await _setup(hass, aioclient_mock, entry, data)
    assert hass.states.get("switch.famille_alice_internet").state == "off"
    punish = hass.states.get("switch.famille_alice_punishment")
    assert punish.state == "on"
    assert punish.attributes["punish_until"] == "2026-10-22T12:00:00+00:00"
    assert punish.attributes["punish_mode"] == "cut"
    assert hass.states.get("switch.famille_alice_vacation_mode").state == "on"
    assert hass.states.get("sensor.famille_alice_state").state == "punished"


async def test_read_only_token_has_sensors_only(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, family(scope="read"))
    assert hass.states.get("sensor.famille_alice_remaining_time") is not None
    assert hass.states.get("binary_sensor.famille_alice_online") is not None
    assert hass.states.get("switch.famille_alice_internet") is None
    assert hass.states.get("button.famille_alice_add_15_minutes") is None


async def test_no_family_scope_no_entities(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry, state())
    assert hass.states.get("sensor.famille_alice_state") is None
    assert hass.states.get("switch.famille_alice_internet") is None


async def test_a_new_child_appears_and_a_removed_one_becomes_unavailable(
    hass, aioclient_mock, entry
):
    await _setup(hass, aioclient_mock, entry)
    entry.runtime_data.async_set_updated_data(family(child(id="c2", name="Bruno")))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.famille_bruno_state").state == "open"
    assert hass.states.get("sensor.famille_alice_state").state == "unavailable"


async def test_switches_and_buttons_call_domum(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    for suffix in ("pause", "bonus", "punish", "punish/lift", "vacation"):
        aioclient_mock.post(f"{API}/family/c1/{suffix}", json={})

    async def call(domain, service, entity):
        await hass.services.async_call(domain, service, {"entity_id": entity}, blocking=True)

    await call("switch", "turn_off", "switch.famille_alice_internet")
    await call("switch", "turn_on", "switch.famille_alice_internet")
    await call("switch", "turn_on", "switch.famille_alice_punishment")
    await call("switch", "turn_off", "switch.famille_alice_punishment")
    await call("switch", "turn_on", "switch.famille_alice_vacation_mode")
    await call("switch", "turn_off", "switch.famille_alice_vacation_mode")
    for name in ("15_minutes", "30_minutes", "1_hour"):
        await call("button", "press", f"button.famille_alice_add_{name}")
    assert _posts(aioclient_mock) == [
        (f"{API}/family/c1/pause", {"paused": True}),
        (f"{API}/family/c1/pause", {"paused": False}),
        (f"{API}/family/c1/punish", {"mode": "profile", "minutes": 60}),
        (f"{API}/family/c1/punish/lift", None),
        (f"{API}/family/c1/vacation", {"enabled": True}),
        (f"{API}/family/c1/vacation", {"enabled": False}),
        (f"{API}/family/c1/bonus", {"minutes": 15}),
        (f"{API}/family/c1/bonus", {"minutes": 30}),
        (f"{API}/family/c1/bonus", {"minutes": 60}),
    ]


async def test_the_punishment_switch_uses_the_options(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"punish_minutes": 90, "punish_mode": "cut"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {"punish_minutes": 90, "punish_mode": "cut"}
    # le formulaire suivant propose les valeurs enregistrées
    again = await hass.config_entries.options.async_init(entry.entry_id)
    assert again["type"] is FlowResultType.FORM
    aioclient_mock.post(f"{API}/family/c1/punish", json={})
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": "switch.famille_alice_punishment"}, blocking=True
    )
    assert _posts(aioclient_mock)[-1] == (f"{API}/family/c1/punish", {"mode": "cut", "minutes": 90})


async def test_family_errors_are_reported_to_the_user(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    for suffix in ("pause", "bonus"):
        aioclient_mock.post(f"{API}/family/c1/{suffix}", status=409, json={"detail": "Refusé"})
    with pytest.raises(HomeAssistantError, match="Refusé"):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.famille_alice_internet"},
            blocking=True,
        )
    with pytest.raises(HomeAssistantError, match="Refusé"):
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": "button.famille_alice_add_15_minutes"},
            blocking=True,
        )


async def test_services_add_time_punish_and_lift(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    for suffix in ("bonus", "punish", "punish/lift"):
        aioclient_mock.post(f"{API}/family/c1/{suffix}", json={})
    await hass.services.async_call(
        DOMAIN, "add_time", {"child": "alice", "minutes": 20}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "punish", {"child": "c1", "minutes": 30, "mode": "cut"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, "punish", {"child": "Alice"}, blocking=True)
    await hass.services.async_call(DOMAIN, "lift_punishment", {"child": "Alice"}, blocking=True)
    assert _posts(aioclient_mock) == [
        (f"{API}/family/c1/bonus", {"minutes": 20}),
        (f"{API}/family/c1/punish", {"mode": "cut", "minutes": 30}),
        (f"{API}/family/c1/punish", {"mode": "profile", "minutes": 60}),
        (f"{API}/family/c1/punish/lift", None),
    ]


async def test_service_errors(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    with pytest.raises(ServiceValidationError, match="Inconnu"):
        await hass.services.async_call(
            DOMAIN, "lift_punishment", {"child": "Inconnu"}, blocking=True
        )
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "lift_punishment", {"child": "Alice", "config_entry_id": "autre"}, blocking=True
        )
    aioclient_mock.post(f"{API}/family/c1/bonus", status=403, json={"detail": "Interdit"})
    with pytest.raises(HomeAssistantError, match="Interdit"):
        await hass.services.async_call(
            DOMAIN, "add_time", {"child": "Alice", "minutes": 5}, blocking=True
        )
    entry.runtime_data.async_set_updated_data(family(scope="read"))
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "add_time", {"child": "Alice", "minutes": 5}, blocking=True
        )


async def test_family_event_service(hass, aioclient_mock, entry):
    await _setup(hass, aioclient_mock, entry)
    aioclient_mock.post(f"{API}/family/events/alarm_night", json={"persons": 2})
    response = await hass.services.async_call(
        DOMAIN, "family_event", {"event": "alarm_night"}, blocking=True, return_response=True
    )
    assert response == {"persons": 2}
    aioclient_mock.post(f"{API}/family/events/inconnu", status=404, json={"detail": "Aucun"})
    with pytest.raises(HomeAssistantError, match="Aucun"):
        await hass.services.async_call(
            DOMAIN, "family_event", {"event": "inconnu"}, blocking=True, return_response=True
        )
    assert entry.state is ConfigEntryState.LOADED
