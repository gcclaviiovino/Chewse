from __future__ import annotations

import re
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

try:
    from pydantic import field_validator
except ImportError:  # pragma: no cover
    field_validator = None
    from pydantic import validator
else:  # pragma: no cover
    validator = None

try:
    from pydantic import model_validator
except ImportError:  # pragma: no cover
    model_validator = None
    from pydantic import root_validator
else:  # pragma: no cover
    root_validator = None


class PipelineInput(BaseModel):
    user_id: Optional[str] = None
    image_path: Optional[str] = None
    barcode: Optional[str] = None
    user_query: Optional[str] = None
    mode: Literal["fast", "deep"] = "fast"
    locale: str = "it-IT"

    if field_validator is not None:

        @field_validator("locale", mode="before")
        @classmethod
        def validate_locale(cls, value: Optional[str]) -> str:
            locale = (value or "it-IT").strip()
            if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", locale):
                raise ValueError("locale must use the format ll-CC, for example it-IT.")
            return locale

    else:

        @validator("locale", pre=True, always=True)
        def validate_locale(cls, value: Optional[str]) -> str:
            locale = (value or "it-IT").strip()
            if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", locale):
                raise ValueError("locale must use the format ll-CC, for example it-IT.")
            return locale

    if model_validator is not None:

        @model_validator(mode="after")
        def validate_required_input(self) -> "PipelineInput":
            if not any(getattr(self, key) for key in ("image_path", "barcode", "user_query")):
                raise ValueError("At least one of image_path, barcode, or user_query must be provided.")
            return self

    else:

        @root_validator(skip_on_failure=True)
        def validate_required_input(cls, values: Dict[str, Any]) -> Dict[str, Any]:
            if not any(values.get(key) for key in ("image_path", "barcode", "user_query")):
                raise ValueError("At least one of image_path, barcode, or user_query must be provided.")
            return values


class ProductData(BaseModel):
    product_name: Optional[str] = None
    brand: Optional[str] = None
    barcode: Optional[str] = None
    ingredients_text: Optional[str] = None
    eco_ingredient_signals: List[Dict[str, Any]] = Field(default_factory=list)
    ecoscore_score: Optional[int] = None
    ecoscore_grade: Optional[str] = None
    ecoscore_data: Dict[str, Any] = Field(default_factory=dict)
    co2e_kg_per_kg: Optional[float] = None
    co2e_source: Optional[str] = None
    field_provenance: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    data_completeness: Dict[str, bool] = Field(default_factory=dict)
    nutriments: Dict[str, Optional[Any]] = Field(default_factory=dict)
    packaging: Optional[str] = None
    origins: Optional[str] = None
    labels_tags: List[str] = Field(default_factory=list)
    categories_tags: List[str] = Field(default_factory=list)
    quantity: Optional[str] = None
    source: Literal["image_llm", "openfoodfacts", "hybrid", "unknown"] = "unknown"
    confidence: float = 0.0


class ScoreResult(BaseModel):
    total_score: int = 0
    official_score: Optional[int] = None
    local_score: Optional[int] = None
    score_source: Literal["off_ecoscore", "off_plus_local", "local_fallback"] = "local_fallback"
    co2e_kg_per_kg: Optional[float] = None
    co2e_source: Optional[str] = None
    subscores: Dict[str, int] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    deterministic_reasons: List[str] = Field(default_factory=list)
    rule_triggers: List[Dict[str, Any]] = Field(default_factory=list)


class RagSuggestion(BaseModel):
    title: str
    suggestion: str
    rationale: str
    sources: List[str] = Field(default_factory=list)
    candidate_barcode: Optional[str] = None
    candidate_product_name: Optional[str] = None
    candidate_brand: Optional[str] = None
    candidate_ingredients_text: Optional[str] = None
    candidate_packaging: Optional[str] = None
    candidate_origins: Optional[str] = None
    candidate_labels_tags: List[str] = Field(default_factory=list)
    candidate_ecoscore_score: Optional[int] = None
    candidate_ecoscore_grade: Optional[str] = None
    candidate_co2e_kg_per_kg: Optional[float] = None
    similarity_score: Optional[float] = None
    eco_improvement_score: Optional[float] = None
    final_rank_score: Optional[float] = None
    comparison_confidence: Optional[float] = None


class ImpactEquivalent(BaseModel):
    type: str
    label: str
    value: Optional[float] = None
    unit: Optional[str] = None
    confidence: Literal["low", "medium", "high"] = "medium"


class ImpactComparison(BaseModel):
    base_product_barcode: Optional[str] = None
    base_product_name: Optional[str] = None
    candidate_barcode: Optional[str] = None
    candidate_product_name: Optional[str] = None
    base_co2e_kg_per_kg: Optional[float] = None
    candidate_co2e_kg_per_kg: Optional[float] = None
    co2e_delta_kg_per_kg: Optional[float] = None
    estimated_co2e_savings_per_pack_kg: Optional[float] = None
    emissions_source: Optional[str] = None
    improvement_summary: List[str] = Field(default_factory=list)
    impact_equivalents: List[ImpactEquivalent] = Field(default_factory=list)
    comparison_confidence: float = 0.0


class TraceStep(BaseModel):
    step_name: str
    duration_ms: int
    status: Literal["ok", "error", "skipped"]
    trace_id: Optional[str] = None
    metadata_summary: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PipelineOutput(BaseModel):
    trace_id: Optional[str] = None
    product: ProductData
    score: ScoreResult
    explanation_short: str
    explanation_bullets: List[str] = Field(default_factory=list)
    rag_suggestions: List[RagSuggestion] = Field(default_factory=list)
    impact_comparison: Optional[ImpactComparison] = None
    trace: List[TraceStep] = Field(default_factory=list)


class UploadPhotoResponse(BaseModel):
    trace_id: Optional[str] = None
    name: str
    product_type: str
    product_score: int
    max_score: int = 100
    explanation_short: str
    official_score: Optional[int] = None
    local_score: Optional[int] = None
    score_source: Literal["off_ecoscore", "off_plus_local", "local_fallback"] = "local_fallback"
    subscores: Dict[str, int] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)


class AlternativesRequest(BaseModel):
    barcode: str
    locale: str = "it-IT"
    user_query: Optional[str] = None
    preferences_markdown: Optional[str] = None


class AlternativeCandidate(BaseModel):
    suggestion: RagSuggestion
    is_preference_compatible: bool = True
    preference_warnings: List[str] = Field(default_factory=list)
    requires_disclaimer: bool = False


class AlternativesResponse(BaseModel):
    trace_id: Optional[str] = None
    base_product: ProductData
    candidates: List[AlternativeCandidate] = Field(default_factory=list)
    selected_candidate: Optional[AlternativeCandidate] = None
    impact_comparison: Optional[ImpactComparison] = None
    requires_disclaimer: bool = False
    preference_source: Literal["none", "inline_markdown"] = "none"
