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
from app.services.impact_translator import ImpactTranslator
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
        impact_translator: ImpactTranslator,
    ) -> None:
        self.extractor = extractor
        self.normalizer = normalizer
        self.off_client = off_client
        self.scoring_engine = scoring_engine
        self.rag_service = rag_service
        self.explainer = explainer
        self.impact_translator = impact_translator
        self._last_debug_payload: Dict[str, Any] = {}

    async def run_pipeline(self, pipeline_input: PipelineInput) -> PipelineOutput:
        trace_id = get_trace_id()
        set_trace_id(trace_id)
        trace: List[TraceStep] = []
        image_product: Optional[ProductData] = None
        off_product: Optional[ProductData] = None
        effective_barcode = (pipeline_input.barcode or "").strip() or None

        async with self._trace_step(trace, "extract_image") as metadata:
            if pipeline_input.image_path:
                try:
                    image_product = await self.extractor.extract(pipeline_input)
                    metadata["source"] = image_product.source
                    extracted_barcode = (image_product.barcode or "").strip() or None
                    if extracted_barcode:
                        metadata["extracted_barcode"] = extracted_barcode
                        if not effective_barcode:
                            effective_barcode = extracted_barcode
                            metadata["barcode_promoted_for_lookup"] = True
                except AppError:
                    raise
                except Exception as exc:
                    metadata["error"] = str(exc)
                    metadata["degraded"] = True
            else:
                metadata["reason"] = "image_path_not_provided"
                metadata["status_override"] = "skipped"

        async with self._trace_step(trace, "fetch_openfoodfacts") as metadata:
            if effective_barcode:
                try:
                    off_result = await self.off_client.fetch_product_result(
                        effective_barcode,
                        locale=pipeline_input.locale,
                    )
                    metadata["lookup_barcode"] = effective_barcode
                    metadata["off_status"] = off_result.status
                    metadata["http_status"] = off_result.http_status
                    metadata["retry_count"] = off_result.meta.get("retry_count", 0)
                    metadata["cache"] = off_result.meta.get("cache", "miss")
                    metadata["reason_codes"] = []
                    if "locale_hints" in off_result.meta:
                        metadata["locale_hints"] = off_result.meta["locale_hints"]
                    if "retry_after_seconds" in off_result.meta:
                        metadata["retry_after_seconds"] = off_result.meta["retry_after_seconds"]

                    if off_result.status == "ok":
                        off_payload = {"status": 1, "product": off_result.product or {}}
                        off_product, normalization_warnings = self.normalizer.normalize_off_payload_with_warnings(
                            off_payload,
                            barcode=effective_barcode,
                        )
                        metadata["found"] = bool(off_result.product)
                        if normalization_warnings:
                            metadata["normalization_warnings"] = normalization_warnings
                        ingredients_image_url = (off_result.product or {}).get("image_ingredients_url")
                        if (
                            ingredients_image_url
                            and not off_product.ingredients_text
                        ):
                            try:
                                ingredients_product = await self.extractor.extract_remote_image_url(
                                    ingredients_image_url,
                                    barcode=effective_barcode,
                                    user_notes="Focus on extracting ingredients_text from the ingredient panel image when visible.",
                                )
                                if ingredients_product.ingredients_text or ingredients_product.eco_ingredient_signals:
                                    if ingredients_product.ingredients_text:
                                        ingredients_product.field_provenance["ingredients_text"] = {
                                            "source": "off_image_ai",
                                            "confidence": ingredients_product.confidence,
                                        }
                                        ingredients_product.data_completeness["ingredients_text"] = True
                                    if ingredients_product.eco_ingredient_signals:
                                        ingredients_product.field_provenance["eco_ingredient_signals"] = {
                                            "source": "off_image_ai",
                                            "confidence": ingredients_product.confidence,
                                        }
                                        ingredients_product.data_completeness["eco_ingredient_signals"] = True
                                    off_product = merge_product_data(off_product, ingredients_product)
                                    metadata["ingredients_image_fallback"] = "used"
                                    metadata["ingredients_image_url_present"] = True
                                    metadata["ingredients_extracted"] = bool(ingredients_product.ingredients_text)
                            except Exception as exc:
                                metadata["ingredients_image_fallback"] = "failed"
                                metadata["ingredients_image_error"] = str(exc)
                    else:
                        off_product = ProductData(
                            barcode=effective_barcode,
                            source="unknown",
                            confidence=0.0,
                        )
                        metadata["found"] = False
                        metadata["degraded"] = True
                        metadata["error_code"] = off_result.error_code
                        metadata["error"] = off_result.error_detail
                        if off_result.status == "not_found":
                            metadata["reason_codes"].append("off_not_found")
                        elif off_result.status == "rate_limited":
                            metadata["reason_codes"].append("off_rate_limited")
                            if off_result.meta.get("retry_exhausted"):
                                metadata["reason_codes"].append("off_retry_exhausted")
                        elif off_result.status == "parse_error":
                            metadata["reason_codes"].append("off_parse_error")
                        else:
                            metadata["reason_codes"].append("off_http_error")
                            if off_result.meta.get("retry_exhausted"):
                                metadata["reason_codes"].append("off_retry_exhausted")
                except AppError as exc:
                    off_product = ProductData(
                        barcode=effective_barcode,
                        source="unknown",
                        confidence=0.0,
                    )
                    metadata["error"] = exc.message
                    metadata["error_code"] = exc.error_code
                    metadata["reason_codes"] = ["off_http_error"]
                    metadata["degraded"] = True
                except Exception as exc:
                    off_product = ProductData(
                        barcode=effective_barcode,
                        source="unknown",
                        confidence=0.0,
                    )
                    metadata["error"] = str(exc)
                    metadata["reason_codes"] = ["off_http_error"]
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
            metadata["data_completeness"] = product.data_completeness
            metadata["field_provenance"] = {
                key: value for key, value in product.field_provenance.items() if key in {
                    "ingredients_text",
                    "packaging",
                    "origins",
                    "ecoscore_score",
                    "co2e_kg_per_kg",
                }
            }

        async with self._trace_step(trace, "score_product") as metadata:
            score = self.scoring_engine.compute_score(product)
            metadata["total_score"] = score.total_score
            metadata["score_source"] = score.score_source
            metadata["official_score"] = score.official_score
            metadata["local_score"] = score.local_score
            if score.co2e_kg_per_kg is not None:
                metadata["co2e_kg_per_kg"] = score.co2e_kg_per_kg
                metadata["co2e_source"] = score.co2e_source

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

        async with self._trace_step(trace, "translate_impact") as metadata:
            impact_comparison = self.impact_translator.build_impact_comparison(product, rag_suggestions)
            metadata["has_impact_comparison"] = impact_comparison is not None
            if impact_comparison is not None:
                metadata["candidate_barcode"] = impact_comparison.candidate_barcode
                metadata["comparison_confidence"] = impact_comparison.comparison_confidence
                if impact_comparison.co2e_delta_kg_per_kg is not None:
                    metadata["co2e_delta_kg_per_kg"] = impact_comparison.co2e_delta_kg_per_kg
                if impact_comparison.estimated_co2e_savings_per_pack_kg is not None:
                    metadata["estimated_co2e_savings_per_pack_kg"] = impact_comparison.estimated_co2e_savings_per_pack_kg

        output = PipelineOutput(
            trace_id=trace_id,
            product=product,
            score=score,
            explanation_short=explanation_short,
            explanation_bullets=explanation_bullets,
            rag_suggestions=rag_suggestions,
            impact_comparison=impact_comparison,
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
