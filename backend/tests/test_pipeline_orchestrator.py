from __future__ import annotations

import asyncio
import json

from app.schemas.pipeline import PipelineInput
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
    assert isinstance(result.rag_suggestions, list)


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
