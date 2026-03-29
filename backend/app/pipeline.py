from __future__ import annotations

from functools import lru_cache

from app.core.settings import get_settings
from app.schemas.pipeline import PipelineInput, PipelineOutput
from app.services.alternatives_service import AlternativesService
from app.services.embeddings_client import EmbeddingsClient
from app.services.explainer import ScoreExplainer
from app.services.extractor import ProductExtractor
from app.services.impact_translator import ImpactTranslator
from app.services.llm_client import LLMClient
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.preference_interpreter import PreferenceInterpreter
from app.services.preferences_chat_service import PreferencesChatService
from app.services.preferences_evaluator import PreferencesEvaluator
from app.services.preferences_memory import PreferencesMemoryService
from app.services.rag_service import RagService
from app.services.scoring_engine import ScoringEngine


@lru_cache(maxsize=1)
def build_orchestrator() -> PipelineOrchestrator:
    settings = get_settings()
    normalizer = ProductNormalizer()
    llm_client = LLMClient(settings)
    embeddings_client = EmbeddingsClient(settings)
    extractor = ProductExtractor(settings, llm_client, normalizer)
    off_client = OpenFoodFactsClient(settings)
    scoring_engine = ScoringEngine()
    rag_service = RagService(settings, embeddings_client, llm_client, off_client)
    explainer = ScoreExplainer(settings, llm_client)
    impact_translator = ImpactTranslator()
    return PipelineOrchestrator(extractor, normalizer, off_client, scoring_engine, rag_service, explainer, impact_translator)


async def run_pipeline(input: PipelineInput) -> PipelineOutput:
    orchestrator = build_orchestrator()
    return await orchestrator.run_pipeline(input)


def build_alternatives_service() -> AlternativesService:
    settings = get_settings()
    orchestrator = build_orchestrator()
    llm_client = LLMClient(settings)
    preference_interpreter = PreferenceInterpreter(
        llm_client=llm_client,
        prompt_path=settings.backend_dir / "app" / "prompts" / "manage_preferences.md",
    )
    return AlternativesService(
        orchestrator=orchestrator,
        preferences_evaluator=PreferencesEvaluator(),
        impact_translator=ImpactTranslator(),
        preferences_memory=PreferencesMemoryService(settings.backend_dir),
        preference_interpreter=preference_interpreter,
    )


def build_preferences_chat_service() -> PreferencesChatService:
    settings = get_settings()
    llm_client = LLMClient(settings)
    return PreferencesChatService(
        preferences_memory=PreferencesMemoryService(settings.backend_dir),
        llm_client=llm_client,
        prompt_path=settings.backend_dir / "app" / "prompts" / "preferences_chat_turn.md",
    )
