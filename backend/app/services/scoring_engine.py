from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas.pipeline import ProductData, ScoreResult


DEFAULT_WEIGHTS = {
    "nutrition": 40,
    "ingredients": 25,
    "packaging": 15,
    "labels": 10,
    "origins": 10,
}


class ScoringEngine:
    def __init__(self, weights: Optional[Dict[str, int]] = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_score(self, product: ProductData) -> ScoreResult:
        reasons: List[str] = []
        flags: List[str] = []

        nutrition_score = self._score_nutrition(product.nutriments, reasons, flags)
        ingredients_score = self._score_ingredients(product.ingredients_text, reasons)
        packaging_score = self._score_packaging(product.packaging, reasons)
        labels_score = self._score_labels(product.labels_tags, reasons)
        origins_score = self._score_origins(product.origins, reasons)

        subscores = {
            "nutrition": nutrition_score,
            "ingredients": ingredients_score,
            "packaging": packaging_score,
            "labels": labels_score,
            "origins": origins_score,
        }

        total = 0
        for key, value in subscores.items():
            total += int((value / 100) * self.weights[key])

        if product.confidence < 0.4:
            flags.append("low_confidence_product_data")
            reasons.append("Product data confidence is low, so the explanation should mention uncertainty.")

        return ScoreResult(
            total_score=max(0, min(total, 100)),
            subscores=subscores,
            flags=sorted(set(flags)),
            deterministic_reasons=reasons,
        )

    def _score_nutrition(self, nutriments: Dict[str, object], reasons: List[str], flags: List[str]) -> int:
        score = 50
        sugar = self._as_float(nutriments.get("sugars_100g"))
        salt = self._as_float(nutriments.get("salt_100g"))
        fat = self._as_float(nutriments.get("fat_100g"))
        fiber = self._as_float(nutriments.get("fiber_100g"))
        proteins = self._as_float(nutriments.get("proteins_100g"))

        if sugar is not None:
            if sugar <= 5:
                score += 15
                reasons.append("Low sugar content improves the nutrition subscore.")
            elif sugar >= 15:
                score -= 20
                flags.append("high_sugar")
                reasons.append("High sugar content penalizes the nutrition subscore.")

        if salt is not None:
            if salt <= 0.3:
                score += 10
            elif salt >= 1.5:
                score -= 15
                flags.append("high_salt")
                reasons.append("High salt content penalizes the nutrition subscore.")

        if fat is not None and fat >= 20:
            score -= 10
            reasons.append("High fat content slightly reduces the nutrition subscore.")

        if fiber is not None and fiber >= 3:
            score += 10
            reasons.append("Fiber content improves the nutrition subscore.")

        if proteins is not None and proteins >= 8:
            score += 5

        return max(0, min(score, 100))

    def _score_ingredients(self, ingredients_text: Optional[str], reasons: List[str]) -> int:
        if not ingredients_text:
            reasons.append("Missing ingredients list keeps the ingredients subscore neutral.")
            return 45

        ingredient_count = len([part.strip() for part in ingredients_text.split(",") if part.strip()])
        score = 80 if ingredient_count <= 5 else 60 if ingredient_count <= 10 else 40
        if "palm" in ingredients_text.lower():
            score -= 15
            reasons.append("Palm oil detected in ingredients reduces the ingredients subscore.")
        if "additive" in ingredients_text.lower():
            score -= 10
        reasons.append("Ingredient list length contributes to the ingredients subscore.")
        return max(0, min(score, 100))

    def _score_packaging(self, packaging: Optional[str], reasons: List[str]) -> int:
        if not packaging:
            return 40
        normalized = packaging.lower()
        score = 50
        if any(token in normalized for token in ("glass", "paper", "carton")):
            score += 30
            reasons.append("Recyclable packaging materials increase the packaging subscore.")
        if any(token in normalized for token in ("plastic", "multilayer")):
            score -= 15
            reasons.append("Plastic-heavy packaging lowers the packaging subscore.")
        return max(0, min(score, 100))

    def _score_labels(self, labels_tags: list[str], reasons: List[str]) -> int:
        if not labels_tags:
            return 45
        score = 40
        if any("organic" in tag.lower() for tag in labels_tags):
            score += 35
            reasons.append("Organic labels improve the labels subscore.")
        if any("fair-trade" in tag.lower() or "fairtrade" in tag.lower() for tag in labels_tags):
            score += 20
        return max(0, min(score, 100))

    def _score_origins(self, origins: Optional[str], reasons: List[str]) -> int:
        if not origins:
            return 40
        normalized = origins.lower()
        score = 50
        if "ital" in normalized or "europe" in normalized:
            score += 25
            reasons.append("Shorter supply-chain origin information increases the origins subscore.")
        if "world" in normalized or "," in normalized:
            score -= 10
        return max(0, min(score, 100))

    @staticmethod
    def _as_float(value: object) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(",", "."))
            except ValueError:
                return None
        return None
