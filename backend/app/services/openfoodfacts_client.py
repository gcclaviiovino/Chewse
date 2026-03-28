from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.core.settings import Settings


class OpenFoodFactsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def healthcheck(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "local_dataset": str(self.settings.off_data_dir),
            "remote_base_url": self.settings.openfoodfacts_base_url,
        }

    async def fetch_product(self, barcode: str) -> Optional[Dict[str, Any]]:
        local_payload = self._read_local_payload(barcode)
        if local_payload is not None:
            return local_payload

        async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
            response = await client.get(
                "{}/product/{}.json".format(self.settings.openfoodfacts_base_url.rstrip("/"), barcode)
            )
            response.raise_for_status()
            payload = response.json()
        return payload if payload.get("status") == 1 or payload.get("product") else None

    def _read_local_payload(self, barcode: str) -> Optional[Dict[str, Any]]:
        file_path = Path(self.settings.off_data_dir) / "{}.json".format(barcode)
        if not file_path.exists():
            return None
        with file_path.open("r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
