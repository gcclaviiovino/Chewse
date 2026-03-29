from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.services.llm_client import LLMClient


@dataclass
class PreferenceInterpretation:
    should_update: bool
    final_preferences_markdown: Optional[str]


class PreferenceInterpreter:
    def __init__(self, llm_client: LLMClient, prompt_path: Path) -> None:
        self.llm_client = llm_client
        self.prompt_template = prompt_path.read_text(encoding="utf-8")

    async def interpret(
        self,
        *,
        category: str,
        user_message: str,
        current_preferences_markdown: Optional[str],
    ) -> PreferenceInterpretation:
        payload = await self.llm_client.interpret_preferences(
            prompt=self.prompt_template,
            category=category,
            user_message=user_message,
            current_preferences_markdown=current_preferences_markdown,
        )

        should_update = bool(payload.get("should_update"))
        final_preferences_markdown = self._normalize_markdown(payload.get("final_preferences_markdown"))
        return PreferenceInterpretation(
            should_update=should_update and bool(final_preferences_markdown),
            final_preferences_markdown=final_preferences_markdown,
        )

    @staticmethod
    def _normalize_markdown(value: object) -> Optional[str]:
        if not isinstance(value, str):
            return None
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            return None
        normalized: list[str] = []
        seen: set[str] = set()
        for line in lines:
            candidate = line if line.startswith("- ") else "- {}".format(line.lstrip("- ").strip())
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(candidate)
        return "\n".join(normalized)
