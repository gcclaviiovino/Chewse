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
from app.services.impact_translator import ImpactTranslator
from app.services.llm_client import LLMClient
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.preference_interpreter import PreferenceInterpreter
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

    async def extract_from_image_url(self, image_url: str, prompt: str, user_notes: Optional[str] = None) -> dict:
        return {
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "confidence": 0.61,
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
                    "title": "Alternativa piu sostenibile",
                    "suggestion": "Valuta un prodotto simile con impatto ambientale migliore.",
                    "rationale": "Confronto filtrato su similarita e miglioramento ambientale.",
                    "sources": [doc["id"]],
                }
                for doc in retrieved_docs[:3]
            ]
        }

    async def filter_candidate_coherence(
        self,
        prompt: str,
        product_payload: dict,
        retrieved_docs: list[dict],
    ) -> dict:
        base_name = str((product_payload or {}).get("product_name") or "").lower()
        accepted_sources: list[str] = []
        rejected_sources: list[dict] = []
        for doc in retrieved_docs:
            candidate_name = str((doc.get("metadata") or {}).get("product_name") or "").lower()
            source_id = str(doc.get("id") or "")
            if "nutella" in base_name or "crema" in base_name:
                if any(token in candidate_name for token in ("tomato", "pomodoro", "passata", "puree")):
                    rejected_sources.append({"source": source_id, "reason": "non e una sostituzione plausibile"})
                    continue
            accepted_sources.append(source_id)
        return {
            "accepted_sources": accepted_sources,
            "rejected_sources": rejected_sources,
        }

    async def interpret_preferences(
        self,
        *,
        prompt: str,
        category: str,
        user_message: str,
        current_preferences_markdown: Optional[str],
    ) -> dict:
        normalized = (user_message or "").strip().lower()
        current_lines = [
            line.strip()
            for line in (current_preferences_markdown or "").splitlines()
            if line.strip().startswith("- ")
        ]

        if not normalized or any(token in normalized for token in ("ciao", "grazie", "ok grazie")):
            return {"should_update": False, "final_preferences_markdown": ""}

        if any(token in normalized for token in ("nessuna preferenza", "nessuna", "no preference", "no preferences")):
            return {"should_update": True, "final_preferences_markdown": "- nessuna preferenza"}

        preferences = [line for line in current_lines if line.lower() != "- nessuna preferenza"]
        mapping = {
            "- vegan": {
                "add": ("vegano", "vegana", "vegan"),
                "remove": ("non sono piu vegana", "non sono più vegana", "non piu vegano", "non più vegano", "togli vegan", "rimuovi vegan"),
            },
            "- vegetarian": {
                "add": ("vegetar", "vegetarian"),
                "remove": ("non sono piu vegetariana", "non sono più vegetariana", "togli vegetarian", "rimuovi vegetarian"),
            },
            "- no dairy": {
                "add": ("intollerante al lattosio", "no lattosio", "senza lattosio", "lactose", "no dairy", "senza latte"),
                "remove": ("togli no dairy", "rimuovi no dairy", "tolgo il no lattosio"),
            },
            "- no gluten": {
                "add": ("glutine", "gluten", "celiac", "celiaco"),
                "remove": ("togli no gluten", "rimuovi no gluten"),
            },
            "- no nuts": {
                "add": ("arachidi", "peanut", "frutta a guscio", "nuts"),
                "remove": ("togli no nuts", "rimuovi no nuts"),
            },
            "- no fish": {
                "add": ("pesce", "fish", "seafood"),
                "remove": ("togli no fish", "rimuovi no fish"),
            },
            "- no beef": {
                "add": ("manzo", "beef"),
                "remove": ("togli no beef", "rimuovi no beef"),
            },
            "- no pork": {
                "add": ("maiale", "pork"),
                "remove": ("togli no pork", "rimuovi no pork"),
            },
            "- no palm oil": {
                "add": ("palma", "palm oil"),
                "remove": ("togli no palm oil", "rimuovi no palm oil"),
            },
            "- no sugar": {
                "add": ("zucchero", "sugar"),
                "remove": ("togli no sugar", "rimuovi no sugar"),
            },
            "- senza plastica": {
                "add": ("senza plastica", "plastic free", "plastic-free", "no plastic"),
                "remove": ("togli senza plastica", "rimuovi senza plastica"),
            },
            "- solo bio": {
                "add": ("solo bio", "biologico", "organic only", "only organic"),
                "remove": ("togli solo bio", "rimuovi solo bio"),
            },
        }

        changed = False
        for bullet, directives in mapping.items():
            if any(token in normalized for token in directives["remove"]):
                if bullet in preferences:
                    preferences.remove(bullet)
                    changed = True
                continue
            if any(token in normalized for token in directives["add"]) and bullet not in preferences:
                preferences.append(bullet)
                changed = True

        if not changed:
            return {"should_update": False, "final_preferences_markdown": ""}

        return {"should_update": True, "final_preferences_markdown": "\n".join(preferences)}

    async def run_preferences_chat_turn(
        self,
        *,
        prompt: str,
        category: str,
        user_message: str,
        current_preferences_markdown: Optional[str],
        chat_history: list[dict[str, str]],
    ) -> dict:
        normalized = (user_message or "").strip().lower()
        interpreted = await self.interpret_preferences(
            prompt=prompt,
            category=category,
            user_message=user_message,
            current_preferences_markdown=current_preferences_markdown,
        )
        if any(token in normalized for token in ("cosa hai in memoria", "cosa hai salvato", "mostrami la memoria", "in memoria")):
            if current_preferences_markdown and current_preferences_markdown.strip():
                return {
                    "assistant_message": "Al momento ho salvato queste preferenze: {}.".format(
                        current_preferences_markdown.replace("\n", ", ")
                    ),
                    "should_update": False,
                    "final_preferences_markdown": "",
                    "needs_preference_input": False,
                }
            return {
                "assistant_message": "Al momento non ho preferenze salvate. Se vuoi, dimmele e le registro.",
                "should_update": False,
                "final_preferences_markdown": "",
                "needs_preference_input": True,
            }
        if interpreted.get("should_update"):
            return {
                "assistant_message": "Ho aggiornato la memoria delle tue preferenze generali.",
                "should_update": True,
                "final_preferences_markdown": interpreted.get("final_preferences_markdown", ""),
                "needs_preference_input": False,
            }
        if current_preferences_markdown and current_preferences_markdown.strip():
            return {
                "assistant_message": "Ho letto la memoria attuale. Se vuoi posso modificarla.",
                "should_update": False,
                "final_preferences_markdown": "",
                "needs_preference_input": False,
            }
        return {
            "assistant_message": "Dimmi pure le preferenze che vuoi salvare.",
            "should_update": False,
            "final_preferences_markdown": "",
            "needs_preference_input": True,
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
    async def fake_search_similar_products(product: ProductData, *, locale: Optional[str] = None, limit: Optional[int] = None) -> list[dict]:
        return []
    off_client.search_similar_products = fake_search_similar_products
    scoring_engine = ScoringEngine()
    rag_service = RagService(settings, FakeEmbeddingsClient(settings), llm_client, off_client)
    explainer = ScoreExplainer(settings, llm_client)
    impact_translator = ImpactTranslator()
    return PipelineOrchestrator(extractor, normalizer, off_client, scoring_engine, rag_service, explainer, impact_translator)


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
            "ecoscore_score": 62,
            "ecoscore_grade": "b",
            "ecoscore_data": {
                "score": 62,
                "grade": "b",
                "missing": {"ingredients": 0, "origins": 0, "packagings": 0},
                "agribalyse": {"co2_total": 1.73},
            },
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
    from app.services.alternatives_service import AlternativesService
    from app.services.impact_translator import ImpactTranslator
    from app.services.preferences_chat_service import PreferencesChatService
    from app.services.preferences_evaluator import PreferencesEvaluator
    from app.services.preferences_memory import PreferencesMemoryService

    build_orchestrator.cache_clear()
    monkeypatch.setattr(app_main, "settings", settings)
    monkeypatch.setattr(app_main, "build_orchestrator", lambda: orchestrator)
    monkeypatch.setattr(
        app_main,
        "build_alternatives_service",
        lambda: AlternativesService(
            orchestrator=orchestrator,
            preferences_evaluator=PreferencesEvaluator(),
            impact_translator=ImpactTranslator(),
            preferences_memory=PreferencesMemoryService(settings.off_data_dir.parent),
            preference_interpreter=PreferenceInterpreter(
                llm_client=FakeLLMClient(settings),
                prompt_path=settings.backend_dir / "app" / "prompts" / "manage_preferences.md",
            ),
        ),
    )
    monkeypatch.setattr(
        app_main,
        "build_preferences_chat_service",
        lambda: PreferencesChatService(
            preferences_memory=PreferencesMemoryService(settings.off_data_dir.parent),
            llm_client=FakeLLMClient(settings),
            prompt_path=settings.backend_dir / "app" / "prompts" / "preferences_chat_turn.md",
        ),
    )
    with TestClient(app) as client:
        yield client
