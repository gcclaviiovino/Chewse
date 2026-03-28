from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from app.core.errors import AppError
from app.core.observability import StepTimer, get_trace_id, log_event, set_trace_id, summarize_metadata
from app.product import merge_product_data
from app.schemas.pipeline import PipelineInput, PipelineOutput, ProductData, TraceStep
from app.services.explainer import ScoreExplainer
from app.services.extractor import ProductExtractor
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.rag_service import RagService
from app.services.scoring_engine import ScoringEngine

logger = logging.getLogger("social-food.pipeline")


class PipelineOrchestrator:
    def __init__(
        self,
        extractor: ProductExtractor,
        normalizer: ProductNormalizer,
        off_client: OpenFoodFactsClient,
        scoring_engine: ScoringEngine,
        rag_service: RagService,
        explainer: ScoreExplainer,
    ) -> None:
        self.extractor = extractor
        self.normalizer = normalizer
        self.off_client = off_client
        self.scoring_engine = scoring_engine
        self.rag_service = rag_service
        self.explainer = explainer
        self._last_debug_payload: Dict[str, Any] = {}

    async def run_pipeline(self, pipeline_input: PipelineInput) -> PipelineOutput:
        trace_id = get_trace_id()
        set_trace_id(trace_id)
        trace: List[TraceStep] = []
        image_product: Optional[ProductData] = None
        off_product: Optional[ProductData] = None

        async with self._trace_step(trace, "extract_image") as metadata:
            if pipeline_input.image_path:
                try:
                    image_product = await self.extractor.extract(pipeline_input)
                    metadata["source"] = image_product.source
                except AppError:
                    raise
                except Exception as exc:
                    metadata["error"] = str(exc)
                    metadata["degraded"] = True
            else:
                metadata["reason"] = "image_path_not_provided"
                metadata["status_override"] = "skipped"

        async with self._trace_step(trace, "fetch_openfoodfacts") as metadata:
            if pipeline_input.barcode:
                try:
                    off_payload = await self.off_client.fetch_product(pipeline_input.barcode)
                    off_product = self.normalizer.normalize_off_payload(off_payload, barcode=pipeline_input.barcode)
                    metadata["found"] = bool(off_payload)
                except AppError as exc:
                    metadata["error"] = exc.message
                    metadata["error_code"] = exc.error_code
                    metadata["degraded"] = True
                except Exception as exc:
                    metadata["error"] = str(exc)
                    metadata["degraded"] = True
            else:
                metadata["reason"] = "barcode_not_provided"
                metadata["status_override"] = "skipped"

        async with self._trace_step(trace, "normalize_merge") as metadata:
            primary = image_product or off_product or ProductData(source="unknown", confidence=0.0)
            product = merge_product_data(primary, off_product if image_product else None)
            if not image_product and off_product:
                product = off_product
            metadata["source"] = product.source
            metadata["confidence"] = product.confidence

        async with self._trace_step(trace, "score_product") as metadata:
            score = self.scoring_engine.compute_score(product)
            metadata["total_score"] = score.total_score

        async with self._trace_step(trace, "generate_explanation") as metadata:
            explanation_short, explanation_bullets = await self.explainer.explain(
                product=product,
                score=score,
                deep_mode=pipeline_input.mode == "deep",
            )
            metadata["bullet_count"] = len(explanation_bullets)

        async with self._trace_step(trace, "rag_suggestions") as metadata:
            rag_suggestions, rag_trace = await self.rag_service.suggest_with_trace(
                product=product,
                user_query=pipeline_input.user_query or product.product_name or "healthy alternative",
            )
            metadata.update(rag_trace)
            metadata["suggestion_count"] = len(rag_suggestions)

        output = PipelineOutput(
            trace_id=trace_id,
            product=product,
            score=score,
            explanation_short=explanation_short,
            explanation_bullets=explanation_bullets,
            rag_suggestions=rag_suggestions,
            trace=trace,
        )
        self._last_debug_payload = {
            "trace_id": trace_id,
            "input_summary": {
                "has_image_path": bool(pipeline_input.image_path),
                "has_barcode": bool(pipeline_input.barcode),
                "has_user_query": bool(pipeline_input.user_query),
                "mode": pipeline_input.mode,
                "locale": pipeline_input.locale,
            },
            "output": output,
        }
        return output

    def get_last_debug_payload(self) -> Dict[str, Any]:
        return self._last_debug_payload

    @asynccontextmanager
    async def _trace_step(self, trace: List[TraceStep], step_name: str) -> AsyncIterator[Dict[str, Any]]:
        timer = StepTimer()
        metadata: Dict[str, Any] = {}
        status = "ok"
        try:
            yield metadata
        except Exception as exc:
            status = "error"
            metadata["error"] = str(exc)
            raise
        finally:
            if metadata.get("status_override") == "skipped":
                status = "skipped"
                metadata.pop("status_override", None)
            elif metadata.get("degraded") and status == "ok":
                status = "error"
            trace_id = get_trace_id()
            metadata_summary = summarize_metadata(metadata)
            trace.append(
                TraceStep(
                    step_name=step_name,
                    duration_ms=timer.duration_ms,
                    status=status,
                    trace_id=trace_id,
                    metadata_summary=metadata_summary,
                    metadata=metadata,
                )
            )
            log_event(
                logger,
                logging.INFO if status != "error" else logging.WARNING,
                "pipeline_step",
                step=step_name,
                status=status,
                duration_ms=timer.duration_ms,
                trace_id=trace_id,
                metadata_summary=metadata_summary,
            )
