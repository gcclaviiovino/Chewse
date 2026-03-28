from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import httpx

from app.core.settings import Settings

OpenFoodFactsStatus = Literal["ok", "not_found", "rate_limited", "error", "parse_error"]


@dataclass
class OpenFoodFactsResult:
    status: OpenFoodFactsStatus
    http_status: Optional[int]
    product: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class _CacheEntry:
    result: OpenFoodFactsResult
    expires_at: float


class OpenFoodFactsClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cache: Dict[str, _CacheEntry] = {}

    async def healthcheck(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "local_dataset": str(self.settings.off_data_dir),
            "remote_base_url": self.settings.off_base_url,
        }

    async def fetch_product(self, barcode: str, locale: Optional[str] = None) -> Optional[Dict[str, Any]]:
        result = await self.fetch_product_result(barcode, locale=locale)
        if result.status != "ok":
            return None
        return {"status": 1, "product": result.product}

    async def fetch_product_result(self, barcode: str, locale: Optional[str] = None) -> OpenFoodFactsResult:
        started_at = time.perf_counter()
        normalized_barcode = (barcode or "").strip()
        cache_key = normalized_barcode

        cached_result = self._get_cached_result(cache_key)
        if cached_result is not None:
            cached_result.meta.setdefault("timings", {})
            cached_result.meta["timings"]["total_ms"] = int((time.perf_counter() - started_at) * 1000)
            cached_result.meta["cache"] = "hit"
            return cached_result

        try:
            local_payload = self._read_local_payload(normalized_barcode)
        except (json.JSONDecodeError, ValueError) as exc:
            return OpenFoodFactsResult(
                status="parse_error",
                http_status=200,
                error_code="invalid_local_json",
                error_detail=str(exc),
                meta={
                    "retry_count": 0,
                    "source": "local_file",
                    "timings": {"total_ms": int((time.perf_counter() - started_at) * 1000)},
                    "cache": "miss",
                },
            )
        if local_payload is not None:
            result = self._result_from_payload(
                payload=local_payload,
                http_status=200,
                barcode=normalized_barcode,
                locale=locale,
                retry_count=0,
                source="local_file",
                started_at=started_at,
            )
            result.meta["cache"] = "miss"
            self._store_cache(cache_key, result)
            return result

        retry_count = 0
        last_result: Optional[OpenFoodFactsResult] = None
        async with httpx.AsyncClient(timeout=self._build_timeout()) as client:
            while True:
                attempt_started = time.perf_counter()
                try:
                    response = await client.get(
                        self._build_product_url(normalized_barcode),
                        headers=self._build_headers(),
                        params=self._build_query_params(locale),
                    )
                except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout, httpx.TimeoutException) as exc:
                    last_result = self._build_error_result(
                        http_status=None,
                        error_code=type(exc).__name__.lower(),
                        error_detail=str(exc),
                        retry_count=retry_count,
                        started_at=started_at,
                        source="remote",
                    )
                    if retry_count >= self.settings.off_max_retries:
                        last_result.meta["retry_exhausted"] = True
                        last_result.meta["cache"] = "miss"
                        return last_result
                    await self._sleep_before_retry(retry_count)
                    retry_count += 1
                    continue

                attempt_ms = int((time.perf_counter() - attempt_started) * 1000)
                status_code = response.status_code

                if status_code == 429:
                    last_result = self._build_error_result(
                        http_status=status_code,
                        error_code="rate_limited",
                        error_detail="Open Food Facts rate limit reached.",
                        retry_count=retry_count,
                        started_at=started_at,
                        source="remote",
                    )
                    last_result.status = "rate_limited"
                    last_result.meta["retry_after_seconds"] = self._retry_after_seconds(response)
                    last_result.meta["attempt_ms"] = attempt_ms
                    if retry_count >= self.settings.off_max_retries:
                        last_result.meta["retry_exhausted"] = True
                        last_result.meta["cache"] = "miss"
                        return last_result
                    await self._sleep_before_retry(retry_count, response=response)
                    retry_count += 1
                    continue

                if 500 <= status_code <= 599:
                    last_result = self._build_error_result(
                        http_status=status_code,
                        error_code="server_error",
                        error_detail="Open Food Facts returned a server error.",
                        retry_count=retry_count,
                        started_at=started_at,
                        source="remote",
                    )
                    last_result.meta["attempt_ms"] = attempt_ms
                    if retry_count >= self.settings.off_max_retries:
                        last_result.meta["retry_exhausted"] = True
                        last_result.meta["cache"] = "miss"
                        return last_result
                    await self._sleep_before_retry(retry_count)
                    retry_count += 1
                    continue

                if status_code != 200:
                    result = self._build_error_result(
                        http_status=status_code,
                        error_code="unexpected_status",
                        error_detail="Unexpected OFF response status.",
                        retry_count=retry_count,
                        started_at=started_at,
                        source="remote",
                    )
                    result.meta["attempt_ms"] = attempt_ms
                    result.meta["cache"] = "miss"
                    return result

                try:
                    payload = response.json()
                except (json.JSONDecodeError, ValueError) as exc:
                    result = OpenFoodFactsResult(
                        status="parse_error",
                        http_status=status_code,
                        error_code="invalid_json",
                        error_detail=str(exc),
                        meta={
                            "retry_count": retry_count,
                            "source": "remote",
                            "timings": {
                                "attempt_ms": attempt_ms,
                                "total_ms": int((time.perf_counter() - started_at) * 1000),
                            },
                            "cache": "miss",
                        },
                    )
                    return result

                result = self._result_from_payload(
                    payload=payload,
                    http_status=status_code,
                    barcode=normalized_barcode,
                    locale=locale,
                    retry_count=retry_count,
                    source="remote",
                    started_at=started_at,
                    attempt_ms=attempt_ms,
                )
                result.meta["cache"] = "miss"
                self._store_cache(cache_key, result)
                return result

    def _build_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.settings.off_timeout_connect_seconds,
            read=self.settings.off_timeout_read_seconds,
            write=self.settings.off_timeout_read_seconds,
            pool=self.settings.off_timeout_connect_seconds,
        )

    def _build_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": self.settings.off_user_agent,
            "Accept": "application/json",
        }

    def _build_query_params(self, locale: Optional[str]) -> Dict[str, str]:
        lc, cc = self._locale_hints(locale)
        params: Dict[str, str] = {}
        if lc:
            params["lc"] = lc
        if cc:
            params["cc"] = cc
        return params

    def _locale_hints(self, locale: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        raw_locale = (locale or self.settings.default_locale or "").strip()
        if "-" not in raw_locale:
            return None, None
        language, country = raw_locale.split("-", 1)
        lc = language.lower() or None
        cc = country.lower() or None
        return lc, cc

    def _build_product_url(self, barcode: str) -> str:
        return "{}/product/{}.json".format(self.settings.off_base_url.rstrip("/"), barcode)

    def _result_from_payload(
        self,
        *,
        payload: Any,
        http_status: int,
        barcode: str,
        locale: Optional[str],
        retry_count: int,
        source: str,
        started_at: float,
        attempt_ms: Optional[int] = None,
    ) -> OpenFoodFactsResult:
        if not isinstance(payload, dict):
            return OpenFoodFactsResult(
                status="parse_error",
                http_status=http_status,
                error_code="invalid_payload_shape",
                error_detail="OFF response body is not a JSON object.",
                meta=self._build_meta(retry_count, source, started_at, attempt_ms, locale),
            )

        product = payload.get("product")
        raw_status = payload.get("status")
        result = OpenFoodFactsResult(
            status="ok",
            http_status=http_status,
            product=product if isinstance(product, dict) else None,
            meta=self._build_meta(retry_count, source, started_at, attempt_ms, locale),
        )
        result.meta["barcode"] = barcode

        if raw_status == 0:
            result.status = "not_found"
            result.product = None
            result.error_code = "not_found"
            result.error_detail = payload.get("status_verbose") or "Product not found in Open Food Facts."
            return result

        if raw_status == 1 and isinstance(product, dict):
            return result

        if isinstance(product, dict) and product:
            return result

        result.status = "parse_error"
        result.product = None
        result.error_code = "missing_product"
        result.error_detail = "OFF response did not contain a usable product object."
        return result

    def _build_meta(
        self,
        retry_count: int,
        source: str,
        started_at: float,
        attempt_ms: Optional[int],
        locale: Optional[str],
    ) -> Dict[str, Any]:
        meta: Dict[str, Any] = {
            "retry_count": retry_count,
            "source": source,
            "timings": {
                "total_ms": int((time.perf_counter() - started_at) * 1000),
            },
        }
        if attempt_ms is not None:
            meta["timings"]["attempt_ms"] = attempt_ms
        query = self._build_query_params(locale)
        if query:
            meta["locale_hints"] = query
        return meta

    def _build_error_result(
        self,
        *,
        http_status: Optional[int],
        error_code: str,
        error_detail: str,
        retry_count: int,
        started_at: float,
        source: str,
    ) -> OpenFoodFactsResult:
        return OpenFoodFactsResult(
            status="error",
            http_status=http_status,
            error_code=error_code,
            error_detail=error_detail,
            meta=self._build_meta(retry_count, source, started_at, None, None),
        )

    async def _sleep_before_retry(self, retry_count: int, response: Optional[httpx.Response] = None) -> None:
        retry_after = self._retry_after_seconds(response) if response is not None else None
        if retry_after is not None and self.settings.off_respect_retry_after:
            await asyncio.sleep(retry_after)
            return
        base_delay = max(self.settings.off_backoff_base_ms, 0) / 1000
        delay = base_delay * (2 ** retry_count)
        jitter = random.uniform(0, base_delay if base_delay > 0 else 0.1)
        await asyncio.sleep(delay + jitter)

    def _retry_after_seconds(self, response: httpx.Response) -> Optional[float]:
        header_value = response.headers.get("Retry-After")
        if not header_value:
            return None
        try:
            return max(float(header_value), 0.0)
        except ValueError:
            pass
        try:
            retry_at = parsedate_to_datetime(header_value)
        except (TypeError, ValueError):
            return None
        return max((retry_at.timestamp() - time.time()), 0.0)

    def _get_cached_result(self, barcode: str) -> Optional[OpenFoodFactsResult]:
        if not self.settings.off_cache_enabled:
            return None
        entry = self._cache.get(barcode)
        if entry is None:
            return None
        if time.monotonic() >= entry.expires_at:
            self._cache.pop(barcode, None)
            return None
        return OpenFoodFactsResult(
            status=entry.result.status,
            http_status=entry.result.http_status,
            product=dict(entry.result.product) if isinstance(entry.result.product, dict) else None,
            error_code=entry.result.error_code,
            error_detail=entry.result.error_detail,
            meta=dict(entry.result.meta),
        )

    def _store_cache(self, barcode: str, result: OpenFoodFactsResult) -> None:
        if not self.settings.off_cache_enabled:
            return
        ttl_seconds = 0
        if result.status == "ok":
            ttl_seconds = self.settings.off_cache_ttl_seconds
        elif result.status == "not_found":
            ttl_seconds = self.settings.off_cache_not_found_ttl_seconds
        if ttl_seconds <= 0:
            return
        self._cache[barcode] = _CacheEntry(
            result=OpenFoodFactsResult(
                status=result.status,
                http_status=result.http_status,
                product=dict(result.product) if isinstance(result.product, dict) else None,
                error_code=result.error_code,
                error_detail=result.error_detail,
                meta=dict(result.meta),
            ),
            expires_at=time.monotonic() + ttl_seconds,
        )

    def _read_local_payload(self, barcode: str) -> Optional[Dict[str, Any]]:
        file_path = Path(self.settings.off_data_dir) / "{}.json".format(barcode)
        if not file_path.exists():
            return None
        with file_path.open("r", encoding="utf-8") as file_obj:
            loaded = json.load(file_obj)
        return loaded if isinstance(loaded, dict) else None
