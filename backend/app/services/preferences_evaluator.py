from __future__ import annotations

from typing import List, Optional, Tuple

from app.schemas.pipeline import RagSuggestion


class PreferencesEvaluator:
    def evaluate(self, suggestion: RagSuggestion, preferences_markdown: Optional[str]) -> tuple[bool, List[str]]:
        if not preferences_markdown or not preferences_markdown.strip():
            return True, []

        warnings: List[str] = []
        normalized_preferences = preferences_markdown.lower()
        candidate_text = self._candidate_text(suggestion)

        for label, tokens in self._avoid_rules():
            if self._mentions_preference(normalized_preferences, label, tokens[0]):
                if any(token in candidate_text for token in tokens):
                    warnings.append("Non in linea con la preferenza '{}'.".format(label))

        if self._mentions_any(normalized_preferences, ("plastic free", "no plastic", "senza plastica", "plastic-free")):
            if "plastic" in (suggestion.candidate_packaging or "").lower() or "plastica" in (suggestion.candidate_packaging or "").lower():
                warnings.append("Packaging non in linea con la preferenza 'senza plastica'.")

        if self._mentions_any(normalized_preferences, ("organic only", "solo bio", "solo biologico", "only organic")):
            labels = {label.lower() for label in suggestion.candidate_labels_tags}
            if not any(token in labels for token in {"organic", "en:organic", "it:biologico", "fr:bio"}):
                warnings.append("Il candidato non espone una label biologica coerente con le preferenze.")

        return len(warnings) == 0, warnings

    @staticmethod
    def _candidate_text(suggestion: RagSuggestion) -> str:
        return " ".join(
            [
                suggestion.candidate_product_name or "",
                suggestion.candidate_ingredients_text or "",
                suggestion.candidate_packaging or "",
                suggestion.candidate_origins or "",
                " ".join(suggestion.candidate_labels_tags),
            ]
        ).lower()

    @staticmethod
    def _mentions_preference(preferences_markdown: str, label: str, fallback_token: str) -> bool:
        if label in preferences_markdown:
            return True
        return fallback_token in preferences_markdown

    @staticmethod
    def _mentions_any(text: str, tokens: tuple[str, ...]) -> bool:
        return any(token in text for token in tokens)

    @staticmethod
    def _avoid_rules() -> List[Tuple[str, tuple[str, ...]]]:
        return [
            ("no latte", ("latte", "milk", "cream", "butter", "panna", "burro")),
            ("no dairy", ("latte", "milk", "cream", "butter", "panna", "burro", "cheese", "formaggio")),
            ("no beef", ("beef", "manzo", "veal", "vitello")),
            ("no pork", ("pork", "maiale", "prosciutto")),
            ("no fish", ("fish", "pesce", "salmone", "tonno")),
            ("no palm oil", ("palm oil", "olio di palma")),
            ("no sugar", ("sugar", "zucchero", "sciroppo di glucosio")),
        ]
