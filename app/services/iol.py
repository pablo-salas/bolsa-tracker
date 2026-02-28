"""InvertirOnline API client with auto token refresh."""

import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import IOL_BASE_URL, IOL_USERNAME, IOL_PASSWORD


@dataclass
class IolClient:
    base_url: str = IOL_BASE_URL
    username: str = IOL_USERNAME
    password: str = IOL_PASSWORD
    _access_token: str = field(default="", repr=False)
    _refresh_token: str = field(default="", repr=False)
    _expires_at: float = field(default=0.0, repr=False)

    # ── auth ──────────────────────────────────────────────

    async def _authenticate(self) -> None:
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self.base_url}/token",
                data={
                    "username": self.username,
                    "password": self.password,
                    "grant_type": "password",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            r.raise_for_status()
            data = r.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", "")
        self._expires_at = time.time() + data.get("expires_in", 900) - 60

    async def _refresh(self) -> None:
        if not self._refresh_token:
            return await self._authenticate()
        async with httpx.AsyncClient() as c:
            r = await c.post(
                f"{self.base_url}/token",
                data={
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if r.status_code != 200:
                return await self._authenticate()
            data = r.json()
        self._access_token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._expires_at = time.time() + data.get("expires_in", 900) - 60

    async def _ensure_auth(self) -> str:
        if not self._access_token or time.time() >= self._expires_at:
            if self._refresh_token:
                await self._refresh()
            else:
                await self._authenticate()
        return self._access_token

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        token = await self._ensure_auth()
        async with httpx.AsyncClient() as c:
            r = await c.request(
                method,
                f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                **kwargs,
            )
            r.raise_for_status()
            if r.status_code == 204:
                return None
            return r.json()

    # ── account ───────────────────────────────────────────

    async def get_account_status(self) -> dict:
        return await self._request("GET", "/api/v2/estadocuenta")

    async def get_portfolio(self, pais: str = "argentina") -> dict:
        return await self._request("GET", f"/api/v2/portafolio/{pais}")

    # ── market data ───────────────────────────────────────

    async def get_quote(self, mercado: str, simbolo: str) -> dict:
        return await self._request(
            "GET", f"/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion"
        )

    async def get_detailed_quote(self, mercado: str, simbolo: str) -> dict:
        return await self._request(
            "GET", f"/api/v2/{mercado}/Titulos/{simbolo}/CotizacionDetalle"
        )

    async def get_historical(
        self, mercado: str, simbolo: str, desde: str, hasta: str, ajustada: bool = True
    ) -> Any:
        adj = "ajustada" if ajustada else "sinAjustar"
        return await self._request(
            "GET",
            f"/api/v2/{mercado}/Titulos/{simbolo}/Cotizacion/seriehistorica/{desde}/{hasta}/{adj}",
        )

    # ── trading ───────────────────────────────────────────

    async def buy(self, mercado: str, simbolo: str, cantidad: int, precio: float, plazo: str = "t2", validez: str = "") -> dict:
        return await self._request(
            "POST",
            "/api/v2/operar/Comprar",
            json={
                "mercado": mercado,
                "simbolo": simbolo,
                "cantidad": cantidad,
                "precio": precio,
                "plazo": plazo,
                "validez": validez,
            },
        )

    async def sell(self, mercado: str, simbolo: str, cantidad: int, precio: float, plazo: str = "t2", validez: str = "") -> dict:
        return await self._request(
            "POST",
            "/api/v2/operar/Vender",
            json={
                "mercado": mercado,
                "simbolo": simbolo,
                "cantidad": cantidad,
                "precio": precio,
                "plazo": plazo,
                "validez": validez,
            },
        )

    # ── operations ────────────────────────────────────────

    async def get_operations(self, estado: str | None = None) -> list[dict]:
        params = {}
        if estado:
            params["estado"] = estado
        return await self._request("GET", "/api/v2/operaciones", params=params)

    async def cancel_operation(self, numero: int) -> None:
        return await self._request("DELETE", f"/api/v2/operaciones/{numero}")

    # ── MEP ───────────────────────────────────────────────

    async def get_mep_quote(self) -> dict:
        return await self._request("POST", "/api/v2/Cotizaciones/MEP")


iol = IolClient()
