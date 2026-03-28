from __future__ import annotations

import base64
import binascii
import logging
from pathlib import Path
from uuid import uuid4
from typing import Optional

from fastapi.encoders import jsonable_encoder
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.errors import AppError, ErrorEnvelope
from app.core.logger import configure_logging
from app.core.observability import generate_trace_id, get_trace_id, log_event, redact_data, safe_debug_trace, set_trace_id
from app.core.settings import get_settings
from app.pipeline import build_alternatives_service, build_orchestrator
from app.schemas.pipeline import AlternativesRequest, AlternativesResponse, PipelineInput, PipelineOutput, UploadPhotoResponse

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(title=settings.app_name)
logger = logging.getLogger("social-food.api")


def _model_dump(model) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class UploadPhotoRequest(BaseModel):
    image: str = Field(min_length=20)
    mode: str = Field(default="fast")
    locale: str = Field(default="it-IT")
    user_query: Optional[str] = None


def _extract_base64_data(image_payload: str) -> str:
    if image_payload.startswith("data:"):
        marker = ";base64,"
        if marker not in image_payload:
            raise AppError(
                "invalid_image_payload",
                "Image payload must be a valid base64 data URL.",
                status_code=400,
            )
        return image_payload.split(marker, 1)[1].strip()
    return image_payload.strip()


def _infer_product_type(product_name: Optional[str]) -> str:
    name = (product_name or "").lower()
    if "banana" in name:
        return "banana"
    if "uovo" in name or "egg" in name:
        return "egg"
    return "apple"


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/alternatives/from-barcode", response_model=AlternativesResponse)
async def alternatives_from_barcode(payload: AlternativesRequest) -> AlternativesResponse:
    service = build_alternatives_service()
    return await service.get_alternatives(payload)


@app.post("/api/upload-photo", response_model=UploadPhotoResponse)
async def upload_photo(payload: UploadPhotoRequest) -> UploadPhotoResponse:
    mode = payload.mode if payload.mode in {"fast", "deep"} else "fast"

    encoded = _extract_base64_data(payload.image)
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise AppError(
            "invalid_image_payload",
            "Image payload is not valid base64.",
            status_code=400,
        )

    if not image_bytes:
        raise AppError(
            "invalid_image_payload",
            "Image payload is empty.",
            status_code=400,
        )

    allowed_root = settings.allowed_image_roots()[0]
    upload_dir = Path(allowed_root) / "captured_uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    image_path = upload_dir / f"webcam-{uuid4().hex}.jpg"
    image_path.write_bytes(image_bytes)

    pipeline_input = PipelineInput(
        image_path=str(image_path),
        mode=mode,
        locale=payload.locale,
        user_query=payload.user_query,
    )
    output = await build_orchestrator().run_pipeline(pipeline_input)

    return UploadPhotoResponse(
        trace_id=output.trace_id,
        name=output.product.product_name or "Prodotto sconosciuto",
        product_type=_infer_product_type(output.product.product_name),
        product_score=output.score.total_score,
        max_score=100,
        explanation_short=output.explanation_short,
        official_score=output.score.official_score,
        local_score=output.score.local_score,
        score_source=output.score.score_source,
        subscores=output.score.subscores,
        flags=output.score.flags,
    )


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
