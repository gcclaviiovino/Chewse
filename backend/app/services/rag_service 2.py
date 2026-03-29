from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import chromadb
except ImportError:  # pragma: no cover
    chromadb = None

from app.core.settings import Settings
from app.core.observability import log_event
from app.product import model_to_dict
from app.schemas.pipeline import ProductData, RagSuggestion
from app.services.embeddings_client import EmbeddingsClient
from app.services.llm_client import LLMClient


class RagService:
    def __init__(
        self,
        settings: Settings,
        embeddings_client: EmbeddingsClient,
        llm_client: LLMClient,
    ) -> None:
        self.settings = settings
        self.embeddings_client = embeddings_client
        self.llm_client = llm_client
        self.client = self._build_client()
        self.collection_name = "off_snippets"
        self.logger = logging.getLogger("social-food.rag")

    async def healthcheck(self) -> Dict[str, Any]:
        try:
            collection = self._get_collection()
            return {"status": "ok", "collection": self.collection_name, "count": collection.count()}
        except Exception as exc:
            return {"status": "error", "collection": self.collection_name, "detail": str(exc)}

    async def reindex_from_local_subset(self) -> Dict[str, Any]:
        docs = self._load_off_subset()
        if not docs:
            return {"status": "empty", "indexed_documents": 0}

        existing_names = {collection.name for collection in self.client.list_collections()}
        if self.collection_name in existing_names:
            self.client.delete_collection(name=self.collection_name)
        collection = self.client.get_or_create_collection(name=self.collection_name)

        ids: List[str] = []
        embeddings: List[List[float]] = []
        metadatas: List[Dict[str, Any]] = []
        documents: List[str] = []

        for index, doc in enumerate(docs):
            doc_id = doc.get("id") or "doc-{}".format(index)
            text = doc.get("text", "")
            ids.append(doc_id)
            documents.append(text)
            metadatas.append(doc.get("metadata", {}))
            embeddings.append(await self.embeddings_client.embed_text(text))

        collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
        return {"status": "ok", "indexed_documents": len(ids)}

    async def suggest(
        self,
        product: ProductData,
        user_query: str,
        top_k: Optional[int] = None,
    ) -> List[RagSuggestion]:
        return (await self.suggest_with_trace(product=product, user_query=user_query, top_k=top_k))[0]

    async def suggest_with_trace(
        self,
        product: ProductData,
        user_query: str,
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        metadata_filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[List[RagSuggestion], Dict[str, Any]]:
        trace: Dict[str, Any] = {}
        try:
            collection = self._get_collection()
        except Exception as exc:
            trace["warning"] = "rag_index_unavailable"
            trace["detail"] = str(exc)
            return [], trace

        if collection.count() == 0:
            trace["warning"] = "rag_index_empty"
            return [], trace

        query_text = self._build_query(product, user_query)
        try:
            query_embedding = await self.embeddings_client.embed_text(query_text)
        except Exception as exc:
            trace["warning"] = "embeddings_unavailable"
            trace["detail"] = str(exc)
            return [], trace
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k or self.settings.rag_top_k)
        docs = self._format_results(
            results,
            score_threshold=score_threshold if score_threshold is not None else self.settings.rag_score_threshold,
            metadata_filters=metadata_filters or self.settings.rag_metadata_filters(),
        )
        if not docs:
            trace["warning"] = "rag_no_match"
            return [], trace

        prompt_path = self.settings.backend_dir / "app" / "prompts" / "rag_suggestions.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        try:
            response = await self.llm_client.generate_rag_answer(
                prompt=prompt,
                product_payload=model_to_dict(product),
                user_query=user_query,
                retrieved_docs=docs,
            )
        except Exception as exc:
            trace["warning"] = "rag_generation_failed"
            trace["detail"] = str(exc)
            log_event(self.logger, logging.WARNING, "rag_generation_failed", detail=str(exc))
            return [], trace

        suggestions_payload = response.get("suggestions") or []
        suggestions: List[RagSuggestion] = []
        for item in suggestions_payload:
            try:
                suggestions.append(RagSuggestion(**item))
            except Exception:
                continue
        trace["retrieved_count"] = len(docs)
        trace["suggestion_count"] = len(suggestions)
        return suggestions, trace

    def _get_collection(self):
        return self.client.get_or_create_collection(name=self.collection_name)

    def _build_client(self):
        if chromadb is not None:
            return chromadb.PersistentClient(path=str(self.settings.chroma_path))
        return _InMemoryChromaClient()

    def _load_off_subset(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for path in sorted(Path(self.settings.off_data_dir).glob("*.json")):
            with path.open("r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            product = payload.get("product", {})
            text_parts = [
                product.get("product_name"),
                product.get("brands"),
                product.get("ingredients_text"),
                product.get("packaging"),
                product.get("origins"),
            ]
            text = " | ".join([part for part in text_parts if part])
            docs.append(
                {
                    "id": product.get("code", path.stem),
                    "text": text,
                    "metadata": {
                        "barcode": product.get("code", path.stem),
                        "product_name": product.get("product_name"),
                        "brands": product.get("brands"),
                    },
                }
            )
        return docs

    @staticmethod
    def _build_query(product: ProductData, user_query: str) -> str:
        return " | ".join(
            [
                product.product_name or "",
                product.brand or "",
                product.ingredients_text or "",
                user_query or "",
            ]
        ).strip()

    @staticmethod
    def _format_results(
        results: Dict[str, Any],
        *,
        score_threshold: float,
        metadata_filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        ids = (results.get("ids") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]
        formatted: List[Dict[str, Any]] = []
        seen_normalized: set[str] = set()
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            if metadata_filters and any(metadata.get(key) != value for key, value in metadata_filters.items()):
                continue
            distance = distances[index] if index < len(distances) else 1.0
            score = max(0.0, 1.0 - float(distance))
            if score < score_threshold:
                continue
            normalized_text = " ".join(str(document or "").lower().split())
            if normalized_text in seen_normalized:
                continue
            seen_normalized.add(normalized_text)
            formatted.append(
                {
                    "id": ids[index] if index < len(ids) else "unknown",
                    "text": document,
                    "metadata": metadata,
                    "score": round(score, 4),
                }
            )
        return formatted


class _InMemoryCollection:
    def __init__(self, name: str) -> None:
        self.name = name
        self._items: List[Dict[str, Any]] = []

    def count(self) -> int:
        return len(self._items)

    def upsert(
        self,
        ids: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict[str, Any]],
        documents: List[str],
    ) -> None:
        self._items = []
        for index, doc_id in enumerate(ids):
            self._items.append(
                {
                    "id": doc_id,
                    "embedding": embeddings[index],
                    "metadata": metadatas[index],
                    "document": documents[index],
                }
            )

    def query(self, query_embeddings: List[List[float]], n_results: int) -> Dict[str, Any]:
        query = query_embeddings[0] if query_embeddings else []
        ranked = sorted(self._items, key=lambda item: _cosine_like_distance(query, item["embedding"]))
        top_items = ranked[:n_results]
        return {
            "ids": [[item["id"] for item in top_items]],
            "documents": [[item["document"] for item in top_items]],
            "metadatas": [[item["metadata"] for item in top_items]],
            "distances": [[_cosine_like_distance(query, item["embedding"]) for item in top_items]],
        }


class _InMemoryChromaClient:
    def __init__(self) -> None:
        self._collections: Dict[str, _InMemoryCollection] = {}

    def list_collections(self) -> List[_InMemoryCollection]:
        return list(self._collections.values())

    def delete_collection(self, name: str) -> None:
        self._collections.pop(name, None)

    def get_or_create_collection(self, name: str) -> _InMemoryCollection:
        if name not in self._collections:
            self._collections[name] = _InMemoryCollection(name)
        return self._collections[name]


def _cosine_like_distance(left: List[float], right: List[float]) -> float:
    if not left or not right:
        return 1e9
    paired = zip(left, right)
    dot = sum(a * b for a, b in paired)
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 1e9
    return 1 - (dot / (left_norm * right_norm))
