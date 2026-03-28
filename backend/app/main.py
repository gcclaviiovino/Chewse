from __future__ import annotations

from fastapi import FastAPI

from app.core.logger import configure_logging
from app.core.settings import get_settings
from app.pipeline import build_orchestrator
from app.schemas.pipeline import PipelineInput, PipelineOutput

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name)


@app.get("/health")
async def health() -> dict:
    orchestrator = build_orchestrator()
    llm_status = await orchestrator.extractor.llm_client.healthcheck()
    embeddings_status = await orchestrator.rag_service.embeddings_client.healthcheck()
    chroma_status = await orchestrator.rag_service.healthcheck()
    off_status = await orchestrator.off_client.healthcheck()
    return {
        "status": "ok",
        "services": {
            "llm": llm_status,
            "embeddings": embeddings_status,
            "chroma": chroma_status,
            "openfoodfacts": off_status,
        },
    }


@app.post("/pipeline/run", response_model=PipelineOutput)
async def pipeline_run(payload: PipelineInput) -> PipelineOutput:
    orchestrator = build_orchestrator()
    return await orchestrator.run_pipeline(payload)


@app.post("/pipeline/reindex")
async def pipeline_reindex() -> dict:
    orchestrator = build_orchestrator()
    return await orchestrator.rag_service.reindex_from_local_subset()
