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
    subscores: Dict[str, int] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    deterministic_reasons: List[str] = Field(default_factory=list)
    rule_triggers: List[Dict[str, Any]] = Field(default_factory=list)


class RagSuggestion(BaseModel):
    title: str
    suggestion: str
    rationale: str
    sources: List[str] = Field(default_factory=list)


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
    trace: List[TraceStep] = Field(default_factory=list)
