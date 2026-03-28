from __future__ import annotations

from app.schemas.pipeline import ProductData
from app.services.scoring_engine import ScoringEngine


def test_scoring_engine_is_deterministic() -> None:
    engine = ScoringEngine()
    product = ProductData(
        product_name="Crackers",
        ingredients_text="whole wheat flour, olive oil, salt",
        nutriments={"sugars_100g": 2.0, "salt_100g": 0.2, "fiber_100g": 4.5},
        packaging="paper",
        labels_tags=["organic"],
        origins="Italy",
        confidence=0.8,
    )

    result_a = engine.compute_score(product)
    result_b = engine.compute_score(product)

    assert result_a.total_score == result_b.total_score
    assert result_a.subscores == result_b.subscores
    assert "high_sugar" not in result_a.flags
    assert result_a.rule_triggers


def test_scoring_engine_handles_unknown_units_robustly() -> None:
    engine = ScoringEngine()
    product = ProductData(
        nutriments={"sugars_100g": "12 g", "salt_100g": "unknown"},
        ingredients_text=None,
        confidence=0.5,
    )

    result = engine.compute_score(product)

    assert result.total_score >= 0
    assert any(trigger["code"] == "ingredients_missing" for trigger in result.rule_triggers)
