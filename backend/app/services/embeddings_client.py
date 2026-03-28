from __future__ import annotations

from typing import Any, Dict, List

import httpx

from app.core.settings import Settings


class EmbeddingsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = settings.build_auth_headers()
        self.base_url = settings.normalize_base_url(settings.embedding_base_url)

    async def healthcheck(self) -> Dict[str, Any]:
        try:
            await self.embed_text("healthcheck")
            return {"status": "ok", "model": self.settings.embedding_model}
        except Exception as exc:
            return {"status": "error", "model": self.settings.embedding_model, "detail": str(exc)}

    async def embed_text(self, text: str) -> List[float]:
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds,
            headers=self.headers,
        ) as client:
            response = await client.post(
                "{}/v1/embeddings".format(self.base_url),
                json={"model": self.settings.embedding_model, "input": texts},
            )
            response.raise_for_status()
            data: Dict[str, Any] = response.json()

        if "data" in data:
            return [item.get("embedding", []) for item in data["data"]]
        if "embeddings" in data:
            return data["embeddings"]
        if "embedding" in data:
            return [data["embedding"]]
        return [[] for _ in texts]
