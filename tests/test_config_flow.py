"""Assistant de configuration et réauthentification."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResultType

from custom_components.domum.const import DOMAIN

from .conftest import API, URL, state

INPUT = {CONF_URL: f"{URL}/", CONF_API_TOKEN: "jeton", CONF_VERIFY_SSL: True}


async def test_a_valid_token_creates_the_entry(hass, aioclient_mock):
    aioclient_mock.get(f"{API}/info", json={"version": "2.8.0", "name": "Maison", "scopes": {}})
    aioclient_mock.get(f"{API}/state", json=state())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Domum (Maison)"
    assert result["data"][CONF_URL] == URL
    # Le même jeton du même Domum n'est configuré qu'une fois.
    again = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    again = await hass.config_entries.flow.async_configure(again["flow_id"], INPUT)
    assert again["type"] is FlowResultType.ABORT and again["reason"] == "already_configured"


async def test_errors_are_shown_on_the_form(hass, aioclient_mock):
    aioclient_mock.get(f"{API}/info", status=401, json={"detail": "Jeton d'intégration invalide"})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/info", status=502, text="Bad gateway")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_a_refused_token_asks_for_a_new_one(hass, aioclient_mock, entry):
    aioclient_mock.get(f"{API}/state", status=401, json={"detail": "Jeton d'intégration invalide"})
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
    flow_id = flows[0]["flow_id"]
    aioclient_mock.get(f"{API}/info", status=401, json={})
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_TOKEN: "mauvais"})
    assert result["errors"] == {"base": "invalid_auth"}
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{API}/info", json={"version": "2.8.0", "name": "Maison", "scopes": {}})
    aioclient_mock.get(f"{API}/state", json=state())
    result = await hass.config_entries.flow.async_configure(flow_id, {CONF_API_TOKEN: "nouveau"})
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reauth_successful"
    assert entry.data[CONF_API_TOKEN] == "nouveau"
