from __future__ import annotations

from pathlib import Path

from app.schemas.pipeline import PreferencesChatRequest, PreferencesChatResponse
from app.services.category_normalizer import aliases_for_category
from app.services.llm_client import LLMClient
from app.services.preferences_memory import PreferencesMemoryService

_ITALIAN_CATEGORY_HINTS = {
    "biscuits": {"biscotti", "biscotto", "cookie", "cookies"},
    "breakfasts": {"colazione", "colazioni", "breakfast"},
    "spreads": {"crema", "creme", "spalmabile", "spalmabili"},
    "snacks": {"snack", "spuntino", "spuntini", "cracker", "crackers"},
    "desserts": {"dolce", "dolci", "dessert"},
    "cereals": {"cereali", "cereale"},
    "fruits": {"frutta", "frutto", "frutti"},
    "vegetables": {"verdura", "verdure", "vegetale", "vegetali"},
    "legumes": {"legumi", "legume"},
    "dairy": {"latticini", "latticino"},
    "fish": {"pesce", "pesci"},
    "meat": {"carne"},
    "bread": {"pane"},
    "pasta": {"pasta"},
}


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
        current_sections = self.preferences_memory.load_all_preferences(user_id)
        current_memory_document = self.preferences_memory.render_memory_document(user_id)
        user_message = (request.user_message or "").strip()

        if not user_message:
            if current_memory_document and current_memory_document.strip():
                return PreferencesChatResponse(
                    preference_source="memory_markdown",
                    preference_category=None,
                    applied_preferences_markdown=current_memory_document.strip(),
                    needs_preference_input=False,
                    assistant_message="Questa e la memoria preferenze salvata al momento. Se vuoi, posso aggiornarla direttamente in chat.",
                )
            return PreferencesChatResponse(
                preference_source="none",
                preference_category=None,
                applied_preferences_markdown=None,
                needs_preference_input=True,
                assistant_message=(
                    "Dimmi le tue preferenze e, se possibile, per quale categoria valgono. "
                    "Per esempio: per i biscotti no lattosio, per le creme niente olio di palma."
                ),
            )

        payload = await self.llm_client.run_preferences_chat_turn(
            prompt=self.prompt_template,
            category="full_memory_document",
            user_message=user_message,
            current_preferences_markdown=current_memory_document,
            chat_history=request.chat_history,
        )
        assistant_message = str(payload.get("assistant_message") or "").strip()
        needs_preference_input = bool(payload.get("needs_preference_input"))
        preference_source = "memory_markdown" if current_memory_document and current_memory_document.strip() else "none"

        final_memory_document = self._normalize_memory_document(payload.get("final_preferences_markdown"))
        if bool(payload.get("should_update")) and final_memory_document:
            if self._has_clear_category_reference(user_message, current_sections):
                self.preferences_memory.replace_memory_document(user_id, final_memory_document)
                current_memory_document = self.preferences_memory.render_memory_document(user_id)
                preference_source = "user_message_extracted"
                needs_preference_input = False
            else:
                assistant_message = (
                    "Per aggiornare la memoria devo sapere a quale categoria ti riferisci. "
                    "Per esempio: per i biscotti, per la colazione, per le creme."
                )
                needs_preference_input = False

        if not assistant_message:
            if current_memory_document and current_memory_document.strip():
                assistant_message = "Ho letto la memoria aggiornata delle tue preferenze."
            else:
                assistant_message = "Non ho ancora preferenze salvate. Dimmi quali vuoi impostare."

        return PreferencesChatResponse(
            preference_source=preference_source,
            preference_category=None,
            applied_preferences_markdown=current_memory_document.strip() if current_memory_document and current_memory_document.strip() else None,
            needs_preference_input=needs_preference_input,
            assistant_message=assistant_message,
        )

    @staticmethod
    def _normalize_memory_document(value: object) -> str | None:
        if not isinstance(value, str):
            return None
        rendered = "\n".join(line.rstrip() for line in value.splitlines()).strip()
        return rendered or None

    @staticmethod
    def _has_clear_category_reference(user_message: str, sections: dict[str, str]) -> bool:
        normalized = (user_message or "").strip().lower()
        if not normalized:
            return False
        for category in sections.keys():
            aliases = set(aliases_for_category(category) or [category])
            aliases.update(_ITALIAN_CATEGORY_HINTS.get(category, set()))
            for alias in aliases:
                if alias and alias in normalized:
                    return True
        return False
