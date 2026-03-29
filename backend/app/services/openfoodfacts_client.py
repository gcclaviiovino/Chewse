from __future__ import annotations

import asyncio
import base64
import json
import random
import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional

import httpx

from app.core.settings import Settings
from app.schemas.pipeline import ProductData
from app.services.category_normalizer import category_search_aliases, humanize_category

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
        product_urls = self._candidate_product_urls(normalized_barcode)
        async with httpx.AsyncClient(timeout=self._build_timeout()) as client:
            while True:
                failover_used = False
                response = None
                attempt_ms = None
                for url_index, product_url in enumerate(product_urls):
                    attempt_started = time.perf_counter()
                    try:
                        response = await client.get(
                            product_url,
                            headers=self._build_headers(base_url=product_url),
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
                        last_result.meta["attempted_url"] = product_url
                        if url_index < len(product_urls) - 1:
                            failover_used = True
                            continue
                        if retry_count >= self.settings.off_max_retries:
                            last_result.meta["retry_exhausted"] = True
                            last_result.meta["cache"] = "miss"
                            last_result.meta["failover_used"] = failover_used
                            return last_result
                        await self._sleep_before_retry(retry_count)
                        retry_count += 1
                        response = None
                        break

                    attempt_ms = int((time.perf_counter() - attempt_started) * 1000)
                    status_code = response.status_code
                    if 500 <= status_code <= 599 and url_index < len(product_urls) - 1:
                        failover_used = True
                        continue
                    break

                if response is None:
                    continue

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
                    last_result.meta["attempted_url"] = str(response.request.url)
                    last_result.meta["failover_used"] = failover_used
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
                    last_result.meta["attempted_url"] = str(response.request.url)
                    last_result.meta["failover_used"] = failover_used
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
                    result.meta["attempted_url"] = str(response.request.url)
                    result.meta["failover_used"] = failover_used
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
                    result.meta["attempted_url"] = str(response.request.url)
                    result.meta["failover_used"] = failover_used
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
                result.meta["attempted_url"] = str(response.request.url)
                result.meta["failover_used"] = failover_used
                result.meta["cache"] = "miss"
                self._store_cache(cache_key, result)
                return result

    async def search_similar_products(
        self,
        product: ProductData,
        *,
        locale: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Dict[str, Any]]:
        query_params_list = self._build_search_queries(product, locale=locale, limit=limit)
        if not query_params_list:
            return []

        retry_count = 0
        search_urls = self._candidate_search_urls()
        merged_results: list[Dict[str, Any]] = []
        seen_barcodes: set[str] = set()
        async with httpx.AsyncClient(timeout=self._build_timeout()) as client:
            for params in query_params_list:
                while True:
                    response = None
                    for url_index, search_url in enumerate(search_urls):
                        try:
                            response = await client.get(
                                search_url,
                                headers=self._build_headers(base_url=search_url),
                                params=params,
                            )
                        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout, httpx.TimeoutException):
                            if url_index < len(search_urls) - 1:
                                continue
                            if retry_count >= self.settings.off_max_retries:
                                return merged_results
                            await self._sleep_before_retry(retry_count)
                            retry_count += 1
                            response = None
                            break

                        if 500 <= response.status_code <= 599 and url_index < len(search_urls) - 1:
                            continue
                        break

                    if response is None:
                        continue

                    if response.status_code == 429:
                        if retry_count >= self.settings.off_max_retries:
                            return merged_results
                        await self._sleep_before_retry(retry_count, response=response)
                        retry_count += 1
                        continue

                    if 500 <= response.status_code <= 599:
                        if retry_count >= self.settings.off_max_retries:
                            return merged_results
                        await self._sleep_before_retry(retry_count)
                        retry_count += 1
                        continue

                    if response.status_code != 200:
                        break

                    try:
                        payload = response.json()
                    except (json.JSONDecodeError, ValueError):
                        break

                    for item in self._extract_search_products(payload):
                        barcode = str(item.get("code") or item.get("barcode") or "").strip()
                        if barcode and barcode not in seen_barcodes:
                            seen_barcodes.add(barcode)
                            merged_results.append(item)
                    break

        return merged_results

    def _build_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=self.settings.off_timeout_connect_seconds,
            read=self.settings.off_timeout_read_seconds,
            write=self.settings.off_timeout_read_seconds,
            pool=self.settings.off_timeout_connect_seconds,
        )

    def _build_headers(self, base_url: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "User-Agent": self.settings.off_user_agent,
            "Accept": "application/json",
        }
        # Use account credentials if provided, otherwise use staging defaults
        if self.settings.off_username and self.settings.off_password:
            credentials = base64.b64encode(
                f"{self.settings.off_username}:{self.settings.off_password}".encode()
            ).decode("ascii")
            headers["Authorization"] = f"Basic {credentials}"
        elif self._is_staging_url(base_url):
            credentials = base64.b64encode(b"off:off").decode("ascii")
            headers["Authorization"] = "Basic {}".format(credentials)
        return headers

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

    def _build_search_url(self) -> str:
        return "{}/search".format(self.settings.off_base_url.rstrip("/"))

    def _candidate_product_urls(self, barcode: str) -> list[str]:
        return ["{}/product/{}.json".format(base_url.rstrip("/"), barcode) for base_url in self._candidate_base_urls()]

    def _candidate_search_urls(self) -> list[str]:
        return ["{}/search".format(base_url.rstrip("/")) for base_url in self._candidate_base_urls()]

    def _candidate_base_urls(self) -> list[str]:
        primary = self.settings.off_base_url.rstrip("/")
        urls = [primary]
        if "world.openfoodfacts.org/api/v2" in primary:
            urls.append(primary.replace("world.openfoodfacts.org/api/v2", "world.openfoodfacts.net/api/v2"))
        deduped: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    @staticmethod
    def _is_staging_url(base_url: Optional[str]) -> bool:
        return bool(base_url and "world.openfoodfacts.net" in base_url)

    def _build_search_queries(
        self,
        product: ProductData,
        *,
        locale: Optional[str],
        limit: Optional[int],
    ) -> list[Dict[str, str]]:
        params = self._build_query_params(locale)
        page_size = max(1, limit or self.settings.similar_products_candidate_limit)
        base_params = dict(params)
        base_params.update(
            {
                "page_size": str(page_size),
                "fields": ",".join(
                    [
                        "code",
                        "product_name",
                        "brands",
                        "ingredients_text",
                        "packaging",
                        "origins",
                        "labels_tags",
                        "categories_tags",
                        "quantity",
                        "ecoscore_score",
                        "ecoscore_grade",
                        "ecoscore_data",
                        "image_ingredients_url",
                    ]
                ),
            }
        )

        queries: list[Dict[str, str]] = []
        category_names = category_search_aliases(product.categories_tags)
        for category_name in category_names[:3]:
            category_params = dict(base_params)
            category_params["categories_tags_en"] = category_name
            queries.append(category_params)

        product_name = (product.product_name or "").strip()
        if product_name:
            name_params = dict(base_params)
            name_params["product_name"] = product_name
            queries.append(name_params)

        if not queries:
            return []

        deduped: list[Dict[str, str]] = []
        seen: set[tuple[tuple[str, str], ...]] = set()
        for query in queries:
            marker = tuple(sorted(query.items()))
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(query)
        return deduped

    @staticmethod
    def _extract_search_products(payload: Any) -> list[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        products = payload.get("products")
        if not isinstance(products, list):
            return []
        return [item for item in products if isinstance(item, dict)]

    @staticmethod
    def _humanize_tag(value: str) -> str:
        return humanize_category(value)

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
