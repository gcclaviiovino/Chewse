from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.settings import Settings


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.headers = settings.build_auth_headers()
        self.base_url = settings.normalize_base_url(settings.llm_base_url)

    async def healthcheck(self) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=5.0, headers=self.headers) as client:
                response = await client.get("{}/v1/models".format(self.base_url))
                response.raise_for_status()
                data = response.json()
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
            {"user_notes": user_notes or "", "image_path": image_path},
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
        return self.parse_json_response(raw)

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
                "product_json": json.dumps(product_payload, ensure_ascii=False),
                "score_json": json.dumps(score_payload, ensure_ascii=False),
            },
        )
        raw = await self._chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            thinking=mode == "think",
        )
        return self.parse_json_response(raw)

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
                "product_json": json.dumps(product_payload, ensure_ascii=False),
                "user_query": user_query,
                "docs_json": json.dumps(retrieved_docs, ensure_ascii=False),
            },
        )
        raw = await self._chat_completion(
            messages=[{"role": "user", "content": prompt_text}],
            thinking=False,
        )
        return self.parse_json_response(raw)

    async def _chat_completion(
        self,
        messages: List[Dict[str, Any]],
        thinking: bool,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
        }
        if thinking:
            payload["thinking"] = True

        async with httpx.AsyncClient(
            timeout=self.settings.request_timeout_seconds,
            headers=self.headers,
        ) as client:
            response = await client.post(
                "{}/v1/chat/completions".format(self.base_url),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        return self._extract_message_content(data)

    @classmethod
    def parse_json_response(cls, raw_text: str) -> Dict[str, Any]:
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
                return {"raw_text": raw_text, "_parse_error": True}

    @staticmethod
    def _repair_json(raw_text: str) -> str:
        fenced_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        candidate = fenced_match.group(0) if fenced_match else raw_text
        candidate = candidate.replace("\n", " ").replace("\t", " ").strip()
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        candidate = re.sub(r"(?<!\\)'", '"', candidate)
        return candidate

    @staticmethod
    def _extract_message_content(payload: Dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return "{}"
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: List[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
            return "\n".join([part for part in text_parts if part])
        if isinstance(content, dict):
            for key in ("text", "output_text", "content"):
                if key in content and isinstance(content[key], str):
                    return content[key]
        return json.dumps(content)

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
