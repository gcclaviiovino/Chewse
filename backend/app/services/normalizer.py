from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.schemas.pipeline import ProductData


class ProductNormalizer:
    def normalize_off_payload(self, payload: Optional[Dict[str, Any]], barcode: Optional[str] = None) -> ProductData:
        product = (payload or {}).get("product", payload or {})
        nutriments = product.get("nutriments") or {}
        return ProductData(
            product_name=product.get("product_name") or product.get("generic_name"),
            brand=product.get("brands"),
            barcode=barcode or product.get("code"),
            ingredients_text=product.get("ingredients_text"),
            nutriments=self._normalize_nutriments(nutriments),
            packaging=product.get("packaging"),
            origins=product.get("origins"),
            labels_tags=self._as_list(product.get("labels_tags")),
            categories_tags=self._as_list(product.get("categories_tags")),
            quantity=product.get("quantity"),
            source="openfoodfacts" if product else "unknown",
            confidence=0.85 if product else 0.1,
        )

    def normalize_llm_payload(self, payload: Optional[Dict[str, Any]], barcode: Optional[str] = None) -> ProductData:
        payload = payload or {}
        return ProductData(
            product_name=payload.get("product_name"),
            brand=payload.get("brand"),
            barcode=barcode or payload.get("barcode"),
            ingredients_text=payload.get("ingredients_text"),
            nutriments=self._normalize_nutriments(payload.get("nutriments") or {}),
            packaging=payload.get("packaging"),
            origins=payload.get("origins"),
            labels_tags=self._as_list(payload.get("labels_tags")),
            categories_tags=self._as_list(payload.get("categories_tags")),
            quantity=payload.get("quantity"),
            source="image_llm" if payload else "unknown",
            confidence=float(payload.get("confidence", 0.35 if payload else 0.0)),
        )

    @staticmethod
    def _normalize_nutriments(nutriments: Dict[str, Any]) -> Dict[str, Optional[Any]]:
        normalized: Dict[str, Optional[Any]] = {}
        for key, value in nutriments.items():
            if isinstance(value, (int, float)) or value is None:
                normalized[key] = value
                continue
            if isinstance(value, str):
                try:
                    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
                    normalized[key] = float(match.group(0).replace(",", ".")) if match else value.strip()
                except ValueError:
                    normalized[key] = value.strip()
                continue
            normalized[key] = str(value)
        return normalized

    @staticmethod
    def _as_list(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(value)]
