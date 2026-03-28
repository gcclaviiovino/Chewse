from __future__ import annotations

import asyncio
import base64

from app.core.errors import AppError
from app.schemas.pipeline import PipelineInput, ProductData


def test_validation_errors_use_uniform_envelope(api_client) -> None:
    response = api_client.post("/pipeline/run", json={"locale": "bad"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "validation_error"
    assert payload["trace_id"]
    assert "details" in payload


def test_path_traversal_is_rejected_with_uniform_envelope(api_client) -> None:
    response = api_client.post("/pipeline/run", json={"image_path": "../secret.jpg"})

    assert response.status_code == 400
    payload = response.json()
    assert payload["error_code"] == "invalid_image_path"
    assert payload["trace_id"]


def test_trace_id_is_returned_and_propagated(api_client, sample_image_path) -> None:
    response = api_client.post(
        "/pipeline/run",
        json={"image_path": str(sample_image_path), "mode": "fast"},
        headers={"x-trace-id": "trace-from-test"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"] == "trace-from-test"
    assert response.headers["x-trace-id"] == "trace-from-test"
    assert all(step["trace_id"] == "trace-from-test" for step in payload["trace"])


def test_debug_endpoint_returns_redacted_summary(api_client, orchestrator, sample_image_path) -> None:
    asyncio.run(orchestrator.run_pipeline(PipelineInput(image_path=str(sample_image_path), user_query="secret query")))

    response = api_client.get("/pipeline/debug/last")

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"]
    assert "output_summary" in payload


def test_payload_size_guard_returns_uniform_envelope(api_client, monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "max_request_bytes", 10)
    response = api_client.post("/pipeline/run", content=b'{"image_path":"12345678901"}')

    assert response.status_code == 413
    payload = response.json()
    assert payload["error_code"] == "payload_too_large"
    assert payload["trace_id"]


def test_health_includes_trace_id(api_client) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["trace_id"]


def test_upload_photo_endpoint_accepts_base64(api_client) -> None:
    encoded = base64.b64encode(b"fake-image-content").decode("ascii")
    response = api_client.post(
        "/api/upload-photo",
        json={
            "image": f"data:image/jpeg;base64,{encoded}",
            "mode": "fast",
            "locale": "it-IT",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["trace_id"]
    assert payload["name"]
    assert 0 <= payload["product_score"] <= payload["max_score"]
