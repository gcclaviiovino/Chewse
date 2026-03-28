from __future__ import annotations

from app.product import merge_product_data
from app.services.normalizer import ProductNormalizer


def test_normalizer_handles_sparse_off_payload() -> None:
    normalizer = ProductNormalizer()
    product = normalizer.normalize_off_payload({"product": {"product_name": "Acqua"}}, barcode="111")

    assert product.product_name == "Acqua"
    assert product.barcode == "111"
    assert product.nutriments == {}
    assert product.labels_tags == []
    assert product.source == "openfoodfacts"


def test_normalizer_handles_dirty_off_payload_with_warnings() -> None:
    normalizer = ProductNormalizer()

    product, warnings = normalizer.normalize_off_payload_with_warnings(
        {
            "status": 1,
            "product": {
                "product_name": ["Wrong", "Shape"],
                "brands": ["Brand A", "Brand B"],
                "ingredients_text": {"text": "water"},
                "nutriments": {"energy-kcal_100g": "45 kcal", "salt_100g": ["0.3"]},
                "packaging": ["bottle", "cap"],
                "origins": 123,
                "labels_tags": "organic, fair-trade",
                "categories_tags": None,
                "quantity": {"value": "1L"},
            },
        },
        barcode="222",
    )

    assert product.product_name is None
    assert product.brand == "Brand A, Brand B"
    assert product.barcode == "222"
    assert product.nutriments["energy-kcal_100g"] == 45.0
    assert product.nutriments["salt_100g"] == "['0.3']"
    assert product.packaging == "bottle, cap"
    assert product.origins == "123"
    assert product.labels_tags == ["organic", "fair-trade"]
    assert product.categories_tags == []
    assert product.source == "openfoodfacts"
    assert product.confidence > 0
    assert "off_name_invalid" in warnings
    assert "off_ingredients_invalid" in warnings
    assert "off_quantity_invalid" in warnings


def test_normalize_llm_payload_drops_null_nutriments_before_merge() -> None:
    normalizer = ProductNormalizer()

    image_product = normalizer.normalize_llm_payload(
        {
            "product_name": "Detected",
            "nutriments": {
                "fat_100g": None,
                "sugars_100g": None,
            },
        },
        barcode="333",
    )
    off_product = normalizer.normalize_off_payload(
        {
            "status": 1,
            "product": {
                "code": "333",
                "nutriments": {
                    "fat_100g": 23,
                    "sugars_100g": 21,
                },
            },
        },
        barcode="333",
    )

    merged = merge_product_data(image_product, off_product)

    assert "fat_100g" not in image_product.nutriments
    assert "sugars_100g" not in image_product.nutriments
    assert merged.nutriments["fat_100g"] == 23
    assert merged.nutriments["sugars_100g"] == 21


def test_normalizer_extracts_structured_eco_ingredient_signals() -> None:
    normalizer = ProductNormalizer()

    product = normalizer.normalize_off_payload(
        {
            "status": 1,
            "product": {
                "code": "444",
                "ingredients_text": "farina di frumento, cacao, panna, zucchero",
                "labels_tags": ["en:no-palm-oil"],
            },
        },
        barcode="444",
    )

    signal_ids = {item["id"] for item in product.eco_ingredient_signals}

    assert "cocoa" in signal_ids
    assert "cream" in signal_ids
    assert "palm_oil" in signal_ids
    palm_signal = next(item for item in product.eco_ingredient_signals if item["id"] == "palm_oil")
    assert palm_signal["present"] is False


def test_normalizer_maps_off_ecoscore_and_emissions() -> None:
    normalizer = ProductNormalizer()

    product = normalizer.normalize_off_payload(
        {
            "status": 1,
            "product": {
                "code": "555",
                "product_name": "Eco Product",
                "ecoscore_score": 58,
                "ecoscore_grade": "c",
                "ecoscore_data": {
                    "score": 58,
                    "grade": "c",
                    "agribalyse": {"co2_total": 2.34},
                },
            },
        },
        barcode="555",
    )

    assert product.ecoscore_score == 58
    assert product.ecoscore_grade == "c"
    assert product.ecoscore_data["score"] == 58
    assert product.co2e_kg_per_kg == 2.34
    assert product.co2e_source == "off_agribalyse"
    assert product.field_provenance["ecoscore_score"]["source"] == "openfoodfacts"
    assert product.field_provenance["co2e_kg_per_kg"]["source"] == "openfoodfacts"
    assert product.data_completeness["ecoscore_score"] is True
    assert product.data_completeness["ingredients_text"] is False
