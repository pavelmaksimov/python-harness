"""Invoices provider client: raw async HTTP with a hand-rolled retry loop."""

import asyncio

import httpx


class InvoicesAdapter:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(base_url="https://invoices.example.com", timeout=10)

    async def get_invoice(self, invoice_id: str) -> dict:
        delay = 1.0
        for attempt in range(4):
            try:
                response = await self._http.get(f"/invoices/{invoice_id}")
            except httpx.TransportError:
                if attempt == 3:
                    raise
                await asyncio.sleep(delay)
                delay *= 2
                continue
            if response.status_code >= 500 and attempt < 3:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError("unreachable")

    async def capture(self, invoice_id: str, amount_cents: int) -> dict:
        response = await self._http.post(
            f"/invoices/{invoice_id}/capture",
            json={"amount_cents": amount_cents},
        )
        response.raise_for_status()
        return response.json()
