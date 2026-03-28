from __future__ import annotations

import asyncio
import json

from app.schemas.pipeline import PipelineInput
from app.services.openfoodfacts_client import OpenFoodFactsResult
from app.services.llm_client import LLMClient


def test_orchestrator_handles_image_only(orchestrator, sample_image_path) -> None:
    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(image_path=str(sample_image_path))))

    assert result.product.source == "image_llm"
    assert result.score.total_score >= 0
    assert result.explanation_short
    assert result.trace
    assert result.trace_id
    assert all(step.trace_id == result.trace_id for step in result.trace)


def test_orchestrator_handles_barcode_only(orchestrator, settings, sample_off_payload) -> None:
    barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    asyncio.run(orchestrator.rag_service.reindex_from_local_subset())

    result = asyncio.run(
        orchestrator.run_pipeline(PipelineInput(barcode=barcode, user_query="consigliami un'alternativa"))
    )

    assert result.product.source == "openfoodfacts"
    assert result.product.product_name == "Biscotti Avena"
    assert result.product.ecoscore_score == 62
    assert result.score.official_score == 62
    assert result.score.score_source == "off_ecoscore"
    assert result.score.co2e_kg_per_kg == 1.73
    assert isinstance(result.rag_suggestions, list)
    assert result.impact_comparison is None


def test_orchestrator_uses_barcode_extracted_from_image_for_off_lookup(
    orchestrator, settings, sample_image_path, sample_off_payload
) -> None:
    barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    asyncio.run(orchestrator.rag_service.reindex_from_local_subset())

    async def fake_extract(_pipeline_input):
        return orchestrator.normalizer.normalize_llm_payload(
            {
                "product_name": None,
                "brand": None,
                "barcode": barcode,
                "confidence": 0.66,
            }
        )

    orchestrator.extractor.extract = fake_extract

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(image_path=str(sample_image_path))))

    assert result.product.barcode == barcode
    assert result.product.product_name == "Biscotti Avena"
    assert result.product.source == "hybrid"
    assert result.score.official_score == 62
    extract_trace = next(step for step in result.trace if step.step_name == "extract_image")
    assert extract_trace.metadata["extracted_barcode"] == barcode
    assert extract_trace.metadata["barcode_promoted_for_lookup"] is True
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert off_trace.metadata["lookup_barcode"] == barcode
    assert off_trace.status == "ok"


def test_orchestrator_normalizes_spaced_barcode_extracted_from_image_for_off_lookup(
    orchestrator, settings, sample_image_path, sample_off_payload
) -> None:
    barcode = sample_off_payload["product"]["code"]
    spaced_barcode = "1234 567 890123"
    (settings.off_data_dir / "{}.json".format(barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    asyncio.run(orchestrator.rag_service.reindex_from_local_subset())

    async def fake_extract(_pipeline_input):
        return orchestrator.normalizer.normalize_llm_payload(
            {
                "product_name": None,
                "brand": None,
                "barcode": spaced_barcode,
                "confidence": 0.66,
            }
        )

    orchestrator.extractor.extract = fake_extract

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(image_path=str(sample_image_path))))

    assert result.product.barcode == barcode
    assert result.product.product_name == "Biscotti Avena"
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert off_trace.metadata["lookup_barcode"] == barcode
    assert off_trace.status == "ok"


def test_orchestrator_handles_missing_fields_fallback(orchestrator) -> None:
    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(user_query="snack salutare")))

    assert result.product.source == "unknown"
    assert result.score.total_score >= 0
    assert "low_confidence_product_data" in result.score.flags


def test_parser_handles_malformed_llm_json_gracefully() -> None:
    malformed = "{'product_name': 'X', 'confidence': 0.2,}"
    parsed = LLMClient.parse_json_response(malformed)

    assert parsed["product_name"] == "X"
    assert parsed["confidence"] == 0.2


def test_extracts_chat_content_from_string_response() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": "{\"ok\": true}"
                }
            }
        ]
    }
    assert LLMClient._extract_message_content(payload) == "{\"ok\": true}"


def test_extracts_chat_content_from_block_response() -> None:
    payload = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "{\"product_name\": \"X\"}"},
                    ]
                }
            }
        ]
    }
    assert LLMClient._extract_message_content(payload) == "{\"product_name\": \"X\"}"


def test_parser_falls_back_to_partial_object_on_unrecoverable_json() -> None:
    malformed = 'explanation_short: "Short", why_bullets: ["One", "Two"'
    parsed = LLMClient.parse_json_response(malformed, fallback_fields=("explanation_short", "why_bullets"))

    assert parsed["explanation_short"] == "Short"
    assert parsed["why_bullets"] == ["One", "Two"]
    assert parsed["_parse_error"] is True


def test_orchestrator_keeps_valid_output_when_off_not_found(orchestrator) -> None:
    async def fake_fetch_product_result(barcode: str, locale: str = None) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="not_found",
            http_status=200,
            error_code="not_found",
            error_detail="missing",
            meta={"retry_count": 0, "cache": "miss", "source": "remote"},
        )

    orchestrator.off_client.fetch_product_result = fake_fetch_product_result

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(barcode="000", user_query="healthy snack")))

    assert result.product.barcode == "000"
    assert result.score.total_score >= 0
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert "off_not_found" in off_trace.metadata["reason_codes"]


def test_orchestrator_keeps_valid_output_when_off_rate_limited(orchestrator) -> None:
    async def fake_fetch_product_result(barcode: str, locale: str = None) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="rate_limited",
            http_status=429,
            error_code="rate_limited",
            error_detail="slow down",
            meta={"retry_count": 2, "cache": "miss", "retry_after_seconds": 1.0, "retry_exhausted": True},
        )

    orchestrator.off_client.fetch_product_result = fake_fetch_product_result

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(barcode="429", user_query="healthy snack")))

    assert result.product.barcode == "429"
    assert result.score.total_score >= 0
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert "off_rate_limited" in off_trace.metadata["reason_codes"]
    assert "off_retry_exhausted" in off_trace.metadata["reason_codes"]


def test_orchestrator_keeps_valid_output_when_off_parse_error(orchestrator) -> None:
    async def fake_fetch_product_result(barcode: str, locale: str = None) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="parse_error",
            http_status=200,
            error_code="invalid_json",
            error_detail="bad json",
            meta={"retry_count": 0, "cache": "miss"},
        )

    orchestrator.off_client.fetch_product_result = fake_fetch_product_result

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(barcode="bad", user_query="healthy snack")))

    assert result.product.barcode == "bad"
    assert result.score.total_score >= 0
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert "off_parse_error" in off_trace.metadata["reason_codes"]


def test_orchestrator_keeps_valid_output_when_off_http_error(orchestrator) -> None:
    async def fake_fetch_product_result(barcode: str, locale: str = None) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="error",
            http_status=503,
            error_code="server_error",
            error_detail="upstream unavailable",
            meta={"retry_count": 2, "cache": "miss", "retry_exhausted": True},
        )

    orchestrator.off_client.fetch_product_result = fake_fetch_product_result

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(barcode="503", user_query="healthy snack")))

    assert result.product.barcode == "503"
    assert result.score.total_score >= 0
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert "off_http_error" in off_trace.metadata["reason_codes"]
    assert "off_retry_exhausted" in off_trace.metadata["reason_codes"]


def test_orchestrator_uses_off_ingredients_image_fallback(orchestrator) -> None:
    async def fake_fetch_product_result(barcode: str, locale: str = None) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="ok",
            http_status=200,
            product={
                "code": barcode,
                "product_name": "Biscotti",
                "brands": "Test Brand",
                "image_ingredients_url": "https://images.example.test/ingredients.jpg",
                "labels_tags": ["en:no-palm-oil"],
                "categories_tags": ["en:biscuits"],
                "quantity": "250g",
                "ecoscore_score": 55,
                "ecoscore_grade": "c",
                "ecoscore_data": {
                    "missing": {"ingredients": 1, "packagings": 0, "origins": 0},
                    "adjustments": {"threatened_species": {"warning": "ingredients_missing"}},
                    "agribalyse": {"co2_total": 1.8},
                },
            },
            meta={"retry_count": 0, "cache": "miss"},
        )

    orchestrator.off_client.fetch_product_result = fake_fetch_product_result

    result = asyncio.run(orchestrator.run_pipeline(PipelineInput(barcode="123", user_query="eco score")))

    assert result.product.ingredients_text == "whole wheat flour, olive oil, salt"
    assert result.product.source == "hybrid"
    assert result.score.official_score == 55
    assert result.score.score_source == "off_plus_local"
    assert result.score.co2e_kg_per_kg == 1.8
    assert result.product.field_provenance["ingredients_text"]["source"] == "off_image_ai"
    assert result.product.data_completeness["ingredients_text"] is True
    off_trace = next(step for step in result.trace if step.step_name == "fetch_openfoodfacts")
    assert off_trace.metadata["ingredients_image_fallback"] == "used"
    assert off_trace.metadata["ingredients_extracted"] is True
    merge_trace = next(step for step in result.trace if step.step_name == "normalize_merge")
    assert merge_trace.metadata["field_provenance"]["ingredients_text"]["source"] == "off_image_ai"
    assert merge_trace.metadata["data_completeness"]["ingredients_text"] is True


def test_orchestrator_builds_impact_comparison_for_better_alternative(orchestrator, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")
    better_candidate = {
        "status": 1,
        "product": {
            "code": "9999999999991",
            "product_name": "Biscotti Avena Integrali",
            "brands": "Green Brand",
            "ingredients_text": "oat flour, whole wheat flour, sunflower oil",
            "packaging": "paper",
            "origins": "Italy",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "240 g",
            "ecoscore_score": 78,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.1}},
        },
    }
    (settings.off_data_dir / "9999999999991.json").write_text(json.dumps(better_candidate), encoding="utf-8")
    asyncio.run(orchestrator.rag_service.reindex_from_local_subset())

    result = asyncio.run(
        orchestrator.run_pipeline(PipelineInput(barcode=base_barcode, user_query="alternativa piu sostenibile"))
    )

    assert result.rag_suggestions
    assert result.impact_comparison is not None
    assert result.impact_comparison.candidate_barcode == "9999999999991"
    assert result.impact_comparison.base_co2e_kg_per_kg == 1.73
    assert result.impact_comparison.candidate_co2e_kg_per_kg == 1.1
    assert result.impact_comparison.co2e_delta_kg_per_kg == 0.63
    assert result.impact_comparison.estimated_co2e_savings_per_pack_kg == 0.158
    impact_trace = next(step for step in result.trace if step.step_name == "translate_impact")
    assert impact_trace.metadata["has_impact_comparison"] is True
    assert impact_trace.metadata["candidate_barcode"] == "9999999999991"
