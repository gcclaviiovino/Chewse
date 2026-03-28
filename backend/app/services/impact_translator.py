from __future__ import annotations

import re
from typing import Optional

from app.schemas.pipeline import ImpactComparison, ImpactEquivalent, ProductData, RagSuggestion


class ImpactTranslator:
    _CAR_KG_CO2E_PER_KM = 0.19

    def build_impact_comparison(
        self,
        product: ProductData,
        suggestions: list[RagSuggestion],
    ) -> Optional[ImpactComparison]:
        if not suggestions:
            return None

        best = suggestions[0]
        base_co2e = product.co2e_kg_per_kg
        candidate_co2e = best.candidate_co2e_kg_per_kg
        co2e_delta = None
        if base_co2e is not None and candidate_co2e is not None:
            co2e_delta = round(base_co2e - candidate_co2e, 3)

        estimated_savings = self._estimated_pack_savings(product.quantity, co2e_delta)
        summary = self._build_summary(product, best, co2e_delta, estimated_savings)
        equivalents = self._build_equivalents(co2e_delta, estimated_savings, product, best)

        confidence = [
            co2e_delta is not None,
            best.candidate_ecoscore_score is not None,
            bool(best.candidate_product_name),
            estimated_savings is not None,
        ]
        comparison_confidence = round(sum(1 for item in confidence if item) / len(confidence), 3)

        return ImpactComparison(
            base_product_barcode=product.barcode,
            base_product_name=product.product_name,
            candidate_barcode=best.candidate_barcode,
            candidate_product_name=best.candidate_product_name,
            base_co2e_kg_per_kg=base_co2e,
            candidate_co2e_kg_per_kg=candidate_co2e,
            co2e_delta_kg_per_kg=co2e_delta,
            estimated_co2e_savings_per_pack_kg=estimated_savings,
            emissions_source=product.co2e_source or "comparison_estimate",
            improvement_summary=summary,
            impact_equivalents=equivalents,
            comparison_confidence=comparison_confidence,
        )

    def _build_summary(
        self,
        product: ProductData,
        suggestion: RagSuggestion,
        co2e_delta: Optional[float],
        estimated_savings: Optional[float],
    ) -> list[str]:
        summary: list[str] = []
        if suggestion.candidate_ecoscore_score is not None and product.ecoscore_score is not None:
            score_delta = suggestion.candidate_ecoscore_score - product.ecoscore_score
            if score_delta > 0:
                summary.append("L'alternativa proposta migliora l'Eco-Score di {} punti.".format(score_delta))
        if co2e_delta is not None and co2e_delta > 0:
            summary.append("Le emissioni stimate scendono di {} kg CO2e per kg di prodotto.".format(self._format_decimal(co2e_delta)))
        if estimated_savings is not None and estimated_savings > 0:
            summary.append("Su una confezione comparabile il risparmio stimato e di {} kg CO2e.".format(self._format_decimal(estimated_savings)))
        if self._is_less_plastic(product.packaging, suggestion.suggestion, suggestion.candidate_product_name):
            summary.append("La proposta sembra anche ridurre il peso ambientale del packaging.")
        if not summary:
            summary.append("L'alternativa selezionata ha dati ambientali migliori o piu completi rispetto al prodotto di partenza.")
        return summary

    def _build_equivalents(
        self,
        co2e_delta: Optional[float],
        estimated_savings: Optional[float],
        product: ProductData,
        suggestion: RagSuggestion,
    ) -> list[ImpactEquivalent]:
        equivalents: list[ImpactEquivalent] = []
        if estimated_savings is not None and estimated_savings > 0:
            km_avoided = round(estimated_savings / self._CAR_KG_CO2E_PER_KM, 2)
            equivalents.append(
                ImpactEquivalent(
                    type="car_km_avoided",
                    label="Equivale a circa {} km in auto evitati per confezione comparabile.".format(self._format_decimal(km_avoided)),
                    value=km_avoided,
                    unit="km",
                    confidence="medium",
                )
            )
        elif co2e_delta is not None and co2e_delta > 0:
            km_avoided = round(co2e_delta / self._CAR_KG_CO2E_PER_KM, 2)
            equivalents.append(
                ImpactEquivalent(
                    type="car_km_avoided_per_kg",
                    label="Equivale a circa {} km in auto evitati per kg di prodotto.".format(self._format_decimal(km_avoided)),
                    value=km_avoided,
                    unit="km/kg",
                    confidence="low",
                )
            )

        if self._packaging_switch_away_from_plastic(product.packaging, suggestion):
            equivalents.append(
                ImpactEquivalent(
                    type="plastic_packaging_reduction",
                    label="Il confronto suggerisce un passaggio da packaging con plastica a una soluzione meno dipendente dalla plastica.",
                    confidence="low",
                )
            )
        return equivalents

    @staticmethod
    def _estimated_pack_savings(quantity: Optional[str], co2e_delta: Optional[float]) -> Optional[float]:
        if co2e_delta is None:
            return None
        parsed = ImpactTranslator._parse_quantity(quantity)
        if not parsed or parsed["unit"] not in {"g", "ml"}:
            return None
        kilograms = parsed["value"] / 1000.0
        return round(max(co2e_delta, 0.0) * kilograms, 3)

    @staticmethod
    def _parse_quantity(value: Optional[str]) -> Optional[dict]:
        if not value:
            return None
        match = re.search(r"(\d+(?:[\.,]\d+)?)\s*(kg|g|ml|l)", value.lower())
        if not match:
            return None
        numeric = float(match.group(1).replace(",", "."))
        unit = match.group(2)
        if unit == "kg":
            numeric *= 1000.0
            unit = "g"
        elif unit == "l":
            numeric *= 1000.0
            unit = "ml"
        return {"value": numeric, "unit": unit}

    @staticmethod
    def _format_decimal(value: float) -> str:
        normalized = "{:.2f}".format(value).rstrip("0").rstrip(".")
        return normalized.replace(".", ",")

    @staticmethod
    def _is_less_plastic(base_packaging: Optional[str], suggestion_text: str, candidate_name: Optional[str]) -> bool:
        base = (base_packaging or "").lower()
        text = "{} {}".format(suggestion_text or "", candidate_name or "").lower()
        return "plastic" in base and any(token in text for token in ("paper", "carton", "glass", "metal"))

    @staticmethod
    def _packaging_switch_away_from_plastic(base_packaging: Optional[str], suggestion: RagSuggestion) -> bool:
        base = (base_packaging or "").lower()
        candidate_text = "{} {}".format(suggestion.suggestion or "", suggestion.rationale or "").lower()
        return "plastic" in base and any(token in candidate_text for token in ("paper", "carton", "glass", "metal"))
