from __future__ import annotations

import asyncio
import json

from app.schemas.pipeline import ProductData


def test_rag_query_returns_empty_safe_response_when_index_missing(settings) -> None:
    from tests.conftest import FakeEmbeddingsClient, FakeLLMClient
    from app.services.rag_service import RagService

    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings))
    result = asyncio.run(rag_service.suggest(ProductData(product_name="X"), user_query="alternative"))
    assert result == []


def test_rag_service_returns_suggestions(settings, sample_off_payload) -> None:
    from tests.conftest import FakeEmbeddingsClient, FakeLLMClient
    from app.services.rag_service import RagService

    barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")

    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings))
    asyncio.run(rag_service.reindex_from_local_subset())
    result = asyncio.run(rag_service.suggest(ProductData(product_name="Biscotti", brand="Test"), user_query="meno zucchero"))

    assert result
    assert result[0].sources == [barcode]
