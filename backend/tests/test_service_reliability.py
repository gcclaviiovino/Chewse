from __future__ import annotations

import asyncio

import httpx

from app.core.errors import AppError
from app.schemas.pipeline import ProductData
from app.services.embeddings_client import EmbeddingsClient
from app.services.llm_client import LLMClient
from app.services.rag_service import RagService


def test_llm_client_retries_after_timeout(monkeypatch, settings) -> None:
    client = LLMClient(settings)
    attempts = {"count": 0}

    async def fake_request(self, method, url, json=None):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise httpx.ReadTimeout("timeout")
        return httpx.Response(200, request=httpx.Request(method, url), json={"choices": [{"message": {"content": "{\"ok\": true}"}}]})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    result = asyncio.run(client.generate_explanation("x", {"foo": "bar"}, {"score": 1}))

    assert result["ok"] is True
    assert attempts["count"] == 2


def test_embeddings_client_raises_after_retries(monkeypatch, settings) -> None:
    client = EmbeddingsClient(settings)
    attempts = {"count": 0}

    async def fake_post(self, url, json=None):
        attempts["count"] += 1
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    try:
        asyncio.run(client.embed_text("hello"))
    except AppError as exc:
        assert exc.error_code == "embeddings_request_failed"
    else:
        raise AssertionError("Expected AppError to be raised.")

    assert attempts["count"] == settings.embedding_retry_count + 1


def test_rag_service_degrades_when_embeddings_are_offline(settings) -> None:
    from tests.conftest import FakeLLMClient

    class OfflineEmbeddingsClient(EmbeddingsClient):
        async def embed_text(self, text: str) -> list[float]:
            raise AppError("embeddings_request_failed", "offline", status_code=502)

    rag_service = RagService(settings, OfflineEmbeddingsClient(settings), FakeLLMClient(settings))
    collection = rag_service._get_collection()
    collection.upsert(ids=["1"], embeddings=[[1.0, 1.0]], metadatas=[{"barcode": "1"}], documents=["doc"])

    suggestions, trace = asyncio.run(rag_service.suggest_with_trace(ProductData(product_name="X"), user_query="alternative"))

    assert suggestions == []
    assert trace["warning"] == "embeddings_unavailable"
