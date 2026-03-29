from __future__ import annotations

from pathlib import Path

from app.schemas.pipeline import PreferencesChatRequest, PreferencesChatResponse
from app.services.llm_client import LLMClient
from app.services.preferences_memory import PreferencesMemoryService


class PreferencesChatService:
    def __init__(
        self,
        preferences_memory: PreferencesMemoryService,
        llm_client: LLMClient,
        prompt_path: Path,
    ) -> None:
        self.preferences_memory = preferences_memory
        self.llm_client = llm_client
        self.prompt_template = prompt_path.read_text(encoding="utf-8")

    async def handle_chat(self, request: PreferencesChatRequest) -> PreferencesChatResponse:
        user_id = (request.user_id or "").strip() or "mvp-default-user"
        current_markdown = self.preferences_memory.load_global_preferences(user_id)
        current_memory_document = self.preferences_memory.render_memory_document(user_id)
        user_message = (request.user_message or "").strip()
        if not user_message:
            if current_memory_document and current_memory_document.strip():
                return PreferencesChatResponse(
                    preference_source="memory_markdown",
                    preference_category=PreferencesMemoryService.GLOBAL_CATEGORY,
                    applied_preferences_markdown=current_memory_document.strip(),
                    needs_preference_input=False,
                    assistant_message="Questa e la memoria preferenze salvata al momento. Se vuoi, posso aggiornarla direttamente in chat.",
                )
            return PreferencesChatResponse(
                preference_source="none",
                preference_category=PreferencesMemoryService.GLOBAL_CATEGORY,
                applied_preferences_markdown=None,
                needs_preference_input=True,
                assistant_message=(
                    "Dimmi le tue preferenze generali, intolleranze o vincoli ambientali. "
                    "Per esempio: vegana, no lattosio, no glutine, senza plastica, solo bio."
                ),
            )

        payload = await self.llm_client.run_preferences_chat_turn(
            prompt=self.prompt_template,
            category=PreferencesMemoryService.GLOBAL_CATEGORY,
            user_message=user_message,
            current_preferences_markdown=current_memory_document,
            chat_history=request.chat_history,
        )
        assistant_message = str(payload.get("assistant_message") or "").strip()
        needs_preference_input = bool(payload.get("needs_preference_input"))
        preference_source = "memory_markdown" if current_memory_document and current_memory_document.strip() else "none"

        final_preferences_markdown = self._normalize_markdown(payload.get("final_preferences_markdown"))
        if bool(payload.get("should_update")) and final_preferences_markdown:
            current_markdown = final_preferences_markdown
            self.preferences_memory.upsert_global_preferences(user_id, current_markdown)
            current_memory_document = self.preferences_memory.render_memory_document(user_id)
            preference_source = "user_message_extracted"
            needs_preference_input = False

        if not assistant_message:
            if current_memory_document and current_memory_document.strip():
                assistant_message = "Ho letto la memoria aggiornata delle tue preferenze."
            else:
                assistant_message = "Non ho ancora preferenze salvate. Dimmi quali vuoi impostare."

        return PreferencesChatResponse(
            preference_source=preference_source,
            preference_category=PreferencesMemoryService.GLOBAL_CATEGORY,
            applied_preferences_markdown=current_memory_document.strip() if current_memory_document and current_memory_document.strip() else None,
            needs_preference_input=needs_preference_input,
            assistant_message=assistant_message,
        )

    @staticmethod
    def _normalize_markdown(value: object) -> str | None:
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
