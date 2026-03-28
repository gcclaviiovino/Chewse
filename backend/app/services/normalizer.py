from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.pipeline import ProductData


class ProductNormalizer:
    def normalize_off_payload(self, payload: Optional[Dict[str, Any]], barcode: Optional[str] = None) -> ProductData:
        product, _warnings = self.normalize_off_payload_with_warnings(payload, barcode=barcode)
        return product

    def normalize_off_payload_with_warnings(
        self, payload: Optional[Dict[str, Any]], barcode: Optional[str] = None
    ) -> Tuple[ProductData, List[str]]:
        warnings: List[str] = []
        payload_dict = payload if isinstance(payload, dict) else {}
        if payload is not None and not isinstance(payload, dict):
            warnings.append("off_payload_not_object")

        raw_product = payload_dict.get("product", payload_dict)
        if not isinstance(raw_product, dict):
            warnings.append("off_product_not_object")
            raw_product = {}

        nutriments = raw_product.get("nutriments")
        if nutriments is None:
            normalized_nutriments: Dict[str, Optional[Any]] = {}
        elif isinstance(nutriments, dict):
            normalized_nutriments = self._normalize_nutriments(nutriments)
        else:
            warnings.append("off_nutriments_not_object")
            normalized_nutriments = {}

        product_name = self._pick_string(raw_product, ("product_name", "generic_name"), warnings, "off_name_invalid")
        brand = self._stringify_joined(raw_product.get("brands"), warnings, "off_brands_invalid")
        normalized_barcode = self._normalize_barcode(barcode or raw_product.get("code"), warnings)
        ingredients_text = self._coerce_string(raw_product.get("ingredients_text"), warnings, "off_ingredients_invalid")
        packaging = self._stringify_joined(raw_product.get("packaging"), warnings, "off_packaging_invalid")
        origins = self._coerce_string(raw_product.get("origins"), warnings, "off_origins_invalid")
        labels_tags = self._as_list(raw_product.get("labels_tags"), warnings, "off_labels_invalid")
        categories_tags = self._as_list(raw_product.get("categories_tags"), warnings, "off_categories_invalid")
        quantity = self._coerce_string(raw_product.get("quantity"), warnings, "off_quantity_invalid")
        ecoscore_data = raw_product.get("ecoscore_data") if isinstance(raw_product.get("ecoscore_data"), dict) else {}
        ecoscore_score = self._coerce_int(raw_product.get("ecoscore_score"))
        if ecoscore_score is None:
            ecoscore_score = self._coerce_int(ecoscore_data.get("score"))
        ecoscore_grade = self._coerce_string(raw_product.get("ecoscore_grade")) or self._coerce_string(ecoscore_data.get("grade"))
        co2e_kg_per_kg = self._extract_co2e_kg_per_kg(ecoscore_data)

        confidence = self._compute_off_confidence(
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            nutriments=normalized_nutriments,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
        )
        field_provenance = self._build_field_provenance(
            source="openfoodfacts",
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
            ecoscore_score=ecoscore_score,
            ecoscore_grade=ecoscore_grade,
            co2e_kg_per_kg=co2e_kg_per_kg,
        )
        data_completeness = self._build_data_completeness(
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
            ecoscore_score=ecoscore_score,
            ecoscore_grade=ecoscore_grade,
            co2e_kg_per_kg=co2e_kg_per_kg,
        )

        return (
            ProductData(
                product_name=product_name,
                brand=brand,
                barcode=normalized_barcode,
                ingredients_text=ingredients_text,
                eco_ingredient_signals=self._extract_eco_ingredient_signals(
                    ingredients_text=ingredients_text,
                    labels_tags=labels_tags,
                ),
                ecoscore_score=ecoscore_score,
                ecoscore_grade=ecoscore_grade,
                ecoscore_data=ecoscore_data,
                co2e_kg_per_kg=co2e_kg_per_kg,
                co2e_source="off_agribalyse" if co2e_kg_per_kg is not None else None,
                field_provenance=field_provenance,
                data_completeness=data_completeness,
                nutriments=normalized_nutriments,
                packaging=packaging,
                origins=origins,
                labels_tags=labels_tags,
                categories_tags=categories_tags,
                quantity=quantity,
                source="openfoodfacts",
                confidence=confidence,
            ),
            warnings,
        )

    def normalize_llm_payload(self, payload: Optional[Dict[str, Any]], barcode: Optional[str] = None) -> ProductData:
        payload = payload or {}
        warnings: List[str] = []
        normalized_nutriments = self._normalize_nutriments(payload.get("nutriments") or {})
        normalized_nutriments = {
            key: value for key, value in normalized_nutriments.items() if value is not None
        }
        product_name = self._coerce_string(payload.get("product_name"))
        brand = self._coerce_string(payload.get("brand"))
        ingredients_text = self._coerce_string(payload.get("ingredients_text"))
        packaging = self._coerce_string(payload.get("packaging"))
        origins = self._coerce_string(payload.get("origins"))
        labels_tags = self._as_list(payload.get("labels_tags"))
        categories_tags = self._as_list(payload.get("categories_tags"))
        quantity = self._coerce_string(payload.get("quantity"))
        normalized_barcode = self._normalize_barcode(barcode or payload.get("barcode"), warnings)
        field_provenance = self._build_field_provenance(
            source="image_llm",
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
            ecoscore_score=None,
            ecoscore_grade=None,
            co2e_kg_per_kg=None,
        )
        data_completeness = self._build_data_completeness(
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
            ecoscore_score=None,
            ecoscore_grade=None,
            co2e_kg_per_kg=None,
        )
        return ProductData(
            product_name=product_name,
            brand=brand,
            barcode=normalized_barcode,
            ingredients_text=ingredients_text,
            eco_ingredient_signals=self._extract_eco_ingredient_signals(
                ingredients_text=ingredients_text,
                labels_tags=labels_tags,
            ),
            nutriments=normalized_nutriments,
            field_provenance=field_provenance,
            data_completeness=data_completeness,
            packaging=packaging,
            origins=origins,
            labels_tags=labels_tags,
            categories_tags=categories_tags,
            quantity=quantity,
            source="image_llm" if payload else "unknown",
            confidence=float(payload.get("confidence", 0.35 if payload else 0.0)),
        )

    @staticmethod
    def _normalize_nutriments(nutriments: Dict[str, Any]) -> Dict[str, Optional[Any]]:
        normalized: Dict[str, Optional[Any]] = {}
        for key, value in nutriments.items():
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            if isinstance(value, (int, float)) or value is None:
                normalized[normalized_key] = value
                continue
            if isinstance(value, str):
                try:
                    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
                    normalized[normalized_key] = float(match.group(0).replace(",", ".")) if match else value.strip()
                except ValueError:
                    normalized[normalized_key] = value.strip()
                continue
            normalized[normalized_key] = str(value)
        return normalized

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(round(value))
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
            if not match:
                return None
            try:
                return int(round(float(match.group(0).replace(",", "."))))
            except ValueError:
                return None
        return None

    @staticmethod
    def _pick_string(raw_product: Dict[str, Any], keys: tuple[str, ...], warnings: List[str], warning_code: str) -> Optional[str]:
        for key in keys:
            value = raw_product.get(key)
            normalized = ProductNormalizer._coerce_string(value, warnings, warning_code)
            if normalized:
                return normalized
        return None

    @staticmethod
    def _normalize_barcode(value: Any, warnings: List[str]) -> Optional[str]:
        normalized = ProductNormalizer._coerce_string(value, warnings, "off_barcode_invalid")
        if normalized is None:
            return None
        digits_only = re.sub(r"\s+", "", normalized)
        return digits_only or None

    @staticmethod
    def _coerce_string(value: Any, warnings: Optional[List[str]] = None, warning_code: Optional[str] = None) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, (int, float)):
            return str(value)
        if warnings is not None and warning_code:
            warnings.append(warning_code)
        return None

    @staticmethod
    def _stringify_joined(value: Any, warnings: List[str], warning_code: str) -> Optional[str]:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, list):
            parts = [str(item).strip() for item in value if str(item).strip()]
            return ", ".join(parts) if parts else None
        if value is None:
            return None
        warnings.append(warning_code)
        return str(value).strip() or None

    @staticmethod
    def _as_list(value: Any, warnings: Optional[List[str]] = None, warning_code: Optional[str] = None) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if warnings is not None and warning_code:
            warnings.append(warning_code)
        coerced = str(value).strip()
        return [coerced] if coerced else []

    @staticmethod
    def _compute_off_confidence(
        *,
        product_name: Optional[str],
        brand: Optional[str],
        barcode: Optional[str],
        ingredients_text: Optional[str],
        nutriments: Dict[str, Optional[Any]],
        packaging: Optional[str],
        origins: Optional[str],
        labels_tags: List[str],
        categories_tags: List[str],
        quantity: Optional[str],
    ) -> float:
        completeness_signals = [
            bool(product_name),
            bool(brand),
            bool(barcode),
            bool(ingredients_text),
            bool(nutriments),
            bool(packaging),
            bool(origins),
            bool(labels_tags),
            bool(categories_tags),
            bool(quantity),
        ]
        score = sum(1 for item in completeness_signals if item) / len(completeness_signals)
        return round(0.2 + (0.75 * score), 3) if any(completeness_signals) else 0.0

    @staticmethod
    def _extract_eco_ingredient_signals(ingredients_text: Optional[str], labels_tags: List[str]) -> List[Dict[str, Any]]:
        signals: List[Dict[str, Any]] = []
        normalized = (ingredients_text or "").lower()
        signal_defs = [
            ("beef", ("beef", "veal"), "high", True),
            ("lamb", ("lamb",), "high", True),
            ("milk", ("milk", "latte"), "medium_high", True),
            ("cream", ("cream", "panna"), "high", True),
            ("butter", ("butter", "burro"), "high", True),
            ("cheese", ("cheese", "formaggio"), "high", True),
            ("cocoa", ("cocoa", "cacao"), "medium_high", True),
            ("coffee", ("coffee", "caffe"), "medium_high", True),
            ("palm_oil", ("palm oil", "olio di palma", "palm"), "high", True),
            ("rice", ("rice", "riso"), "medium", True),
            ("almonds", ("almond", "mandor"), "medium", True),
            ("fish", ("fish", "pesce", "salmone", "tonno"), "medium_high", True),
            ("soy", ("soy", "soia"), "medium", True),
        ]

        for signal_id, tokens, impact_level, present_value in signal_defs:
            if not normalized:
                continue
            if any(token in normalized for token in tokens):
                signals.append(
                    {
                        "id": signal_id,
                        "label": signal_id.replace("_", " "),
                        "present": present_value,
                        "impact_level": impact_level,
                        "source": "ingredients_text",
                    }
                )

        normalized_labels = [tag.lower() for tag in labels_tags]
        if any("no-palm-oil" in tag for tag in normalized_labels) and not any(item["id"] == "palm_oil" for item in signals):
            signals.append(
                {
                    "id": "palm_oil",
                    "label": "palm oil",
                    "present": False,
                    "impact_level": "high",
                    "source": "labels_tags",
                }
            )
        return signals

    @staticmethod
    def _extract_co2e_kg_per_kg(ecoscore_data: Dict[str, Any]) -> Optional[float]:
        agribalyse = ecoscore_data.get("agribalyse")
        if not isinstance(agribalyse, dict):
            return None
        co2_total = agribalyse.get("co2_total")
        if isinstance(co2_total, (int, float)):
            return float(co2_total)
        if isinstance(co2_total, str):
            match = re.search(r"[-+]?\d+(?:[.,]\d+)?", co2_total)
            if not match:
                return None
            try:
                return float(match.group(0).replace(",", "."))
            except ValueError:
                return None
        return None

    @staticmethod
    def _build_field_provenance(
        *,
        source: str,
        product_name: Optional[str],
        brand: Optional[str],
        barcode: Optional[str],
        ingredients_text: Optional[str],
        packaging: Optional[str],
        origins: Optional[str],
        labels_tags: List[str],
        categories_tags: List[str],
        quantity: Optional[str],
        ecoscore_score: Optional[int],
        ecoscore_grade: Optional[str],
        co2e_kg_per_kg: Optional[float],
    ) -> Dict[str, Dict[str, Any]]:
        fields = {
            "product_name": product_name,
            "brand": brand,
            "barcode": barcode,
            "ingredients_text": ingredients_text,
            "packaging": packaging,
            "origins": origins,
            "labels_tags": labels_tags,
            "categories_tags": categories_tags,
            "quantity": quantity,
            "ecoscore_score": ecoscore_score,
            "ecoscore_grade": ecoscore_grade,
            "co2e_kg_per_kg": co2e_kg_per_kg,
        }
        provenance: Dict[str, Dict[str, Any]] = {}
        for field_name, value in fields.items():
            if value in (None, "", [], {}):
                continue
            provenance[field_name] = {"source": source}
        return provenance

    @staticmethod
    def _build_data_completeness(
        *,
        product_name: Optional[str],
        brand: Optional[str],
        barcode: Optional[str],
        ingredients_text: Optional[str],
        packaging: Optional[str],
        origins: Optional[str],
        labels_tags: List[str],
        categories_tags: List[str],
        quantity: Optional[str],
        ecoscore_score: Optional[int],
        ecoscore_grade: Optional[str],
        co2e_kg_per_kg: Optional[float],
    ) -> Dict[str, bool]:
        return {
            "product_name": bool(product_name),
            "brand": bool(brand),
            "barcode": bool(barcode),
            "ingredients_text": bool(ingredients_text),
            "packaging": bool(packaging),
            "origins": bool(origins),
            "labels_tags": bool(labels_tags),
            "categories_tags": bool(categories_tags),
            "quantity": bool(quantity),
            "ecoscore_score": ecoscore_score is not None,
            "ecoscore_grade": bool(ecoscore_grade),
            "co2e_kg_per_kg": co2e_kg_per_kg is not None,
        }
