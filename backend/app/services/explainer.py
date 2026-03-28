from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from app.core.observability import truncate_text
from app.core.settings import Settings
from app.product import model_to_dict
from app.schemas.pipeline import ProductData, ScoreResult
from app.services.llm_client import LLMClient


class ScoreExplainer:
    def __init__(self, settings: Settings, llm_client: LLMClient) -> None:
        self.settings = settings
        self.llm_client = llm_client

    async def explain(self, product: ProductData, score: ScoreResult, deep_mode: bool) -> Tuple[str, List[str]]:
        think_prompt = (self.settings.backend_dir / "app" / "prompts" / "explain_score_think.md").read_text(
            encoding="utf-8"
        )
        fast_prompt = (self.settings.backend_dir / "app" / "prompts" / "explain_score_fast.md").read_text(
            encoding="utf-8"
        )

        think_response = {}
        try:
            think_response = await self.llm_client.generate_explanation(
                prompt=think_prompt,
                product_payload=model_to_dict(product),
                score_payload=model_to_dict(score),
                mode="think",
            )
        except Exception:
            think_response = {}

        try:
            fast_response = await self.llm_client.generate_explanation(
                prompt=fast_prompt,
                product_payload={
                    "product": model_to_dict(product),
                    "score": model_to_dict(score),
                    "draft": think_response,
                    "depth": "deep" if deep_mode else "fast",
                },
                score_payload=model_to_dict(score),
                mode="no_think",
            )
        except Exception:
            fast_response = {}

        short = fast_response.get("explanation_short") or self._fallback_short(score)
        bullets = self._structured_bullets(think_response, fast_response)
        return truncate_text(short, self.settings.explanation_short_max_chars), bullets

    def _structured_bullets(self, think_response: dict, fast_response: dict) -> List[str]:
        facts = [str(item) for item in (think_response.get("facts") or []) if str(item).strip()]
        assumptions = [str(item) for item in (think_response.get("assumptions") or []) if str(item).strip()]
        advice = [str(item) for item in (think_response.get("actionable_advice") or think_response.get("advice_candidates") or []) if str(item).strip()]

        if not facts and not assumptions and not advice:
            raw_bullets = [str(item) for item in (fast_response.get("why_bullets") or []) if str(item).strip()]
            facts = raw_bullets[:1]
            assumptions = raw_bullets[1:2]
            advice = raw_bullets[2:3]

        sections = [
            "Observed facts: {}".format(truncate_text("; ".join(facts) or "Available product data is limited.", self.settings.explanation_bullet_max_chars)),
            "Assumptions: {}".format(truncate_text("; ".join(assumptions) or "Some product details may be incomplete or inferred.", self.settings.explanation_bullet_max_chars)),
            "Actionable advice: {}".format(truncate_text("; ".join(advice) or "Compare similar products and prefer options with clearer ingredient and nutrition data.", self.settings.explanation_bullet_max_chars)),
        ]
        return sections

    @staticmethod
    def _fallback_short(score: ScoreResult) -> str:
        return "Deterministic score: {} out of 100. Generated explanation is temporarily unavailable.".format(score.total_score)
