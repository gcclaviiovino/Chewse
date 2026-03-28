from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ErrorEnvelope(BaseModel):
    error_code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    trace_id: str


class AppError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NonCriticalPipelineError(AppError):
    pass
