from __future__ import annotations

from pathlib import Path

from app.core.errors import AppError
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
        self._validate_image_path(pipeline_input.image_path)

        prompt = Path(self.prompt_path).read_text(encoding="utf-8")
        llm_payload = await self.llm_client.extract_from_image(
            image_path=pipeline_input.image_path,
            prompt=prompt,
            user_notes=pipeline_input.user_query,
        )
        return self.normalizer.normalize_llm_payload(llm_payload, barcode=pipeline_input.barcode)

    def _validate_image_path(self, image_path: str) -> None:
        candidate = Path(image_path).expanduser()
        if ".." in candidate.parts:
            raise AppError("invalid_image_path", "Image path traversal is not allowed.", details={"image_path": image_path})
        resolved = candidate.resolve(strict=False)
        allowed_roots = self.settings.allowed_image_roots()
        if not any(root == resolved or root in resolved.parents for root in allowed_roots):
            raise AppError(
                "invalid_image_path",
                "Image path is outside the configured allowed roots.",
                details={"allowed_roots": [str(root) for root in allowed_roots]},
            )
        if not resolved.exists():
            raise AppError("image_not_found", "Image path does not exist.", status_code=404, details={"image_path": image_path})
