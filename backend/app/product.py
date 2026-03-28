from __future__ import annotations

from typing import Dict, Optional

from app.schemas.pipeline import ProductData


def model_to_dict(model: object) -> Dict[str, object]:
    if hasattr(model, "model_dump"):
        return getattr(model, "model_dump")()
    return getattr(model, "dict")()


def merge_product_data(primary: ProductData, secondary: Optional[ProductData]) -> ProductData:
    if secondary is None:
        return primary

    merged_payload: Dict[str, object] = model_to_dict(primary)
    secondary_payload = model_to_dict(secondary)

    for field_name, value in secondary_payload.items():
        current = merged_payload.get(field_name)
        if field_name == "nutriments":
            merged_nutriments = dict(value or {})
            merged_nutriments.update(current or {})
            merged_payload[field_name] = merged_nutriments
            continue
        if field_name == "eco_ingredient_signals":
            merged_signals = _merge_eco_signals(current or [], value or [])
            merged_payload[field_name] = merged_signals
            continue
        if field_name == "field_provenance":
            merged_payload[field_name] = _merge_field_provenance(current or {}, value or {})
            continue
        if field_name == "data_completeness":
            merged_payload[field_name] = _merge_data_completeness(current or {}, value or {})
            continue
        if field_name in {"labels_tags", "categories_tags"}:
            merged_payload[field_name] = sorted(set((current or []) + (value or [])))
            continue
        if not current and value:
            merged_payload[field_name] = value

    if primary.source != secondary.source and secondary.source != "unknown":
        merged_payload["source"] = "hybrid"
    merged_payload["confidence"] = round(max(primary.confidence, secondary.confidence), 3)
    return ProductData(**merged_payload)


def _merge_eco_signals(primary: list[dict], secondary: list[dict]) -> list[dict]:
    merged: Dict[str, dict] = {}
    for item in secondary + primary:
        if not isinstance(item, dict):
            continue
        signal_id = str(item.get("id") or item.get("label") or "").strip()
        if not signal_id:
            continue
        merged[signal_id] = dict(item)
    return list(merged.values())


def _merge_field_provenance(primary: dict, secondary: dict) -> dict:
    merged = dict(secondary)
    merged.update(primary)
    return merged


def _merge_data_completeness(primary: dict, secondary: dict) -> dict:
    merged = dict(secondary)
    for key, value in primary.items():
        merged[key] = bool(value) or bool(merged.get(key))
    return merged
