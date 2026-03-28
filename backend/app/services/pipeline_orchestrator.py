from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional

from app.product import merge_product_data
from app.schemas.pipeline import PipelineInput, PipelineOutput, ProductData, TraceStep
from app.services.explainer import ScoreExplainer
from app.services.extractor import ProductExtractor
from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient
from app.services.rag_service import RagService
from app.services.scoring_engine import ScoringEngine


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

    async def run_pipeline(self, pipeline_input: PipelineInput) -> PipelineOutput:
        trace: List[TraceStep] = []
        image_product: Optional[ProductData] = None
        off_product: Optional[ProductData] = None

        async with self._trace_step(trace, "extract_image") as metadata:
            if pipeline_input.image_path:
                image_product = await self.extractor.extract(pipeline_input)
                metadata["source"] = image_product.source
            else:
                metadata["reason"] = "image_path_not_provided"
                metadata["status_override"] = "skipped"

        async with self._trace_step(trace, "fetch_openfoodfacts") as metadata:
            if pipeline_input.barcode:
                off_payload = await self.off_client.fetch_product(pipeline_input.barcode)
                off_product = self.normalizer.normalize_off_payload(off_payload, barcode=pipeline_input.barcode)
                metadata["found"] = bool(off_payload)
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
            rag_suggestions = await self.rag_service.suggest(
                product=product,
                user_query=pipeline_input.user_query or product.product_name or "healthy alternative",
            )
            metadata["suggestion_count"] = len(rag_suggestions)

        return PipelineOutput(
            product=product,
            score=score,
            explanation_short=explanation_short,
            explanation_bullets=explanation_bullets,
            rag_suggestions=rag_suggestions,
            trace=trace,
        )

    @asynccontextmanager
    async def _trace_step(self, trace: List[TraceStep], step_name: str) -> AsyncIterator[Dict[str, Any]]:
        started_at = time.perf_counter()
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
            trace.append(
                TraceStep(
                    step_name=step_name,
                    duration_ms=int((time.perf_counter() - started_at) * 1000),
                    status=status,
                    metadata=metadata,
                )
            )
