from __future__ import annotations

from app.schemas.pipeline import ProductData
from app.services.category_normalizer import canonicalize_categories, canonicalize_category, category_search_aliases
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


def test_preferences_memory_uses_canonical_category_keys(tmp_path) -> None:
    service = PreferencesMemoryService(tmp_path)

    service.upsert_category_preferences("alice", "en:biscuit", "- no dairy")

    assert service.load_category_preferences("alice", "en:biscuits") == "- no dairy"


def test_rag_category_similarity_uses_canonical_categories(settings) -> None:
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), FakeLLMClient(settings), OpenFoodFactsClient(settings))

    similarity = rag_service._category_similarity(["en:biscuit"], ["en:biscuits"])

    assert similarity == 1.0
