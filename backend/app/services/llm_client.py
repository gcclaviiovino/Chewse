from __future__ import annotations

import base64
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.errors import AppError
from app.core.observability import guard_untrusted_text, log_event, redact_data, truncate_text
from app.core.retry import async_retry
from app.core.settings import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = settings.build_auth_headers()
        self.base_url = settings.normalize_base_url(settings.llm_base_url)
        self.logger = logging.getLogger("social-food.llm")

    async def healthcheck(self) -> Dict[str, Any]:
        try:
            data = await self._request_json("GET", "{}/v1/models".format(self.base_url), timeout=5.0, retry_count=1)
            return {"status": "ok", "model": self.settings.llm_model, "available": len(data.get("data", []))}
        except Exception as exc:
            return {"status": "error", "model": self.settings.llm_model, "detail": str(exc)}

    async def extract_from_image(
        self,
        image_path: str,
        prompt: str,
        user_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        prompt_text = self._render_prompt(
            prompt,
            {
                "user_notes": guard_untrusted_text(user_notes, self.settings.llm_input_max_chars),
                "image_path": image_path,
            },
        )
        image_url = self._build_data_url(image_path)
        raw = await self._chat_completion(
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }
            ],
            thinking=False,
        )
        return self.parse_json_response(raw, fallback_fields=("product_name", "brand", "barcode", "quantity", "packaging"))

    async def generate_explanation(
        self,
        prompt: str,
        product_payload: Dict[str, Any],
        score_payload: Dict[str, Any],
        mode: str = "no_think",
    ) -> Dict[str, Any]:
        prompt_text = self._render_prompt(
            prompt,
            {
                "mode": mode,
                "product_json": truncate_text(json.dumps(redact_data(product_payload), ensure_ascii=False), self.settings.llm_input_max_chars),
                "score_json": truncate_text(json.dumps(score_payload, ensure_ascii=False), self.settings.llm_input_max_chars),
            },
        )
        raw = await self._chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            thinking=mode == "think",
        )
        return self.parse_json_response(raw, fallback_fields=("explanation_short", "why_bullets", "facts", "assumptions", "actionable_advice"))

    async def generate_rag_answer(
        self,
        prompt: str,
        product_payload: Dict[str, Any],
        user_query: str,
        retrieved_docs: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        prompt_text = self._render_prompt(
            prompt,
            {
                "product_json": truncate_text(json.dumps(redact_data(product_payload), ensure_ascii=False), self.settings.llm_input_max_chars),
                "user_query": guard_untrusted_text(user_query, self.settings.llm_input_max_chars),
                "docs_json": truncate_text(json.dumps(redact_data(retrieved_docs), ensure_ascii=False), self.settings.llm_input_max_chars),
            },
        )
        raw = await self._chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            thinking=False,
        )
        return self.parse_json_response(raw, fallback_fields=("suggestions",))

    async def _chat_completion(
        self,
        messages: List[Dict[str, Any]],
        thinking: bool,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "max_tokens": self._default_max_tokens(thinking),
        }
        if thinking:
            payload["thinking"] = True

        data = await self._request_json(
            "POST",
            "{}/v1/chat/completions".format(self.base_url),
            json_body=payload,
            timeout=self.settings.llm_timeout_seconds,
            retry_count=self.settings.llm_retry_count,
        )
        return truncate_text(self._extract_message_content(data), self.settings.llm_output_max_chars)

    @staticmethod
    def _default_max_tokens(thinking: bool) -> int:
        return 1200 if thinking else 800

    @classmethod
    def parse_json_response(cls, raw_text: str, fallback_fields: tuple[str, ...] = ()) -> Dict[str, Any]:
        raw_text = raw_text.strip()
        if not raw_text:
            return {}

        try:
            parsed = json.loads(raw_text)
            return parsed if isinstance(parsed, dict) else {"data": parsed}
        except json.JSONDecodeError:
            repaired = cls._repair_json(raw_text)
            try:
                parsed = json.loads(repaired)
                return parsed if isinstance(parsed, dict) else {"data": parsed}
            except json.JSONDecodeError:
                partial = cls._extract_partial_object(raw_text, fallback_fields)
                partial["raw_text"] = truncate_text(raw_text, 400)
                partial["_parse_error"] = True
                return partial

    @staticmethod
    def _repair_json(raw_text: str) -> str:
        fenced_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        candidate = fenced_match.group(0) if fenced_match else raw_text
        candidate = candidate.replace("\n", " ").replace("\t", " ").strip()
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = re.sub(r"(?<!\\)'", '"', candidate)
        return candidate

    @staticmethod
    def _extract_partial_object(raw_text: str, fallback_fields: tuple[str, ...]) -> Dict[str, Any]:
        partial: Dict[str, Any] = {}
        for key in fallback_fields:
            if key in {"why_bullets", "facts", "assumptions", "actionable_advice", "suggestions"}:
                list_match = re.search(r'"?{}"?\s*:\s*\[(.*?)(?:\]|$)'.format(re.escape(key)), raw_text, re.DOTALL)
                if not list_match:
                    continue
                items = re.findall(r'"([^"]+)"|\'([^\']+)\'', list_match.group(1))
                partial[key] = [left or right for left, right in items if (left or right)]
                continue
            match = re.search(r'"?{}"?\s*:\s*("([^"]*)"|\'([^\']*)\'|[-+]?\d+(?:[\.,]\d+)?)'.format(re.escape(key)), raw_text)
            if not match:
                continue
            if match.group(2) is not None or match.group(3) is not None:
                partial[key] = match.group(2) or match.group(3)
            else:
                numeric = match.group(1).replace(",", ".")
                partial[key] = float(numeric) if "." in numeric else int(numeric)
        return partial

    @staticmethod
    def _extract_message_content(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return "{}"
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return truncate_text(content, 12000)
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return truncate_text("\n".join([part for part in text_parts if part]), 12000)
        if isinstance(content, dict):
            for key in ("text", "output_text", "content"):
                if key in content and isinstance(content[key], str):
                    return truncate_text(content[key], 12000)
        return truncate_text(json.dumps(content), 12000)

    @staticmethod
    def _build_data_url(image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError("Image not found: {}".format(image_path))
        mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return "data:{};base64,{}".format(mime_type, encoded)

    @staticmethod
    def _render_prompt(template: str, values: Dict[str, str]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{" + key + "}", value)
        return rendered

    async def _request_json(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        timeout: float,
        retry_count: int,
    ) -> Dict[str, Any]:
        async def operation() -> Dict[str, Any]:
            async with httpx.AsyncClient(timeout=timeout, headers=self.headers) as client:
                response = await client.request(method, url, json=json_body)
                response.raise_for_status()
                return response.json()

        try:
            return await async_retry(
                operation,
                attempts=max(1, retry_count + 1),
                base_delay_seconds=self.settings.retry_backoff_base_seconds,
                jitter_seconds=self.settings.retry_jitter_seconds,
                retry_on=(httpx.TimeoutException, httpx.HTTPError),
            )
        except Exception as exc:
            log_event(
                self.logger,
                logging.ERROR,
                "llm_request_failed",
                method=method,
                url=url,
                retry_count=retry_count,
                error_type=type(exc).__name__,
                message=str(exc),
            )
            raise AppError(
                "llm_request_failed",
                "The LLM service request failed.",
                status_code=502,
                details={"error_type": type(exc).__name__},
            ) from exc
