from __future__ import annotations

from pathlib import Path

from app.core.settings import Settings
from app.schemas.pipeline import PipelineInput, ProductData
from app.services.llm_client import LLMClient
from app.services.normalizer import ProductNormalizer


class ProductExtractor:
    def __init__(self, settings: Settings, llm_client: LLMClient, normalizer: ProductNormalizer) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.normalizer = normalizer
        self.prompt_path = self.settings.backend_dir / "app" / "prompts" / "extract_product.md"

    async def extract(self, pipeline_input: PipelineInput) -> ProductData:
        if not pipeline_input.image_path:
            return ProductData(source="unknown", confidence=0.0, barcode=pipeline_input.barcode)

        prompt = Path(self.prompt_path).read_text(encoding="utf-8")
        llm_payload = await self.llm_client.extract_from_image(
            image_path=pipeline_input.image_path,
            prompt=prompt,
            user_notes=pipeline_input.user_query,
        )
        return self.normalizer.normalize_llm_payload(llm_payload, barcode=pipeline_input.barcode)
