from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any, Dict, Iterable, Optional

_TRACE_ID: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "headers",
    "image_bytes",
    "image_url",
    "prompt",
    "raw_text",
    "user_notes",
    "user_query",
    "ingredients_text",
    "product_json",
    "score_json",
    "docs_json",
}


def generate_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_id(trace_id: Optional[str]) -> None:
    _TRACE_ID.set(trace_id)


def get_trace_id() -> str:
    return _TRACE_ID.get() or generate_trace_id()


def summarize_metadata(metadata: Dict[str, Any]) -> str:
    redacted = redact_data(metadata)
    pairs = []
    for key, value in redacted.items():
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        pairs.append("{}={}".format(key, value))
    return ", ".join(pairs[:8])


def redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            if key.lower() in _SENSITIVE_KEYS:
                redacted[key] = "[redacted]"
            else:
                redacted[key] = redact_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_data(item) for item in value[:10]]
    if isinstance(value, str):
        compact = " ".join(value.split())
        if len(compact) > 160:
            return compact[:157] + "..."
        return compact
    return value


def truncate_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    suffix = "... [truncated]"
    if limit <= len(suffix):
        return suffix[:limit]
    return value[: limit - len(suffix)] + suffix


def guard_untrusted_text(value: Optional[str], limit: int) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    return "<<UNTRUSTED_INPUT>>\n{}\n<</UNTRUSTED_INPUT>>".format(truncate_text(text, limit))


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        "trace_id": fields.pop("trace_id", get_trace_id()),
        **redact_data(fields),
    }
    logger.log(level, json.dumps(payload, ensure_ascii=False, sort_keys=True))


class StepTimer:
    def __init__(self) -> None:
        self.started_at = time.perf_counter()

    @property
    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started_at) * 1000)


def safe_debug_trace(trace: Iterable[Any]) -> list[Dict[str, Any]]:
    safe_items: list[Dict[str, Any]] = []
    for item in trace:
        payload = item.model_dump() if hasattr(item, "model_dump") else item.dict()
        payload["metadata"] = redact_data(payload.get("metadata", {}))
        safe_items.append(payload)
    return safe_items
