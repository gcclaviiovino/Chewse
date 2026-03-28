from __future__ import annotations

import asyncio
import json

import httpx

from app.services.normalizer import ProductNormalizer
from app.services.openfoodfacts_client import OpenFoodFactsClient


def test_off_client_fetches_product_and_maps_response(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings)
    normalizer = ProductNormalizer()
    captured: dict = {}

    async def fake_get(self, url, headers=None, params=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(
            200,
            request=request,
            json={
                "status": 1,
                "product": {
                    "code": "1234567890123",
                    "product_name": "Biscotti Avena",
                    "brands": "Test Brand",
                    "ingredients_text": "oat flour, sugar",
                    "nutriments": {"sugars_100g": "12,5 g"},
                    "labels_tags": ["organic"],
                },
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = asyncio.run(client.fetch_product_result("1234567890123", locale="it-IT"))
    product, warnings = normalizer.normalize_off_payload_with_warnings(
        {"status": 1, "product": result.product or {}},
        barcode="1234567890123",
    )

    assert result.status == "ok"
    assert result.http_status == 200
    assert result.meta["cache"] == "miss"
    assert captured["headers"]["User-Agent"] == settings.off_user_agent
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["params"] == {"lc": "it", "cc": "it"}
    assert product.product_name == "Biscotti Avena"
    assert product.nutriments["sugars_100g"] == 12.5
    assert warnings == []


def test_off_client_returns_not_found_on_status_zero(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings)

    async def fake_get(self, url, headers=None, params=None):
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(200, request=request, json={"status": 0, "status_verbose": "product not found"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = asyncio.run(client.fetch_product_result("000"))

    assert result.status == "not_found"
    assert result.http_status == 200
    assert result.error_code == "not_found"
    assert result.product is None


def test_off_client_respects_retry_after_on_429(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings.model_copy(update={"off_max_retries": 1, "off_backoff_base_ms": 1}))
    attempts = {"count": 0}
    sleeps: list[float] = []

    async def fake_get(self, url, headers=None, params=None):
        attempts["count"] += 1
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(429, request=request, headers={"Retry-After": "2"})

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.services.openfoodfacts_client.asyncio.sleep", fake_sleep)

    result = asyncio.run(client.fetch_product_result("429"))

    assert result.status == "rate_limited"
    assert result.http_status == 429
    assert result.meta["retry_after_seconds"] == 2.0
    assert sleeps == [2.0]
    assert attempts["count"] == 2


def test_off_client_retries_5xx_then_fails(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings.model_copy(update={"off_max_retries": 2, "off_backoff_base_ms": 1}))
    attempts = {"count": 0}

    async def fake_get(self, url, headers=None, params=None):
        attempts["count"] += 1
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(503, request=request, json={"status": 0})

    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.services.openfoodfacts_client.asyncio.sleep", fake_sleep)

    result = asyncio.run(client.fetch_product_result("503"))

    assert result.status == "error"
    assert result.http_status == 503
    assert result.error_code == "server_error"
    assert result.meta["retry_exhausted"] is True
    assert attempts["count"] == 3


def test_off_client_returns_parse_error_on_malformed_json(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings)

    async def fake_get(self, url, headers=None, params=None):
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(200, request=request, content=b"{")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    result = asyncio.run(client.fetch_product_result("bad-json"))

    assert result.status == "parse_error"
    assert result.http_status == 200
    assert result.error_code == "invalid_json"


def test_off_client_cache_hit_miss_and_ttl_expiry(monkeypatch, settings) -> None:
    client = OpenFoodFactsClient(settings.model_copy(update={"off_cache_ttl_seconds": 5}))
    attempts = {"count": 0}
    clock = {"now": 100.0}

    async def fake_get(self, url, headers=None, params=None):
        attempts["count"] += 1
        request = httpx.Request("GET", url, headers=headers, params=params)
        return httpx.Response(
            200,
            request=request,
            json={"status": 1, "product": {"code": "321", "product_name": "Cached Product"}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
    monkeypatch.setattr("app.services.openfoodfacts_client.time.monotonic", lambda: clock["now"])

    first = asyncio.run(client.fetch_product_result("321"))
    second = asyncio.run(client.fetch_product_result("321"))
    clock["now"] = 106.0
    third = asyncio.run(client.fetch_product_result("321"))

    assert first.meta["cache"] == "miss"
    assert second.meta["cache"] == "hit"
    assert third.meta["cache"] == "miss"
    assert attempts["count"] == 2


def test_off_client_reads_local_payload_and_caches_it(settings) -> None:
    barcode = "999"
    payload = {"status": 1, "product": {"code": barcode, "product_name": "Local Product"}}
    (settings.off_data_dir / f"{barcode}.json").write_text(json.dumps(payload), encoding="utf-8")
    client = OpenFoodFactsClient(settings)

    first = asyncio.run(client.fetch_product_result(barcode))
    second = asyncio.run(client.fetch_product_result(barcode))

    assert first.status == "ok"
    assert first.meta["source"] == "local_file"
    assert first.meta["cache"] == "miss"
    assert second.meta["cache"] == "hit"
