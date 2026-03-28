from __future__ import annotations

from app.schemas.pipeline import ProductData, RagSuggestion
from app.services.impact_translator import ImpactTranslator


def test_impact_translator_builds_emissions_comparison() -> None:
    translator = ImpactTranslator()
    comparison = translator.build_impact_comparison(
        ProductData(
            barcode="111",
            product_name="Biscotti Avena",
            quantity="250 g",
            co2e_kg_per_kg=1.73,
            co2e_source="off_agribalyse",
            ecoscore_score=62,
        ),
        [
            RagSuggestion(
                title="Alternativa migliore",
                suggestion="Valuta un biscotto simile con packaging paper.",
                rationale="Eco-Score migliore e meno emissioni.",
                sources=["222"],
                candidate_barcode="222",
                candidate_product_name="Biscotti Avena Integrali",
                candidate_ecoscore_score=78,
                candidate_co2e_kg_per_kg=1.1,
            )
        ],
    )

    assert comparison is not None
    assert comparison.candidate_barcode == "222"
    assert comparison.base_co2e_kg_per_kg == 1.73
    assert comparison.candidate_co2e_kg_per_kg == 1.1
    assert comparison.co2e_delta_kg_per_kg == 0.63
    assert comparison.estimated_co2e_savings_per_pack_kg == 0.158
    assert comparison.impact_equivalents
    assert comparison.impact_equivalents[0].type == "car_km_avoided"


def test_impact_translator_returns_none_without_suggestions() -> None:
    translator = ImpactTranslator()
    comparison = translator.build_impact_comparison(ProductData(product_name="X"), [])
    assert comparison is None
