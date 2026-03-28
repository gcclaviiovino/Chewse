from __future__ import annotations

from app.services.normalizer import ProductNormalizer


def test_normalizer_handles_sparse_off_payload() -> None:
    normalizer = ProductNormalizer()
    product = normalizer.normalize_off_payload({"product": {"product_name": "Acqua"}}, barcode="111")

    assert product.product_name == "Acqua"
    assert product.barcode == "111"
    assert product.nutriments == {}
    assert product.labels_tags == []
    assert product.source == "openfoodfacts"
