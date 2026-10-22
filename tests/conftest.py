"""Fixtures : intégrations personnalisées autorisées, état type renvoyé par Domum."""

import pytest
from homeassistant.const import CONF_API_TOKEN, CONF_URL, CONF_VERIFY_SSL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.domum.const import DOMAIN

URL = "https://tools.example"
API = f"{URL}/api/integration"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def state(**changes) -> dict:
    data = {
        "version": "2.8.0",
        "at": "2026-10-22T10:00:00+00:00",
        "name": "Maison",
        "scopes": {"backup": "write", "bastion": "write", "alias": "write"},
        "backups": [
            {
                "id": "b1",
                "name": "Critique",
                "flux": "critical",
                "type": "archive",
                "enabled": True,
                "state": "success",
                "last_run_at": "2026-10-22T00:48:07+00:00",
                "last_status": "success",
                "last_size": 734000000,
                "last_duration": 187,
                "last_success_at": "2026-10-22T00:48:07+00:00",
                "next_run_at": "2026-10-22T22:45:00+00:00",
            },
            {
                "id": "b2",
                "name": "Nextcloud",
                "flux": "nextcloud",
                "type": "sync",
                "enabled": True,
                "state": "failed",
                "last_run_at": "2026-10-21T23:31:00+00:00",
                "last_status": "failed",
                "last_size": None,
                "last_duration": 4,
                "last_success_at": None,
                "next_run_at": None,
            },
        ],
        "bastion": {"alive": True, "active_sessions": 2, "sessions_day": 14},
        "aliases": [
            {
                "id": "a1",
                "address": "achats@roques.bzh",
                "destination": "moi@exemple.fr",
                "description": None,
                "active": True,
            }
        ],
    }
    data.update(changes)
    return data


@pytest.fixture
def entry(hass):
    config = MockConfigEntry(
        domain=DOMAIN,
        title="Domum (Maison)",
        unique_id=f"{URL}|Maison",
        data={CONF_URL: URL, CONF_API_TOKEN: "jeton", CONF_VERIFY_SSL: True},
    )
    config.add_to_hass(hass)
    return config
