from __future__ import annotations

import logging

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import AppError, ErrorEnvelope
from app.core.logger import configure_logging
from app.core.observability import generate_trace_id, get_trace_id, log_event, redact_data, safe_debug_trace, set_trace_id
from app.core.settings import get_settings
from app.pipeline import build_orchestrator
from app.schemas.pipeline import PipelineInput, PipelineOutput

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name)
logger = logging.getLogger("social-food.api")


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


@app.middleware("http")
async def attach_trace_context(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id") or generate_trace_id()
    set_trace_id(trace_id)
    request.state.trace_id = trace_id

    if request.method in {"POST", "PUT", "PATCH"}:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.max_request_bytes:
            envelope = ErrorEnvelope(
                error_code="payload_too_large",
                message="Request payload exceeds the configured size limit.",
                details={"max_request_bytes": settings.max_request_bytes},
                trace_id=trace_id,
            )
            return JSONResponse(status_code=413, content=_model_dump(envelope))

    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or get_trace_id()
    log_event(
        logger,
        logging.WARNING,
        "request_failed",
        trace_id=trace_id,
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        path=str(request.url.path),
    )
    envelope = ErrorEnvelope(
        error_code=exc.error_code,
        message=exc.message,
        details=redact_data(exc.details),
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=_model_dump(envelope),
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or get_trace_id()
    details = {"errors": jsonable_encoder(exc.errors())}
    envelope = ErrorEnvelope(
        error_code="validation_error",
        message="Request validation failed.",
        details=details,
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=422,
        content=_model_dump(envelope),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or get_trace_id()
    log_event(
        logger,
        logging.ERROR,
        "unexpected_error",
        trace_id=trace_id,
        error_type=type(exc).__name__,
        message=str(exc),
        path=str(request.url.path),
    )
    envelope = ErrorEnvelope(
        error_code="internal_error",
        message="An unexpected error occurred.",
        details={"error_type": type(exc).__name__},
        trace_id=trace_id,
    )
    return JSONResponse(
        status_code=500,
        content=_model_dump(envelope),
    )


@app.get("/health")
async def health() -> dict:
    orchestrator = build_orchestrator()
    llm_status = await orchestrator.extractor.llm_client.healthcheck()
    embeddings_status = await orchestrator.rag_service.embeddings_client.healthcheck()
    chroma_status = await orchestrator.rag_service.healthcheck()
    off_status = await orchestrator.off_client.healthcheck()
    return {
        "status": "ok",
        "trace_id": get_trace_id(),
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


@app.get("/pipeline/debug/last")
async def pipeline_debug_last() -> dict:
    if not settings.enable_pipeline_debug_last:
        raise AppError(
            "debug_endpoint_disabled",
            "The debug endpoint is disabled.",
            status_code=404,
        )
    payload = build_orchestrator().get_last_debug_payload()
    if not payload:
        return {"trace_id": get_trace_id(), "status": "empty"}
    output = payload["output"]
    return {
        "trace_id": payload["trace_id"],
        "input_summary": payload["input_summary"],
        "output_summary": {
            "score": output.score.total_score,
            "flags": output.score.flags,
            "rag_suggestions": len(output.rag_suggestions),
            "trace": safe_debug_trace(output.trace),
        },
    }
