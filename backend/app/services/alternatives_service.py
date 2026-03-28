from __future__ import annotations

import re
from typing import List, Optional

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
        pipeline_output = await self.orchestrator.run_pipeline(
            PipelineInput(
                barcode=request.barcode,
                locale=request.locale,
                user_query=request.user_query or "alternativa piu sostenibile",
            )
        )

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

        evaluated = self._evaluate_candidates(
            pipeline_output.rag_suggestions,
            active_preferences_markdown,
        )
        compatible = [item for item in evaluated if item.is_preference_compatible]
        selected_pool = compatible if compatible else evaluated
        selected_candidates = selected_pool[:3]
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
