from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

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

        think_response = await self.llm_client.generate_explanation(
            prompt=think_prompt,
            product_payload=model_to_dict(product),
            score_payload=model_to_dict(score),
            mode="think",
        )

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

        short = fast_response.get("explanation_short") or "No concise explanation could be generated."
        bullets = fast_response.get("why_bullets") or []
        return short, [str(item) for item in bullets]
