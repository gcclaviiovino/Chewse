from __future__ import annotations

import re
from types import SimpleNamespace
from typing import List, Optional, Set

from app.core.errors import AppError
from app.schemas.pipeline import (
    AlternativeCandidate,
    AlternativesRequest,
    AlternativesResponse,
    PipelineInput,
    ProductData,
    RagSuggestion,
)
from app.services.impact_translator import ImpactTranslator
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.preferences_evaluator import PreferencesEvaluator
from app.services.preferences_memory import PreferencesMemoryService


class AlternativesService:
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        preferences_evaluator: PreferencesEvaluator,
        impact_translator: ImpactTranslator,
        preferences_memory: PreferencesMemoryService,
    ) -> None:
        self.orchestrator = orchestrator
        self.preferences_evaluator = preferences_evaluator
        self.impact_translator = impact_translator
        self.preferences_memory = preferences_memory

    async def get_alternatives(self, request: AlternativesRequest) -> AlternativesResponse:
        pipeline_output = await self._build_pipeline_output(request)

        category = self._infer_preference_category(pipeline_output.product)
        user_id = self._resolve_user_id(request.user_id)
        memory_markdown = self.preferences_memory.load_category_preferences(user_id, category)

        preference_source = "none"
        active_preferences_markdown = None

        if request.preferences_markdown and request.preferences_markdown.strip():
            active_preferences_markdown = request.preferences_markdown.strip()
            preference_source = "inline_markdown"
            self.preferences_memory.upsert_category_preferences(user_id, category, active_preferences_markdown)
        elif request.user_message and request.user_message.strip():
            extracted = self._extract_preferences_from_message(request.user_message)
            if extracted:
                active_preferences_markdown = extracted
                preference_source = "user_message_extracted"
                self.preferences_memory.upsert_category_preferences(user_id, category, active_preferences_markdown)
            elif memory_markdown and memory_markdown.strip():
                active_preferences_markdown = memory_markdown.strip()
                preference_source = "memory_markdown"
        elif memory_markdown and memory_markdown.strip():
            active_preferences_markdown = memory_markdown.strip()
            preference_source = "memory_markdown"

        candidate_suggestions = list(pipeline_output.rag_suggestions)
        if active_preferences_markdown:
            candidate_suggestions.extend(
                await self._build_preference_aware_supplement(
                    product=pipeline_output.product,
                    locale=request.locale,
                    preferences_markdown=active_preferences_markdown,
                    excluded_barcodes={
                        str(item.candidate_barcode or "").strip()
                        for item in candidate_suggestions
                        if item.candidate_barcode
                    },
                    limit=6,
                )
            )

        deduped_suggestions: List[RagSuggestion] = []
        seen_barcodes: Set[str] = set()
        for suggestion in candidate_suggestions:
            barcode = str(suggestion.candidate_barcode or "").strip()
            if barcode and barcode in seen_barcodes:
                continue
            if barcode:
                seen_barcodes.add(barcode)
            deduped_suggestions.append(suggestion)

        evaluated = self._evaluate_candidates(
            deduped_suggestions,
            active_preferences_markdown,
        )
        compatible = [item for item in evaluated if item.is_preference_compatible]
        selected_pool = compatible if compatible else evaluated
        selected_candidates = selected_pool[:3]
        fallback_candidates: List[AlternativeCandidate] = []
        if not compatible and len(selected_candidates) < 3:
            fallback_candidates = await self._build_assessment_fallback_candidates(
                product=pipeline_output.product,
                locale=request.locale,
                excluded_barcodes={
                    str(item.suggestion.candidate_barcode or "").strip()
                    for item in selected_candidates
                    if item.suggestion.candidate_barcode
                },
                limit=3 - len(selected_candidates),
            )
            selected_candidates = selected_candidates + fallback_candidates

        requires_disclaimer = not bool(compatible) and bool(selected_candidates)

        final_candidates: List[AlternativeCandidate] = []
        for item in selected_candidates:
            final_candidates.append(
                AlternativeCandidate(
                    suggestion=item.suggestion,
                    is_preference_compatible=item.is_preference_compatible,
                    preference_warnings=item.preference_warnings,
                    requires_disclaimer=requires_disclaimer or item.requires_disclaimer,
                )
            )

        selected_candidate = final_candidates[0] if final_candidates else None
        impact_comparison = None
        if selected_candidate is not None:
            impact_comparison = self.impact_translator.build_impact_comparison(
                pipeline_output.product,
                [selected_candidate.suggestion],
            )

        needs_preference_input = not bool(active_preferences_markdown and active_preferences_markdown.strip())
        assistant_message = self._build_assistant_message(
            category=category,
            needs_preference_input=needs_preference_input,
            selected_candidates=selected_candidates,
        )

        return AlternativesResponse(
            trace_id=pipeline_output.trace_id,
            base_product=pipeline_output.product,
            candidates=final_candidates,
            selected_candidate=selected_candidate,
            impact_comparison=impact_comparison,
            requires_disclaimer=requires_disclaimer,
            preference_source=preference_source,
            preference_category=category,
            applied_preferences_markdown=active_preferences_markdown,
            needs_preference_input=needs_preference_input,
            assistant_message=assistant_message,
        )

    async def _build_preference_aware_supplement(
        self,
        *,
        product: ProductData,
        locale: str,
        preferences_markdown: str,
        excluded_barcodes: Set[str],
        limit: int,
    ) -> List[RagSuggestion]:
        if limit <= 0:
            return []

        rag_service = self.orchestrator.rag_service
        local_candidates = rag_service._load_local_candidates()
        remote_candidates = await self.orchestrator.off_client.search_similar_products(
            product,
            locale=locale,
            limit=max(limit * 5, 15),
        )
        candidate_pool = rag_service._normalize_candidates(local_candidates + remote_candidates)
        candidate_pool = rag_service._dedupe_candidates(candidate_pool, product.barcode)

        ranked_items: List[tuple[float, RagSuggestion]] = []
        for candidate in candidate_pool:
            candidate_barcode = str(candidate.barcode or "").strip()
            if not candidate_barcode or candidate_barcode in excluded_barcodes:
                continue

            similarity_score = round(
                (0.35 * rag_service._category_similarity(product.categories_tags, candidate.categories_tags))
                + (0.2 * rag_service._ingredient_similarity(product, candidate))
                + (0.2 * rag_service._name_similarity(product.product_name, candidate.product_name))
                + (0.15 * rag_service._quantity_similarity(product.quantity, candidate.quantity))
                + (0.1 * rag_service._packaging_similarity(product.packaging, candidate.packaging)),
                4,
            )
            if similarity_score <= 0:
                continue

            candidate_product = ProductData(
                product_name=candidate.product_name,
                brand=candidate.brand,
                barcode=candidate.barcode,
                ingredients_text=candidate.ingredients_text,
                ecoscore_score=candidate.ecoscore_score,
                ecoscore_grade=candidate.ecoscore_grade,
                co2e_kg_per_kg=candidate.co2e_kg_per_kg,
                co2e_source="off_agribalyse" if candidate.co2e_kg_per_kg is not None else None,
                packaging=candidate.packaging,
                origins=candidate.origins,
                labels_tags=candidate.labels_tags,
                categories_tags=candidate.categories_tags,
                quantity=candidate.quantity,
                source="openfoodfacts",
                confidence=0.65,
            )
            score = self.orchestrator.scoring_engine.compute_score(candidate_product)
            eco_signal = score.total_score / 100.0
            suggestion = RagSuggestion(
                title="Alternativa in linea con le preferenze",
                suggestion=self._build_preference_candidate_message(candidate.product_name, candidate.brand),
                rationale="Candidato simile rivalutato dando piu peso alle preferenze espresse, senza escludere del tutto le altre alternative.",
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
                similarity_score=similarity_score,
                eco_improvement_score=round(eco_signal, 3),
                final_rank_score=0.0,
                comparison_confidence=round(candidate_product.confidence, 3),
            )
            is_compatible, warnings = self.preferences_evaluator.evaluate(suggestion, preferences_markdown)
            preference_affinity = 1.0 if is_compatible else max(0.0, 1.0 - (0.35 * len(warnings)))
            final_rank = round(
                (0.4 * similarity_score)
                + (0.25 * eco_signal)
                + (0.35 * preference_affinity),
                4,
            )
            suggestion.final_rank_score = final_rank
            ranked_items.append((final_rank, suggestion))

        ranked_items.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in ranked_items[:limit]]

    async def _build_assessment_fallback_candidates(
        self,
        *,
        product: ProductData,
        locale: str,
        excluded_barcodes: Set[str],
        limit: int,
    ) -> List[AlternativeCandidate]:
        if limit <= 0:
            return []

        rag_service = self.orchestrator.rag_service
        local_candidates = rag_service._load_local_candidates()
        remote_candidates = await self.orchestrator.off_client.search_similar_products(
            product,
            locale=locale,
            limit=max(limit * 4, 12),
        )
        candidate_pool = rag_service._normalize_candidates(local_candidates + remote_candidates)
        candidate_pool = rag_service._dedupe_candidates(candidate_pool, product.barcode)

        ranked_fallbacks: List[tuple[float, object, AlternativeCandidate]] = []
        for candidate in candidate_pool:
            candidate_barcode = str(candidate.barcode or "").strip()
            if not candidate_barcode or candidate_barcode in excluded_barcodes:
                continue

            candidate_product = ProductData(
                product_name=candidate.product_name,
                brand=candidate.brand,
                barcode=candidate.barcode,
                ingredients_text=candidate.ingredients_text,
                ecoscore_score=candidate.ecoscore_score,
                ecoscore_grade=candidate.ecoscore_grade,
                co2e_kg_per_kg=candidate.co2e_kg_per_kg,
                co2e_source="off_agribalyse" if candidate.co2e_kg_per_kg is not None else None,
                packaging=candidate.packaging,
                origins=candidate.origins,
                labels_tags=candidate.labels_tags,
                categories_tags=candidate.categories_tags,
                quantity=candidate.quantity,
                source="openfoodfacts",
                confidence=0.65,
            )
            score = self.orchestrator.scoring_engine.compute_score(candidate_product)
            similarity_score = round(
                (0.35 * rag_service._category_similarity(product.categories_tags, candidate.categories_tags))
                + (0.2 * rag_service._ingredient_similarity(product, candidate))
                + (0.2 * rag_service._name_similarity(product.product_name, candidate.product_name))
                + (0.15 * rag_service._quantity_similarity(product.quantity, candidate.quantity))
                + (0.1 * rag_service._packaging_similarity(product.packaging, candidate.packaging)),
                4,
            )
            if similarity_score <= 0:
                continue

            assessed_rank = round((0.55 * similarity_score) + (0.45 * (score.total_score / 100.0)), 4)
            suggestion = RagSuggestion(
                title="Alternativa valutata con scoring locale",
                suggestion=self._build_fallback_candidate_message(candidate.product_name, candidate.brand, score.total_score),
                rationale="Nessuna alternativa ha soddisfatto tutte le preferenze. Questo prodotto e stato valutato con lo stesso motore di assessment del prodotto scansionato.",
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
                similarity_score=similarity_score,
                eco_improvement_score=round(score.total_score / 100.0, 3),
                final_rank_score=assessed_rank,
                comparison_confidence=round(candidate_product.confidence, 3),
            )
            ranked_fallbacks.append(
                (
                    assessed_rank,
                    candidate,
                    AlternativeCandidate(
                        suggestion=suggestion,
                        is_preference_compatible=False,
                        preference_warnings=[
                            "Nessuna alternativa ha soddisfatto tutte le preferenze; mostro una scelta simile valutata con lo stesso motore di scoring."
                        ],
                        requires_disclaimer=True,
                    ),
                )
            )

        ranked_fallbacks.sort(
            key=lambda item: (
                item[0],
                item[1].ecoscore_score if item[1].ecoscore_score is not None else -1,
            ),
            reverse=True,
        )
        return [item[2] for item in ranked_fallbacks[:limit]]

    async def _build_pipeline_output(self, request: AlternativesRequest):
        if request.barcode and request.barcode.strip():
            return await self.orchestrator.run_pipeline(
                PipelineInput(
                    barcode=request.barcode.strip(),
                    locale=request.locale,
                    user_query=request.user_query or "alternativa piu sostenibile",
                )
            )

        base_product = ProductData(
            product_name=(request.product_name or "").strip() or None,
            brand=(request.brand or "").strip() or None,
            ingredients_text=(request.ingredients_text or "").strip() or None,
            packaging=(request.packaging or "").strip() or None,
            origins=(request.origins or "").strip() or None,
            labels_tags=request.labels_tags,
            categories_tags=request.categories_tags,
            quantity=(request.quantity or "").strip() or None,
            source="image_llm",
            confidence=0.4,
        )
        if not (base_product.product_name or base_product.categories_tags):
            raise AppError(
                "missing_alternatives_context",
                "Either barcode or product context is required to fetch alternatives.",
                status_code=400,
            )

        rag_suggestions, _trace = await self.orchestrator.rag_service.suggest_with_trace(
            product=base_product,
            user_query=request.user_query or base_product.product_name or "alternativa piu sostenibile",
        )
        return SimpleNamespace(
            trace_id=None,
            product=base_product,
            rag_suggestions=rag_suggestions,
        )

    def _evaluate_candidates(
        self,
        suggestions: List[RagSuggestion],
        preferences_markdown: Optional[str],
    ) -> List[AlternativeCandidate]:
        evaluated: List[AlternativeCandidate] = []
        for suggestion in suggestions:
            is_compatible, warnings = self.preferences_evaluator.evaluate(suggestion, preferences_markdown)
            evaluated.append(
                AlternativeCandidate(
                    suggestion=suggestion,
                    is_preference_compatible=is_compatible,
                    preference_warnings=warnings,
                    requires_disclaimer=not is_compatible,
                )
            )
        evaluated.sort(
            key=lambda item: (
                item.is_preference_compatible,
                item.suggestion.final_rank_score if item.suggestion.final_rank_score is not None else 0.0,
                item.suggestion.eco_improvement_score if item.suggestion.eco_improvement_score is not None else 0.0,
            ),
            reverse=True,
        )
        return evaluated

    @staticmethod
    def _build_fallback_candidate_message(
        candidate_name: Optional[str],
        candidate_brand: Optional[str],
        assessed_score: int,
    ) -> str:
        name = candidate_name or "Prodotto simile"
        if candidate_brand:
            return "Valuta {} di {}. Punteggio ambientale stimato: {}/100.".format(name, candidate_brand, assessed_score)
        return "Valuta {}. Punteggio ambientale stimato: {}/100.".format(name, assessed_score)

    @staticmethod
    def _build_preference_candidate_message(
        candidate_name: Optional[str],
        candidate_brand: Optional[str],
    ) -> str:
        name = candidate_name or "Prodotto simile"
        if candidate_brand:
            return "Valuta {} di {} come opzione vicina alle tue preferenze.".format(name, candidate_brand)
        return "Valuta {} come opzione vicina alle tue preferenze.".format(name)

    @staticmethod
    def _infer_preference_category(product: ProductData) -> str:
        for raw_tag in product.categories_tags:
            cleaned = str(raw_tag or "").strip().lower()
            if not cleaned:
                continue
            if ":" in cleaned:
                cleaned = cleaned.split(":", 1)[1]
            cleaned = cleaned.replace("_", "-")
            cleaned = re.sub(r"\s+", "-", cleaned)
            if cleaned:
                return cleaned

        if product.product_name:
            tokens = re.findall(r"[a-zA-Z]+", product.product_name.lower())
            if tokens:
                return tokens[0]
        return "generic"

    @staticmethod
    def _resolve_user_id(user_id: Optional[str]) -> str:
        value = (user_id or "").strip()
        return value or "mvp-default-user"

    @staticmethod
    def _extract_preferences_from_message(message: str) -> Optional[str]:
        normalized = (message or "").strip().lower()
        if not normalized:
            return None

        bullets: List[str] = []
        if any(token in normalized for token in ("vegano", "vegan")):
            bullets.append("- vegan")
        if any(token in normalized for token in ("vegetar", "vegetarian")):
            bullets.append("- vegetarian")
        if any(token in normalized for token in ("lattosio", "lactose", "no dairy", "senza latte")):
            bullets.append("- no dairy")
        if any(token in normalized for token in ("glutine", "gluten", "celiac", "celiaco")):
            bullets.append("- no gluten")
        if any(token in normalized for token in ("arachidi", "peanut", "frutta a guscio", "nuts")):
            bullets.append("- no nuts")
        if any(token in normalized for token in ("pesce", "fish", "seafood")):
            bullets.append("- no fish")
        if any(token in normalized for token in ("manzo", "beef")):
            bullets.append("- no beef")
        if any(token in normalized for token in ("maiale", "pork")):
            bullets.append("- no pork")
        if any(token in normalized for token in ("palma", "palm oil")):
            bullets.append("- no palm oil")
        if any(token in normalized for token in ("zucchero", "sugar")):
            bullets.append("- no sugar")
        if any(token in normalized for token in ("senza plastica", "plastic free", "plastic-free", "no plastic")):
            bullets.append("- senza plastica")
        if any(token in normalized for token in ("solo bio", "biologico", "organic only", "only organic")):
            bullets.append("- solo bio")

        if not bullets:
            if any(token in normalized for token in ("nessuna preferenza", "nessuna", "no preference", "no preferences")):
                return "- nessuna preferenza"
            return None

        deduped = []
        seen = set()
        for bullet in bullets:
            if bullet in seen:
                continue
            seen.add(bullet)
            deduped.append(bullet)
        return "\n".join(deduped)

    @staticmethod
    def _build_assistant_message(
        *,
        category: str,
        needs_preference_input: bool,
        selected_candidates: List[AlternativeCandidate],
    ) -> str:
        if needs_preference_input:
            return (
                "Ti mostro alternative sostenibili per la categoria '{}'. "
                "Hai preferenze alimentari o intolleranze per questa categoria? "
                "Puoi rispondere, ad esempio: vegano, no lattosio, no glutine, no pesce, senza plastica, solo bio."
            ).format(category)

        if not selected_candidates:
            return "Non ho trovato alternative valide in questo momento, ma ho mantenuto le tue preferenze in memoria."

        return "Ho applicato le preferenze salvate per la categoria '{}' e ordinato le alternative disponibili.".format(category)
