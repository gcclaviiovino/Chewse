from __future__ import annotations

import asyncio
import json

from app.schemas.pipeline import ProductData
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.rag_service import RagService
from tests.conftest import FakeEmbeddingsClient, FakeLLMClient


def _build_rag_service(settings, remote_candidates=None) -> RagService:
    off_client = OpenFoodFactsClient(settings)

    async def fake_search_similar_products(product: ProductData, *, locale=None, limit=None) -> list[dict]:
        del product, locale, limit
        return list(remote_candidates or [])

    off_client.search_similar_products = fake_search_similar_products
    return RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings), off_client)


def test_rag_query_returns_empty_safe_response_when_index_missing(settings) -> None:
    rag_service = _build_rag_service(settings)
    result = asyncio.run(rag_service.suggest(ProductData(product_name="X"), user_query="alternative"))
    assert result == []


def test_rag_service_returns_better_similar_suggestion(settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    candidate_barcode = "9999999999991"
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    better_candidate = {
        "status": 1,
        "product": {
            "code": candidate_barcode,
            "product_name": "Biscotti Avena Integrali",
            "brands": "Green Brand",
            "ingredients_text": "oat flour, whole wheat flour, sunflower oil",
            "packaging": "paper",
            "origins": "Italy",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "240 g",
            "ecoscore_score": 78,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.1}},
        },
    }
    (settings.off_data_dir / "{}.json".format(candidate_barcode)).write_text(json.dumps(better_candidate), encoding="utf-8")

    rag_service = _build_rag_service(settings)
    asyncio.run(rag_service.reindex_from_local_subset())
    result, trace = asyncio.run(
        rag_service.suggest_with_trace(
            ProductData(
                barcode=base_barcode,
                product_name="Biscotti Avena",
                brand="Test Brand",
                ingredients_text="oat flour, sugar, sunflower oil",
                categories_tags=["breakfasts"],
                quantity="250 g",
                ecoscore_score=62,
                co2e_kg_per_kg=1.73,
            ),
            user_query="consigliami un'alternativa piu sostenibile",
        )
    )

    assert result
    assert result[0].sources == [candidate_barcode]
    assert result[0].candidate_barcode == candidate_barcode
    assert result[0].candidate_ecoscore_score == 78
    assert result[0].similarity_score is not None
    assert result[0].eco_improvement_score is not None
    assert trace["filtered_count"] >= 1


def test_rag_service_filters_candidates_that_are_too_different(settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    unrelated_candidate = {
        "status": 1,
        "product": {
            "code": "9999999999992",
            "product_name": "Salmone Affumicato",
            "brands": "Sea Brand",
            "ingredients_text": "salmon, salt",
            "packaging": "plastic tray",
            "categories_tags": ["fish-and-meat-and-eggs"],
            "quantity": "120 g",
            "ecoscore_score": 85,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 2.2}},
        },
    }
    (settings.off_data_dir / "9999999999992.json").write_text(json.dumps(unrelated_candidate), encoding="utf-8")

    rag_service = _build_rag_service(settings)
    suggestions, trace = asyncio.run(
        rag_service.suggest_with_trace(
            ProductData(
                barcode=base_barcode,
                product_name="Biscotti Avena",
                ingredients_text="oat flour, sugar, sunflower oil",
                categories_tags=["breakfasts"],
                quantity="250 g",
                ecoscore_score=62,
            ),
            user_query="alternativa",
        )
    )

    assert suggestions == []
    assert trace["warning"] == "no_similar_better_candidates"


def test_rag_service_deduplicates_near_identical_candidates(settings) -> None:
    candidate_one = {
        "status": 1,
        "product": {
            "code": "111",
            "product_name": "Crackers Integrali",
            "brands": "Brand A",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "categories_tags": ["snacks"],
            "quantity": "200 g",
            "ecoscore_score": 72,
            "ecoscore_grade": "a",
        },
    }
    candidate_two = {
        "status": 1,
        "product": {
            "code": "222",
            "product_name": "Crackers Integrali",
            "brands": "Brand A",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "categories_tags": ["snacks"],
            "quantity": "200 g",
            "ecoscore_score": 74,
            "ecoscore_grade": "a",
        },
    }
    (settings.off_data_dir / "111.json").write_text(json.dumps(candidate_one), encoding="utf-8")
    (settings.off_data_dir / "222.json").write_text(json.dumps(candidate_two), encoding="utf-8")

    rag_service = _build_rag_service(settings)
    suggestions, trace = asyncio.run(
        rag_service.suggest_with_trace(
            ProductData(
                barcode="000",
                product_name="Crackers Integrali",
                ingredients_text="whole wheat flour, olive oil, salt",
                categories_tags=["snacks"],
                quantity="200 g",
                ecoscore_score=60,
            ),
            user_query="alternativa",
        )
    )

    assert trace["retrieved_count"] == 1
    assert suggestions
