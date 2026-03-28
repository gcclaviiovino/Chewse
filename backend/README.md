# Social Food AI Pipeline

Local-first Python backend focused only on the LLM and retrieval pipeline for product understanding, deterministic scoring, explanation generation, and candidate-based product suggestions.

## Features

- Multimodal extraction from image via Regolo `qwen3-vl-32b`
- Barcode enrichment through Open Food Facts wrapper
- Canonical `ProductData` normalization
- Deterministic scoring engine decoupled from the LLM
- Explanation generation with think and no-think passes
- Embedding-assisted candidate comparison and AI reranking for similar-product suggestions
- Deterministic impact translation with explicit emissions deltas for frontend consumption
- Minimal FastAPI endpoints for health, run, and reindex
- Dedicated alternatives endpoint with preference-aware candidate fallback
- Step-by-step trace with `trace_id`, structured step logs, and degraded-step warnings
- Uniform API error envelopes: `error_code`, `message`, `details`, `trace_id`
- Configurable per-service retries, timeouts, request limits, and local path allowlists
- OFF barcode caching, typed degraded results, and defensive normalization for sparse payloads

## Run

1. Create a Python 3.11+ virtualenv.
2. Install requirements with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and adjust local endpoints if needed.
4. Start the API with `make dev` or `uvicorn app.main:app --reload`.

## Make Targets

- `make dev`: run the FastAPI app with reload
- `make test`: run the backend test suite
- `make lint`: run `ruff` or `flake8` if already installed, otherwise skip

## Config

- `DEFAULT_LOCALE`: fallback locale for `PipelineInput`
- `MAX_REQUEST_BYTES`: rejects oversized API payloads before processing
- `ALLOWED_IMAGE_ROOTS`: comma-separated roots allowed for `image_path`
- `ENABLE_PIPELINE_DEBUG_LAST`: enables `GET /pipeline/debug/last` when `true`
- `LLM_TIMEOUT_SECONDS`, `EMBEDDING_TIMEOUT_SECONDS`: per-service timeouts
- `LLM_RETRY_COUNT`, `EMBEDDING_RETRY_COUNT`: retry counts for remote calls
- `OFF_BASE_URL`: OFF API base URL. Default is `https://world.openfoodfacts.org/api/v2`
- `OFF_USER_AGENT`: required custom user agent in the format `AppName/Version (ContactEmail)`
- `OFF_TIMEOUT_CONNECT_SECONDS`, `OFF_TIMEOUT_READ_SECONDS`: OFF connect/read timeouts
- `OFF_MAX_RETRIES`, `OFF_BACKOFF_BASE_MS`, `OFF_RESPECT_RETRY_AFTER`: OFF retry controls
- `OFF_CACHE_ENABLED`, `OFF_CACHE_TTL_SECONDS`, `OFF_CACHE_NOT_FOUND_TTL_SECONDS`: OFF barcode cache controls
- `RETRY_BACKOFF_BASE_SECONDS`, `RETRY_JITTER_SECONDS`: retry timing controls
- `RAG_TOP_K`, `RAG_SCORE_THRESHOLD`, `RAG_METADATA_FILTERS`: suggestion output controls
- `SIMILAR_PRODUCTS_CANDIDATE_LIMIT`, `SIMILAR_PRODUCTS_SHORTLIST_SIZE`, `SIMILAR_PRODUCTS_SIMILARITY_THRESHOLD`: candidate generation and deterministic filtering controls
- `LLM_INPUT_MAX_CHARS`, `LLM_OUTPUT_MAX_CHARS`, `EXPLANATION_SHORT_MAX_CHARS`, `EXPLANATION_BULLET_MAX_CHARS`: prompt/output safety limits

## Reliability Behavior

- Invalid `image_path` values are rejected with a uniform error envelope instead of falling through silently.
- Open Food Facts, embeddings, and LLM failures use bounded retries with exponential backoff and jitter.
- OFF barcode lookups use `GET /api/v2/product/{barcode}.json` semantics:
  - `200` + `status=1`: success
  - `200` + `status=0`: not found
  - `429`: rate limited, optionally waits on `Retry-After`
  - `5xx`: retried, then degraded as HTTP error if exhausted
  - malformed JSON or invalid payload shape: degraded as parse error
- OFF requests send a custom `User-Agent` on every call and request JSON responses explicitly.
- OFF locale hints are derived from the pipeline locale when available and sent as `lc` and `cc`.
- OFF normalization is defensive for missing/null/wrong-type fields and records warnings in trace metadata.
- OFF barcode cache is in-memory, keyed by barcode, can be disabled, and can cache short-lived `not_found` responses.
- Similar-product suggestions no longer rely on generic text snippets alone. The pipeline now:
  - gathers candidate products from the local OFF subset and OFF search when available
  - filters candidates deterministically for category, ingredient, format, and quantity similarity
  - reranks the shortlist with the LLM while keeping a deterministic fallback
- `POST /alternatives/from-barcode` wraps the pipeline result, evaluates the candidate shortlist against user preferences, and can persist category-level preferences in local markdown memory (`backend/data/agent_memory/{user_id}.md`).
- The endpoint supports three preference inputs in priority order: `preferences_markdown` (inline), `user_message` (extracted to preferences), and memory fallback by `user_id` + product category.
- When no preference memory exists for that category, the response sets `needs_preference_input=true` and returns an `assistant_message` that can be shown by the frontend chat.
- If no candidate matches the stated preferences, the endpoint still returns up to 3 strong candidates with `requires_disclaimer=true` so the frontend can show a disclaimer instead of hiding the options.
- When a better alternative is found, the pipeline also returns `impact_comparison` with:
  - explicit emissions values for the base product and the selected alternative
  - `co2e_delta_kg_per_kg`
  - `estimated_co2e_savings_per_pack_kg` when quantity is comparable
  - human-readable summaries and conservative equivalences for frontend display
- The orchestrator degrades non-critical failures when possible:
  - Open Food Facts failure: pipeline can continue with image-only or query-only data.
  - Missing or weak candidate pool: suggestions return empty and record a warning in trace.
  - Embeddings or AI reranking failure: scoring and explanation still return, and suggestion generation falls back to deterministic ranking when possible.
- Explanation output is normalized into three sections:
  - observed facts
  - assumptions
  - actionable advice

## Debugging

- `trace_id` is generated per request and returned in `/health`, `/pipeline/run`, and all error envelopes.
- Each trace step includes status, duration, metadata summary, and the propagated `trace_id`.
- `GET /pipeline/debug/last` returns a redacted summary of the latest pipeline run only when `ENABLE_PIPELINE_DEBUG_LAST=true`.
- OFF trace metadata includes cache hit/miss, retry count, locale hints, and degraded reason codes such as `off_not_found`, `off_rate_limited`, `off_http_error`, `off_parse_error`, and `off_retry_exhausted`.
- Suggestion trace metadata includes local/remote candidate counts, filtered shortlist size, and warning states such as `candidate_pool_empty`, `no_similar_better_candidates`, or `llm_rerank_unavailable`.
- Impact trace metadata includes whether a comparison was generated, the selected candidate barcode, and any computed emissions deltas.

## OFF Integration Notes

- OFF data is best-effort only. The upstream docs explicitly note that product completeness and accuracy vary by item.
- For this local MVP, OFF lookup is enrichment, not a hard dependency. Scoring still runs even if OFF returns not found, rate limits, transient HTTP failures, or malformed JSON.
- When OFF already provides an Eco-Score, that remains the official environmental baseline. Local logic is used to enrich missing ingredients from OFF images, improve comparisons, and support fallback behavior.
- Example degraded flow: barcode only request, OFF `429`, cached miss, retries exhausted. The pipeline still returns a valid `PipelineOutput` with an empty/partial `ProductData`, deterministic score, explanation, and an OFF trace step containing `off_rate_limited` and `off_retry_exhausted`.
- Example degraded flow: barcode only request, OFF `200` + `status=0`. The pipeline returns a valid `PipelineOutput` and the OFF trace step records `off_not_found`.
- Example comparison flow: a scanned biscuit gets OFF official Eco-Score plus recovered ingredient text from `image_ingredients_url`; candidate products are then filtered to similar biscuits with better Eco-Score before the LLM writes the final recommendation.
- Example impact flow: if the chosen alternative has lower `co2e_kg_per_kg`, the backend exposes both raw emissions values and a derived per-pack estimate when the quantities are comparable.

## OFF Tests

Run only the OFF-focused tests with:

```bash
pytest backend/tests/test_openfoodfacts_client.py backend/tests/test_normalizer.py backend/tests/test_pipeline_orchestrator.py -q
```

## Troubleshooting

- `invalid_image_path`:
  - Ensure the file exists and is inside one of `ALLOWED_IMAGE_ROOTS`.
- `payload_too_large`:
  - Increase `MAX_REQUEST_BYTES` only if the local deployment actually needs it.
- Empty product suggestions with a warning in trace:
  - Rebuild or refresh the local OFF subset with `POST /pipeline/reindex`.
  - Check embeddings availability and `SIMILAR_PRODUCTS_SIMILARITY_THRESHOLD`.
- Missing `impact_comparison`:
  - This usually means no better similar candidate was found, or the candidate lacks enough emissions data for a strong comparison.
- `requires_disclaimer=true` in alternatives:
  - No candidate satisfied the current preference checks, so the backend returned the best available options anyway.
- Frequent remote retries or `*_request_failed` errors:
  - Verify the configured base URLs, auth headers, and local network access to the configured services.
- OFF rate limiting:
  - Reduce request volume, keep caching enabled, and ensure `OFF_USER_AGENT` is set to a real app identifier before increasing retry counts.

## Regolo.ai config

Regolo docs show bearer auth plus OpenAI-style endpoints. This backend is aligned to:

- `POST /v1/chat/completions`
- `POST /v1/embeddings`
- `GET /v1/models` for health probing

If both models are hosted on Regolo and share one API key, set the same credentials once in `.env`:

```env
LLM_BASE_URL=https://api.regolo.ai
EMBEDDING_BASE_URL=https://api.regolo.ai
REGOLO_API_KEY=your_single_key_here
REGOLO_API_HEADER=Authorization
REGOLO_API_PREFIX=Bearer
```

## Notes

- For remote multimodal extraction, the backend reads the local image file and sends it as a base64 data URL inside an OpenAI-style chat message.
- `backend/data/off_subset` can host local OFF JSON documents for Chroma indexing and barcode fallback.
- Logs and debug payloads redact raw prompts, user queries, image data, and large raw response bodies.
