from __future__ import annotations

from app.product import merge_product_data
from app.schemas.pipeline import ProductData
from app.services.category_normalizer import (
    canonicalize_categories,
    canonicalize_category,
    category_search_aliases,
    prioritize_categories,
    select_primary_category,
)
from app.services.preferences_memory import PreferencesMemoryService
from app.services.rag_service import RagService
from tests.conftest import FakeEmbeddingsClient, FakeLLMClient
from app.services.openfoodfacts_client import OpenFoodFactsClient


def test_category_normalizer_unifies_singular_and_plural() -> None:
    assert canonicalize_category("en:biscuit") == "biscuits"
    assert canonicalize_category("en:biscuits") == "biscuits"
    assert canonicalize_category("cookies") == "biscuits"
    assert canonicalize_categories(["en:snack", "snacks", "en:crackers"]) == ["snacks"]


def test_category_search_aliases_expand_family() -> None:
    aliases = category_search_aliases(["en:biscuit"])
    assert "biscuits" in aliases
    assert "cookies" in aliases


def test_primary_category_prefers_specific_spreads_over_breakfasts() -> None:
    assert select_primary_category(["en:breakfasts", "en:spreads"]) == "spreads"
    assert prioritize_categories(["en:breakfasts", "en:spreads"])[0] == "spreads"


def test_preferences_memory_uses_canonical_category_keys(tmp_path) -> None:
    service = PreferencesMemoryService(tmp_path)

    service.upsert_category_preferences("alice", "en:biscuit", "- no dairy")

    assert service.load_category_preferences("alice", "en:biscuits") == "- no dairy"


def test_rag_category_similarity_uses_canonical_categories(settings) -> None:
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings), OpenFoodFactsClient(settings))

    similarity = rag_service._category_similarity(["en:biscuit"], ["en:biscuits"])

    assert similarity == 1.0


def test_merge_product_data_preserves_primary_category_order() -> None:
    primary = ProductData(product_name="Crema", categories_tags=["en:spreads", "en:breakfasts"], source="image_llm", confidence=0.4)
    secondary = ProductData(product_name="Crema", categories_tags=["en:breakfasts", "en:sweet-spreads"], source="openfoodfacts", confidence=0.9)

    merged = merge_product_data(primary, secondary)

    assert merged.categories_tags == ["en:spreads", "en:breakfasts", "en:sweet-spreads"]
