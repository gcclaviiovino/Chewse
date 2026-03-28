from __future__ import annotations

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


class AlternativesService:
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        preferences_evaluator: PreferencesEvaluator,
        impact_translator: ImpactTranslator,
    ) -> None:
        self.orchestrator = orchestrator
        self.preferences_evaluator = preferences_evaluator
        self.impact_translator = impact_translator

    async def get_alternatives(self, request: AlternativesRequest) -> AlternativesResponse:
        pipeline_output = await self.orchestrator.run_pipeline(
            PipelineInput(
                barcode=request.barcode,
                locale=request.locale,
                user_query=request.user_query or "alternativa piu sostenibile",
            )
        )

        evaluated = self._evaluate_candidates(
            pipeline_output.rag_suggestions,
            request.preferences_markdown,
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

        return AlternativesResponse(
            trace_id=pipeline_output.trace_id,
            base_product=pipeline_output.product,
            candidates=final_candidates,
            selected_candidate=selected_candidate,
            impact_comparison=impact_comparison,
            requires_disclaimer=requires_disclaimer,
            preference_source="inline_markdown" if request.preferences_markdown else "none",
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
