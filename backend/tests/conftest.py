from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import app
from app.schemas.pipeline import ProductData
from app.services.embeddings_client import EmbeddingsClient
from app.services.explainer import ScoreExplainer
from app.services.extractor import ProductExtractor
from app.services.llm_client import LLMClient
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.rag_service import RagService
from app.services.scoring_engine import ScoringEngine


class FakeLLMClient(LLMClient):
    async def extract_from_image(self, image_path: str, prompt: str, user_notes: Optional[str] = None) -> dict:
        return {
            "product_name": "Crackers Integrali",
            "brand": "Local Test",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "nutriments": {"sugars_100g": 2.0, "salt_100g": 0.9, "fiber_100g": 5.0},
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["snacks"],
            "quantity": "200g",
            "confidence": 0.72,
        }

    async def generate_explanation(self, prompt: str, product_payload: dict, score_payload: dict, mode: str = "no_think") -> dict:
        if mode == "think":
            return {
                "facts": ["Sugar is low."],
                "assumptions": ["Origin may be local."],
                "advice_candidates": ["Pair with fresh vegetables."],
                "draft_summary": "Draft rationale.",
            }
        return {
            "explanation_short": "Prodotto con profilo discreto e alcuni segnali positivi.",
            "why_bullets": [
                "Fact: zuccheri contenuti.",
                "Assumption: alcune informazioni potrebbero essere incomplete.",
                "Advice: abbinalo a cibi freschi e poco processati.",
            ],
        }

    async def generate_rag_answer(
        self,
        prompt: str,
        product_payload: dict,
        user_query: str,
        retrieved_docs: list[dict],
    ) -> dict:
        if not retrieved_docs:
            return {"suggestions": []}
        return {
            "suggestions": [
                {
                    "title": "Alternativa meno salata",
                    "suggestion": "Valuta un prodotto simile con meno sale.",
                    "rationale": "Riduce il carico di sodio complessivo.",
                    "sources": [retrieved_docs[0]["id"]],
                }
            ]
        }


class FakeEmbeddingsClient(EmbeddingsClient):
    async def embed_text(self, text: str) -> list[float]:
        return [float(len(text)), 1.0, 0.5]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text)), 1.0, 0.5] for text in texts]


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    off_dir = tmp_path / "off_subset"
    off_dir.mkdir(parents=True, exist_ok=True)
    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir(parents=True, exist_ok=True)
    images_dir = tmp_path / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        backend_dir=Path(__file__).resolve().parents[1],
        off_data_dir=off_dir,
        chroma_path=chroma_dir,
        allowed_image_roots_raw=str(images_dir),
        enable_pipeline_debug_last=True,
    )


@pytest.fixture
def orchestrator(settings: Settings) -> PipelineOrchestrator:
    normalizer = ProductNormalizer()
    llm_client = FakeLLMClient(settings)
    extractor = ProductExtractor(settings, llm_client, normalizer)
    off_client = OpenFoodFactsClient(settings)
    scoring_engine = ScoringEngine()
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), llm_client)
    explainer = ScoreExplainer(settings, llm_client)
    return PipelineOrchestrator(extractor, normalizer, off_client, scoring_engine, rag_service, explainer)


@pytest.fixture
def sample_off_payload() -> dict:
    return {
        "status": 1,
        "product": {
            "code": "1234567890123",
            "product_name": "Biscotti Avena",
            "brands": "Test Brand",
            "ingredients_text": "oat flour, sugar, sunflower oil",
            "nutriments": {"sugars_100g": 12.0, "salt_100g": 0.3},
            "packaging": "plastic",
            "origins": "Italy",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "250 g",
        },
    }


@pytest.fixture
def sample_image_path(settings: Settings) -> Path:
    image_root = settings.allowed_image_roots()[0]
    image_path = image_root / "product.jpg"
    image_path.write_bytes(b"fake-image")
    return image_path


@pytest.fixture
def api_client(monkeypatch, orchestrator, settings: Settings) -> TestClient:
    from app import main as app_main
    from app.pipeline import build_orchestrator

    build_orchestrator.cache_clear()
    monkeypatch.setattr(app_main, "settings", settings)
    monkeypatch.setattr(app_main, "build_orchestrator", lambda: orchestrator)
    with TestClient(app) as client:
        yield client
