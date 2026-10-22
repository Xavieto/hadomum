"""Coordinateur : un appel à ``/api/integration/state`` par cycle."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import DomumAuthError, DomumClient, DomumError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type DomumConfigEntry = ConfigEntry[DomumCoordinator]


class DomumCoordinator(DataUpdateCoordinator[dict]):
    """État de Domum permis par le jeton (sauvegardes, bastion, alias…)."""

    config_entry: DomumConfigEntry

    def __init__(self, hass: HomeAssistant, entry: DomumConfigEntry, client: DomumClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.state()
        except DomumAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except DomumError as exc:
            raise UpdateFailed(str(exc)) from exc

    def can(self, domain: str, level: str = "read") -> bool:
        granted = (self.data or {}).get("scopes", {}).get(domain)
        return granted == "write" or (granted == "read" and level == "read")

    def items(self, key: str) -> dict[str, dict]:
        """Éléments d'une liste de l'état (sauvegardes, alias…), par identifiant."""
        return {item["id"]: item for item in (self.data or {}).get(key, [])}
