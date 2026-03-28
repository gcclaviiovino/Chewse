from __future__ import annotations

from app.core.settings import get_settings
from app.schemas.pipeline import PipelineInput, PipelineOutput
from app.services.embeddings_client import EmbeddingsClient
from app.services.explainer import ScoreExplainer
from app.services.extractor import ProductExtractor
from app.services.llm_client import LLMClient
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.rag_service import RagService
from app.services.scoring_engine import ScoringEngine


def build_orchestrator() -> PipelineOrchestrator:
    settings = get_settings()
    normalizer = ProductNormalizer()
    llm_client = LLMClient(settings)
    embeddings_client = EmbeddingsClient(settings)
    extractor = ProductExtractor(settings, llm_client, normalizer)
    off_client = OpenFoodFactsClient(settings)
    scoring_engine = ScoringEngine()
    rag_service = RagService(settings, embeddings_client, llm_client)
    explainer = ScoreExplainer(settings, llm_client)
    return PipelineOrchestrator(extractor, normalizer, off_client, scoring_engine, rag_service, explainer)


async def run_pipeline(input: PipelineInput) -> PipelineOutput:
    orchestrator = build_orchestrator()
    return await orchestrator.run_pipeline(input)
