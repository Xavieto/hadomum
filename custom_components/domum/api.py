"""Client de l'API d'intégration de Domum (``/api/integration``)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import aiohttp

TIMEOUT = aiohttp.ClientTimeout(total=30)


class DomumError(Exception):
    """Erreur renvoyée par Domum ou réseau indisponible."""


class DomumAuthError(DomumError):
    """Jeton refusé (révoqué ou invalide)."""


class DomumClient:
    """Appels authentifiés par le jeton d'intégration."""

    def __init__(self, session: aiohttp.ClientSession, url: str, token: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._token = token

    @property
    def url(self) -> str:
        return self._url

    async def _request(self, method: str, path: str, payload: dict | None = None) -> Any:
        try:
            async with self._session.request(
                method,
                f"{self._url}/api/integration{path}",
                headers={"Authorization": f"Bearer {self._token}"},
                json=payload,
                timeout=TIMEOUT,
            ) as response:
                try:
                    data = await response.json(content_type=None)
                except ValueError:
                    data = None
                detail = data.get("detail") if isinstance(data, dict) else None
                if response.status == 401:
                    raise DomumAuthError(detail or "Jeton refusé")
                if response.status >= 400:
                    raise DomumError(detail or f"Erreur HTTP {response.status}")
                return data
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise DomumError(f"Domum injoignable : {exc}") from exc

    async def info(self) -> dict:
        return await self._request("GET", "/info")

    async def state(self) -> dict:
        return await self._request("GET", "/state")

    async def run_backup(self, backup_id: str) -> dict:
        return await self._request("POST", f"/backups/{backup_id}/run")

    async def kill_sessions(self) -> dict:
        return await self._request("POST", "/bastion/kill-all")

    async def set_alias(self, alias_id: str, active: bool) -> dict:
        return await self._request("PATCH", f"/aliases/{alias_id}", {"active": active})

    async def server_action(self, server_id: str, kind: str) -> dict:
        return await self._request("POST", f"/servers/{server_id}/{kind}")

    async def calendar(self, start: str, end: str) -> list[dict]:
        return await self._request("GET", f"/calendar?start={quote(start)}&end={quote(end)}")

    async def generate_alias(self, destination: str | None, domain: str | None) -> dict:
        payload = {k: v for k, v in (("destination", destination), ("domain", domain)) if v}
        return await self._request("POST", "/aliases/generate", payload)
