from __future__ import annotations

from app.schemas.pipeline import ProductData
from app.services.scoring_engine import ScoringEngine


def test_scoring_engine_is_deterministic() -> None:
    engine = ScoringEngine()
    product = ProductData(
        product_name="Crackers",
        ingredients_text="whole wheat flour, olive oil, salt",
        packaging="paper",
        labels_tags=["organic"],
        origins="Italy",
        categories_tags=["en:biscuits"],
        confidence=0.8,
    )

    result_a = engine.compute_score(product)
    result_b = engine.compute_score(product)

    assert result_a.total_score == result_b.total_score
    assert result_a.subscores == result_b.subscores
    assert "plastic_packaging" not in result_a.flags
    assert result_a.rule_triggers


def test_scoring_engine_penalizes_ecological_hotspots() -> None:
    engine = ScoringEngine()
    product = ProductData(
        product_name="Chocolate Biscuits",
        ingredients_text="wheat flour, cocoa, palm oil, cream, sugar",
        eco_ingredient_signals=[
            {"id": "cocoa", "present": True, "impact_level": "medium_high"},
            {"id": "palm_oil", "present": True, "impact_level": "high"},
            {"id": "cream", "present": True, "impact_level": "high"},
        ],
        packaging="plastic bag",
        labels_tags=["en:no-palm-oil"],
        categories_tags=["en:sweet-snacks", "en:biscuits"],
        confidence=0.7,
    )

    result = engine.compute_score(product)

    assert result.total_score >= 0
    assert any(trigger["code"] == "cocoa_hotspot" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "palm_oil" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "high_impact_dairy" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "plastic_packaging" for trigger in result.rule_triggers)


def test_scoring_engine_uses_structured_no_palm_oil_signal_without_ingredients_text() -> None:
    engine = ScoringEngine()
    product = ProductData(
        product_name="Cookies",
        ingredients_text=None,
        eco_ingredient_signals=[
            {"id": "palm_oil", "present": False, "impact_level": "high"},
        ],
        packaging="paper",
        labels_tags=["en:no-palm-oil"],
        categories_tags=["en:biscuits"],
        confidence=0.8,
    )

    result = engine.compute_score(product)

    assert any(trigger["code"] == "no_palm_oil_signal" for trigger in result.rule_triggers)
    assert result.subscores["ingredients"] > 45


def test_scoring_engine_handles_missing_ecology_data_conservatively() -> None:
    engine = ScoringEngine()
    product = ProductData(
        ingredients_text=None,
        origins=None,
        packaging=None,
        categories_tags=[],
        confidence=0.3,
    )

    result = engine.compute_score(product)

    assert result.total_score >= 0
    assert "low_confidence_product_data" in result.flags
    assert any(trigger["code"] == "ingredients_missing" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "origins_missing" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "packaging_missing" for trigger in result.rule_triggers)
    assert any(trigger["code"] == "category_missing" for trigger in result.rule_triggers)
