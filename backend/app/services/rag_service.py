from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import Settings
from app.core.observability import log_event
from app.product import model_to_dict
from app.schemas.pipeline import ProductData, RagSuggestion
from app.services.category_normalizer import canonicalize_category
from app.services.embeddings_client import EmbeddingsClient
from app.services.llm_client import LLMClient
from app.services.openfoodfacts_client import OpenFoodFactsClient


@dataclass
class _Candidate:
    barcode: str
    product_name: Optional[str]
    brand: Optional[str]
    ingredients_text: Optional[str]
    packaging: Optional[str]
    origins: Optional[str]
    quantity: Optional[str]
    labels_tags: List[str]
    categories_tags: List[str]
    ecoscore_score: Optional[int]
    ecoscore_grade: Optional[str]
    co2e_kg_per_kg: Optional[float]
    source: str
    embedding_score: float = 0.0
    similarity_score: float = 0.0
    eco_improvement_score: float = 0.0
    final_rank_score: float = 0.0
    comparison_confidence: float = 0.0


class RagService:
    def __init__(
        self,
        settings: Settings,
        embeddings_client: EmbeddingsClient,
        llm_client: LLMClient,
        off_client: OpenFoodFactsClient,
    ) -> None:
        self.settings = settings
        self.embeddings_client = embeddings_client
        self.llm_client = llm_client
        self.off_client = off_client
        self.logger = logging.getLogger("social-food.rag")

    async def healthcheck(self) -> Dict[str, Any]:
        local_docs = len(self._load_local_candidates())
        return {"status": "ok", "collection": "similar_products", "count": local_docs}

    async def reindex_from_local_subset(self) -> Dict[str, Any]:
        docs = self._load_local_candidates()
        if not docs:
            return {"status": "empty", "indexed_documents": 0}
        return {"status": "ok", "indexed_documents": len(docs)}

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
        del metadata_filters

        trace: Dict[str, Any] = {}
        candidates = self._load_local_candidates()
        trace["local_candidate_count"] = len(candidates)

        remote_candidates = await self.off_client.search_similar_products(
            product,
            locale=None,
            limit=self.settings.similar_products_candidate_limit,
        )
        trace["remote_candidate_count"] = len(remote_candidates)
        candidates.extend(remote_candidates)
        candidate_pool = self._normalize_candidates(candidates)
        candidate_pool = self._dedupe_candidates(candidate_pool, product.barcode)
        trace["candidate_pool_count"] = len(candidate_pool)

        if not candidate_pool:
            trace["warning"] = "candidate_pool_empty"
            return [], trace

        ranked_candidates = await self._rank_candidates(
            product,
            candidate_pool,
            similarity_threshold=score_threshold if score_threshold is not None else self.settings.similar_products_similarity_threshold,
        )
        trace["retrieved_count"] = len(candidate_pool)
        trace["filtered_count"] = len(ranked_candidates)
        trace["candidate_barcodes"] = [candidate.barcode for candidate in ranked_candidates[:5]]

        if not ranked_candidates:
            trace["warning"] = "no_similar_better_candidates"
            return [], trace

        shortlist_size = max(1, min(top_k or self.settings.rag_top_k, self.settings.similar_products_shortlist_size))
        shortlist = ranked_candidates[:shortlist_size]
        shortlist = await self._filter_shortlist_for_substitutability(product, shortlist)

        suggestions = await self._rerank_with_llm(product, user_query, shortlist)
        if not suggestions:
            trace["warning"] = "llm_rerank_unavailable"
            suggestions = self._fallback_suggestions(product, shortlist)
        trace["suggestion_count"] = len(suggestions)
        return suggestions, trace

    async def _filter_shortlist_for_substitutability(
        self,
        product: ProductData,
        shortlist: List[_Candidate],
    ) -> List[_Candidate]:
        if len(shortlist) <= 1:
            return shortlist

        prompt_path = self.settings.backend_dir / "app" / "prompts" / "filter_alternative_coherence.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        retrieved_docs = [self._candidate_to_doc(candidate) for candidate in shortlist]

        try:
            response = await self.llm_client.filter_candidate_coherence(
                prompt=prompt,
                product_payload=model_to_dict(product),
                retrieved_docs=retrieved_docs,
            )
        except Exception as exc:
            log_event(self.logger, logging.WARNING, "rag_coherence_filter_failed", detail=str(exc))
            return shortlist

        accepted_sources = {
            str(source).strip()
            for source in (response.get("accepted_sources") or [])
            if str(source).strip()
        }
        if not accepted_sources:
            return shortlist

        filtered = [candidate for candidate in shortlist if candidate.barcode in accepted_sources]
        return filtered or shortlist

    async def _rerank_with_llm(
        self,
        product: ProductData,
        user_query: str,
        shortlist: List[_Candidate],
    ) -> List[RagSuggestion]:
        prompt_path = self.settings.backend_dir / "app" / "prompts" / "rag_suggestions.md"
        prompt = prompt_path.read_text(encoding="utf-8")
        retrieved_docs = [self._candidate_to_doc(candidate) for candidate in shortlist]

        try:
            response = await self.llm_client.generate_rag_answer(
                prompt=prompt,
                product_payload=model_to_dict(product),
                user_query=user_query,
                retrieved_docs=retrieved_docs,
            )
        except Exception as exc:
            log_event(self.logger, logging.WARNING, "rag_generation_failed", detail=str(exc))
            return []

        suggestions_payload = response.get("suggestions") or []
        candidate_by_barcode = {candidate.barcode: candidate for candidate in shortlist}
        suggestions: List[RagSuggestion] = []
        for item in suggestions_payload:
            if not isinstance(item, dict):
                continue
            source_ids = [str(value) for value in (item.get("sources") or []) if value]
            candidate = candidate_by_barcode.get(source_ids[0]) if source_ids else None
            if candidate is None:
                continue
            enriched_item = dict(item)
            enriched_item.setdefault("candidate_barcode", candidate.barcode)
            enriched_item.setdefault("candidate_product_name", candidate.product_name)
            enriched_item.setdefault("candidate_brand", candidate.brand)
            enriched_item.setdefault("candidate_ingredients_text", candidate.ingredients_text)
            enriched_item.setdefault("candidate_packaging", candidate.packaging)
            enriched_item.setdefault("candidate_origins", candidate.origins)
            enriched_item.setdefault("candidate_labels_tags", candidate.labels_tags)
            enriched_item.setdefault("candidate_ecoscore_score", candidate.ecoscore_score)
            enriched_item.setdefault("candidate_ecoscore_grade", candidate.ecoscore_grade)
            enriched_item.setdefault("candidate_co2e_kg_per_kg", candidate.co2e_kg_per_kg)
            enriched_item.setdefault("similarity_score", round(candidate.similarity_score, 3))
            enriched_item.setdefault("eco_improvement_score", round(candidate.eco_improvement_score, 3))
            enriched_item.setdefault("final_rank_score", round(candidate.final_rank_score, 3))
            enriched_item.setdefault("comparison_confidence", round(candidate.comparison_confidence, 3))
            try:
                suggestions.append(RagSuggestion(**enriched_item))
            except Exception:
                continue
        return suggestions

    async def _rank_candidates(
        self,
        product: ProductData,
        candidates: List[_Candidate],
        *,
        similarity_threshold: float,
    ) -> List[_Candidate]:
        base_score = product.ecoscore_score
        base_text = self._candidate_text_from_product(product)
        candidate_texts = [self._candidate_text(candidate) for candidate in candidates]
        embedding_scores = [0.0 for _ in candidates]

        if base_text and candidate_texts:
            try:
                embeddings = await self.embeddings_client.embed_texts([base_text] + candidate_texts)
                base_embedding = embeddings[0] if embeddings else []
                candidate_embeddings = embeddings[1:]
                for index, candidate_embedding in enumerate(candidate_embeddings):
                    embedding_scores[index] = self._cosine_similarity(base_embedding, candidate_embedding)
            except Exception as exc:
                log_event(self.logger, logging.WARNING, "rag_embeddings_failed", detail=str(exc))

        ranked: List[_Candidate] = []
        for index, candidate in enumerate(candidates):
            candidate.embedding_score = embedding_scores[index] if index < len(embedding_scores) else 0.0
            category_score = self._category_similarity(product.categories_tags, candidate.categories_tags)
            ingredient_score = self._ingredient_similarity(product, candidate)
            name_score = self._name_similarity(product.product_name, candidate.product_name)
            quantity_score = self._quantity_similarity(product.quantity, candidate.quantity)
            packaging_score = self._packaging_similarity(product.packaging, candidate.packaging)

            candidate.similarity_score = round(
                (0.35 * category_score)
                + (0.2 * ingredient_score)
                + (0.2 * name_score)
                + (0.15 * candidate.embedding_score)
                + (0.05 * quantity_score)
                + (0.05 * packaging_score),
                4,
            )
            candidate.eco_improvement_score = round(
                self._eco_improvement_score(
                    base_ecoscore=base_score,
                    base_co2e=product.co2e_kg_per_kg,
                    candidate_ecoscore=candidate.ecoscore_score,
                    candidate_co2e=candidate.co2e_kg_per_kg,
                ),
                4,
            )
            candidate.comparison_confidence = round(self._comparison_confidence(candidate), 4)
            candidate.final_rank_score = round(
                (0.55 * candidate.similarity_score)
                + (0.35 * candidate.eco_improvement_score)
                + (0.1 * candidate.comparison_confidence),
                4,
            )

            if candidate.similarity_score < similarity_threshold:
                continue
            if base_score is not None and candidate.ecoscore_score is not None and candidate.ecoscore_score <= base_score:
                continue
            if base_score is None and candidate.ecoscore_score is None:
                continue
            ranked.append(candidate)

        ranked.sort(
            key=lambda item: (
                item.final_rank_score,
                item.ecoscore_score if item.ecoscore_score is not None else -1,
                item.similarity_score,
            ),
            reverse=True,
        )
        return ranked

    def _load_local_candidates(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for path in sorted(Path(self.settings.off_data_dir).glob("*.json")):
            with path.open("r", encoding="utf-8") as file_obj:
                payload = json.load(file_obj)
            product = payload.get("product", {})
            if isinstance(product, dict):
                docs.append(product)
        return docs

    def _normalize_candidates(self, payloads: List[Dict[str, Any]]) -> List[_Candidate]:
        normalized: List[_Candidate] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            barcode = str(payload.get("code") or payload.get("barcode") or "").strip()
            if not barcode:
                continue
            normalized.append(
                _Candidate(
                    barcode=barcode,
                    product_name=self._clean_text(payload.get("product_name")),
                    brand=self._clean_text(payload.get("brands") or payload.get("brand")),
                    ingredients_text=self._clean_text(payload.get("ingredients_text")),
                    packaging=self._clean_text(payload.get("packaging")),
                    origins=self._clean_text(payload.get("origins")),
                    quantity=self._clean_text(payload.get("quantity")),
                    labels_tags=self._coerce_list(payload.get("labels_tags")),
                    categories_tags=self._coerce_list(payload.get("categories_tags")),
                    ecoscore_score=self._coerce_int(payload.get("ecoscore_score")),
                    ecoscore_grade=self._clean_text(payload.get("ecoscore_grade")),
                    co2e_kg_per_kg=self._extract_co2e(payload),
                    source="openfoodfacts",
                )
            )
        return normalized

    def _dedupe_candidates(self, candidates: List[_Candidate], barcode_to_exclude: Optional[str]) -> List[_Candidate]:
        seen_barcodes: set[str] = set()
        seen_texts: set[str] = set()
        deduped: List[_Candidate] = []
        excluded = (barcode_to_exclude or "").strip()
        for candidate in candidates:
            if candidate.barcode == excluded:
                continue
            normalized_text = " ".join(self._candidate_text(candidate).lower().split())
            if candidate.barcode in seen_barcodes or normalized_text in seen_texts:
                continue
            seen_barcodes.add(candidate.barcode)
            if normalized_text:
                seen_texts.add(normalized_text)
            deduped.append(candidate)
        return deduped

    def _fallback_suggestions(self, product: ProductData, shortlist: List[_Candidate]) -> List[RagSuggestion]:
        suggestions: List[RagSuggestion] = []
        for candidate in shortlist:
            base_score = product.ecoscore_score
            delta_score = None
            if base_score is not None and candidate.ecoscore_score is not None:
                delta_score = candidate.ecoscore_score - base_score
            rationale_parts = []
            if delta_score is not None and delta_score > 0:
                rationale_parts.append("Eco-Score migliore di {} punti.".format(delta_score))
            if candidate.co2e_kg_per_kg is not None and product.co2e_kg_per_kg is not None:
                delta_co2e = round(product.co2e_kg_per_kg - candidate.co2e_kg_per_kg, 2)
                if delta_co2e > 0:
                    rationale_parts.append("Emissioni stimate inferiori di {} kg CO2e/kg.".format(delta_co2e))
            rationale_parts.append("Alternativa filtrata per categoria, ingredienti e formato comparabili.")
            suggestions.append(
                RagSuggestion(
                    title="Alternativa piu sostenibile",
                    suggestion=self._build_candidate_message(candidate),
                    rationale=" ".join(rationale_parts),
                    sources=[candidate.barcode],
                    candidate_barcode=candidate.barcode,
                    candidate_product_name=candidate.product_name,
                    candidate_brand=candidate.brand,
                    candidate_ingredients_text=candidate.ingredients_text,
                    candidate_packaging=candidate.packaging,
                    candidate_origins=candidate.origins,
                    candidate_labels_tags=candidate.labels_tags,
                    candidate_ecoscore_score=candidate.ecoscore_score,
                    candidate_ecoscore_grade=candidate.ecoscore_grade,
                    candidate_co2e_kg_per_kg=candidate.co2e_kg_per_kg,
                    similarity_score=round(candidate.similarity_score, 3),
                    eco_improvement_score=round(candidate.eco_improvement_score, 3),
                    final_rank_score=round(candidate.final_rank_score, 3),
                    comparison_confidence=round(candidate.comparison_confidence, 3),
                )
            )
        return suggestions

    @staticmethod
    def _build_candidate_message(candidate: _Candidate) -> str:
        name = candidate.product_name or "Prodotto simile"
        if candidate.brand:
            return "Valuta {} di {} come alternativa piu sostenibile.".format(name, candidate.brand)
        return "Valuta {} come alternativa piu sostenibile.".format(name)

    @staticmethod
    def _candidate_to_doc(candidate: _Candidate) -> Dict[str, Any]:
        return {
            "id": candidate.barcode,
            "text": RagService._candidate_text(candidate),
            "metadata": {
                "barcode": candidate.barcode,
                "product_name": candidate.product_name,
                "brand": candidate.brand,
                "ecoscore_score": candidate.ecoscore_score,
                "ecoscore_grade": candidate.ecoscore_grade,
                "co2e_kg_per_kg": candidate.co2e_kg_per_kg,
                "similarity_score": round(candidate.similarity_score, 3),
                "eco_improvement_score": round(candidate.eco_improvement_score, 3),
                "final_rank_score": round(candidate.final_rank_score, 3),
            },
            "score": round(candidate.final_rank_score, 4),
        }

    @staticmethod
    def _candidate_text(candidate: _Candidate) -> str:
        return " | ".join(
            [
                candidate.product_name or "",
                candidate.brand or "",
                candidate.ingredients_text or "",
                candidate.packaging or "",
                candidate.origins or "",
                " ".join(candidate.categories_tags),
            ]
        ).strip()

    @staticmethod
    def _candidate_text_from_product(product: ProductData) -> str:
        return " | ".join(
            [
                product.product_name or "",
                product.brand or "",
                product.ingredients_text or "",
                product.packaging or "",
                product.origins or "",
                " ".join(product.categories_tags),
            ]
        ).strip()

    @staticmethod
    def _category_similarity(base_categories: List[str], candidate_categories: List[str]) -> float:
        base = {RagService._normalize_tag(value) for value in base_categories if value}
        candidate = {RagService._normalize_tag(value) for value in candidate_categories if value}
        base.discard("")
        candidate.discard("")
        if not base or not candidate:
            return 0.0
        intersection = len(base & candidate)
        if not intersection:
            return 0.0
        return intersection / max(len(base), len(candidate), 1)

    @staticmethod
    def _ingredient_similarity(product: ProductData, candidate: _Candidate) -> float:
        base_tokens = RagService._ingredient_tokens_from_product(product)
        candidate_tokens = RagService._ingredient_tokens(candidate.ingredients_text)
        if not base_tokens or not candidate_tokens:
            return 0.0
        intersection = len(base_tokens & candidate_tokens)
        return intersection / max(len(base_tokens), len(candidate_tokens), 1)

    @staticmethod
    def _ingredient_tokens_from_product(product: ProductData) -> set[str]:
        signal_tokens = {str(item.get("id") or "").strip().lower() for item in product.eco_ingredient_signals if isinstance(item, dict)}
        signal_tokens.discard("")
        return signal_tokens or RagService._ingredient_tokens(product.ingredients_text)

    @staticmethod
    def _ingredient_tokens(value: Optional[str]) -> set[str]:
        if not value:
            return set()
        tokens = {
            token
            for token in re.findall(r"[a-zA-Z]{3,}", value.lower())
            if token not in {"con", "senza", "puo", "pu", "contiene", "tracce"}
        }
        return tokens

    @staticmethod
    def _name_similarity(base_name: Optional[str], candidate_name: Optional[str]) -> float:
        base_tokens = RagService._tokenize(base_name)
        candidate_tokens = RagService._tokenize(candidate_name)
        if not base_tokens or not candidate_tokens:
            return 0.0
        intersection = len(base_tokens & candidate_tokens)
        return intersection / max(len(base_tokens), len(candidate_tokens), 1)

    @staticmethod
    def _packaging_similarity(base_packaging: Optional[str], candidate_packaging: Optional[str]) -> float:
        base_tokens = RagService._tokenize(base_packaging)
        candidate_tokens = RagService._tokenize(candidate_packaging)
        if not base_tokens or not candidate_tokens:
            return 0.0
        intersection = len(base_tokens & candidate_tokens)
        return intersection / max(len(base_tokens), len(candidate_tokens), 1)

    @staticmethod
    def _quantity_similarity(base_quantity: Optional[str], candidate_quantity: Optional[str]) -> float:
        base = RagService._parse_quantity(base_quantity)
        candidate = RagService._parse_quantity(candidate_quantity)
        if not base or not candidate or base["unit"] != candidate["unit"]:
            return 0.0
        bigger = max(base["value"], candidate["value"], 1.0)
        smaller = min(base["value"], candidate["value"])
        ratio = smaller / bigger
        if ratio >= 0.8:
            return 1.0
        if ratio >= 0.6:
            return 0.7
        if ratio >= 0.4:
            return 0.4
        return 0.0

    @staticmethod
    def _parse_quantity(value: Optional[str]) -> Optional[Dict[str, Any]]:
        if not value:
            return None
        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(kg|g|ml|l)", value.lower())
        if not match:
            return None
        numeric = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        if unit == "kg":
            numeric *= 1000
            unit = "g"
        if unit == "l":
            numeric *= 1000
            unit = "ml"
        return {"value": numeric, "unit": unit}

    @staticmethod
    def _eco_improvement_score(
        *,
        base_ecoscore: Optional[int],
        base_co2e: Optional[float],
        candidate_ecoscore: Optional[int],
        candidate_co2e: Optional[float],
    ) -> float:
        score = 0.0
        if candidate_ecoscore is not None:
            if base_ecoscore is None:
                score += min(candidate_ecoscore / 100.0, 1.0)
            else:
                score += max(candidate_ecoscore - base_ecoscore, 0) / 30.0
        if base_co2e is not None and candidate_co2e is not None and base_co2e > 0:
            score += max(base_co2e - candidate_co2e, 0.0) / base_co2e
        return min(score, 1.0)

    @staticmethod
    def _comparison_confidence(candidate: _Candidate) -> float:
        checks = [
            bool(candidate.product_name),
            bool(candidate.categories_tags),
            candidate.ecoscore_score is not None,
            bool(candidate.ingredients_text),
            bool(candidate.quantity),
            candidate.co2e_kg_per_kg is not None,
        ]
        return sum(1 for item in checks if item) / len(checks)

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return max(0.0, min(numerator / (left_norm * right_norm), 1.0))

    @staticmethod
    def _extract_co2e(payload: Dict[str, Any]) -> Optional[float]:
        ecoscore_data = payload.get("ecoscore_data")
        if not isinstance(ecoscore_data, dict):
            return None
        agribalyse = ecoscore_data.get("agribalyse")
        if not isinstance(agribalyse, dict):
            return None
        value = agribalyse.get("co2_total")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _coerce_list(value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value is None:
            return []
        return [str(value)]

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        try:
            if value is None or value == "":
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _clean_text(value: Any) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _normalize_tag(value: str) -> str:
        return canonicalize_category(value).replace("-", " ").strip()

    @staticmethod
    def _tokenize(value: Optional[str]) -> set[str]:
        if not value:
            return set()
        return {token for token in re.findall(r"[a-zA-Z]{3,}", value.lower()) if token}
