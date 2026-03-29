from __future__ import annotations

import asyncio
import json

from app.schemas.pipeline import ProductData
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.rag_service import RagService
from tests.conftest import FakeEmbeddingsClient, FakeLLMClient


def test_rag_coherence_filter_rejects_semantically_wrong_substitute(settings) -> None:
    base_barcode = "1234567890123"
    better_spread = {
        "status": 1,
        "product": {
            "code": "9999999999991",
            "product_name": "Crema Nocciola Bio",
            "brands": "Green Brand",
            "ingredients_text": "hazelnut, cocoa, sugar",
            "packaging": "glass",
            "categories_tags": ["breakfasts"],
            "quantity": "300 g",
            "ecoscore_score": 72,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.1}},
        },
    }
    wrong_tomato = {
        "status": 1,
        "product": {
            "code": "9999999999992",
            "product_name": "Passata di Pomodoro",
            "brands": "Red Brand",
            "ingredients_text": "tomato puree",
            "packaging": "glass",
            "categories_tags": ["breakfasts"],
            "quantity": "300 g",
            "ecoscore_score": 88,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.8}},
        },
    }
    (settings.off_data_dir / f"{base_barcode}.json").write_text(
        json.dumps(
            {
                "status": 1,
                "product": {
                    "code": base_barcode,
                    "product_name": "Nutella",
                    "brands": "Ferrero",
                    "ingredients_text": "hazelnut, cocoa, sugar, palm oil",
                    "packaging": "glass",
                    "categories_tags": ["breakfasts"],
                    "quantity": "300 g",
                    "ecoscore_score": 55,
                    "ecoscore_grade": "c",
                    "ecoscore_data": {"agribalyse": {"co2_total": 1.6}},
                },
            }
        ),
        encoding="utf-8",
    )
    (settings.off_data_dir / "9999999999991.json").write_text(json.dumps(better_spread), encoding="utf-8")
    (settings.off_data_dir / "9999999999992.json").write_text(json.dumps(wrong_tomato), encoding="utf-8")

    off_client = OpenFoodFactsClient(settings)

    async def fake_search_similar_products(product: ProductData, *, locale=None, limit=None) -> list[dict]:
        del product, locale, limit
        return []

    off_client.search_similar_products = fake_search_similar_products
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings), off_client)

    suggestions, _trace = asyncio.run(
        rag_service.suggest_with_trace(
            ProductData(
                barcode=base_barcode,
                product_name="Nutella",
                brand="Ferrero",
                ingredients_text="hazelnut, cocoa, sugar, palm oil",
                categories_tags=["breakfasts"],
                quantity="300 g",
                ecoscore_score=55,
                co2e_kg_per_kg=1.6,
            ),
            user_query="alternativa piu sostenibile",
        )
    )

    assert suggestions
    assert all(item.candidate_product_name != "Passata di Pomodoro" for item in suggestions)


def test_rag_prefers_candidates_with_characteristic_ingredients_within_same_category(settings) -> None:
    base_barcode = "5555555555555"
    better_spread = {
        "status": 1,
        "product": {
            "code": "9999999999911",
            "product_name": "Crema Nocciole Bio",
            "brands": "Green Brand",
            "ingredients_text": "hazelnut, cocoa, sugar",
            "packaging": "glass",
            "categories_tags": ["spreads"],
            "quantity": "300 g",
            "ecoscore_score": 72,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.0}},
        },
    }
    wrong_spread = {
        "status": 1,
        "product": {
            "code": "9999999999912",
            "product_name": "Peanut Butter Bio",
            "brands": "Nut Brand",
            "ingredients_text": "peanut, salt",
            "packaging": "glass",
            "categories_tags": ["spreads"],
            "quantity": "300 g",
            "ecoscore_score": 90,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.7}},
        },
    }
    (settings.off_data_dir / f"{base_barcode}.json").write_text(
        json.dumps(
            {
                "status": 1,
                "product": {
                    "code": base_barcode,
                    "product_name": "Crema Nocciole",
                    "brands": "Base Brand",
                    "ingredients_text": "hazelnut, cocoa, sugar, palm oil",
                    "packaging": "glass",
                    "categories_tags": ["spreads", "breakfasts"],
                    "quantity": "300 g",
                    "ecoscore_score": 55,
                    "ecoscore_grade": "c",
                    "ecoscore_data": {"agribalyse": {"co2_total": 1.6}},
                },
            }
        ),
        encoding="utf-8",
    )
    (settings.off_data_dir / "9999999999911.json").write_text(json.dumps(better_spread), encoding="utf-8")
    (settings.off_data_dir / "9999999999912.json").write_text(json.dumps(wrong_spread), encoding="utf-8")

    off_client = OpenFoodFactsClient(settings)

    async def fake_search_similar_products(product: ProductData, *, locale=None, limit=None) -> list[dict]:
        del product, locale, limit
        return []

    off_client.search_similar_products = fake_search_similar_products
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings), off_client)

    suggestions, _trace = asyncio.run(
        rag_service.suggest_with_trace(
            ProductData(
                barcode=base_barcode,
                product_name="Crema Nocciole",
                brand="Base Brand",
                ingredients_text="hazelnut, cocoa, sugar, palm oil",
                categories_tags=["spreads", "breakfasts"],
                quantity="300 g",
                ecoscore_score=55,
                co2e_kg_per_kg=1.6,
                eco_ingredient_signals=[
                    {"id": "cocoa", "present": True},
                    {"id": "palm_oil", "present": True},
                ],
            ),
            user_query="alternativa piu sostenibile",
        )
    )

    assert suggestions
    assert suggestions[0].candidate_product_name == "Crema Nocciole Bio"
    assert all(item.candidate_product_name != "Peanut Butter Bio" for item in suggestions)
