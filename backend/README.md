# Social Food AI Pipeline

Local-first Python backend focused only on the LLM and retrieval pipeline for product understanding, deterministic scoring, explanation generation, and RAG suggestions.

## Features

- Multimodal extraction from image via Regolo `qwen3-vl-32b`
- Barcode enrichment through Open Food Facts wrapper
- Canonical `ProductData` normalization
- Deterministic scoring engine decoupled from the LLM
- Explanation generation with think and no-think passes
- Local ChromaDB retrieval powered by `Qwen3-Embedding-8B`
- Minimal FastAPI endpoints for health, run, and reindex
- Step-by-step trace for observability

## Run

1. Create a Python 3.11+ virtualenv.
2. Install requirements with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and adjust local endpoints if needed.
4. Start the API with `uvicorn app.main:app --reload`.

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
- Verified from docs: auth scheme, chat endpoint, embeddings endpoint, and embeddings payload shape.
- Inferred from OpenAI-compatible multimodal conventions: `messages[].content` blocks with `image_url` carrying a base64 data URL for vision input.
- Not yet verified against a live Regolo account in this workspace: exact availability and identifier of `qwen3-vl:32b`, exact identifier of `qwen3-embedding:8b`, and whether the deployed vision model accepts data URLs versus remote image URLs only.
