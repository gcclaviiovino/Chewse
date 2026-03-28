from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.schemas.pipeline import ProductData, ScoreResult
from app.services.scoring_config import DEFAULT_WEIGHTS, NEUTRAL_SUBSCORES, NUTRITION_THRESHOLDS


class ScoringEngine:
    def __init__(self, weights: Optional[Dict[str, int]] = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_score(self, product: ProductData) -> ScoreResult:
        reasons: List[str] = []
        flags: List[str] = []
        rule_triggers: List[Dict[str, object]] = []

        nutrition_score = self._score_nutrition(product.nutriments, reasons, flags, rule_triggers)
        ingredients_score = self._score_ingredients(product.ingredients_text, reasons, rule_triggers)
        packaging_score = self._score_packaging(product.packaging, reasons, rule_triggers)
        labels_score = self._score_labels(product.labels_tags, reasons, rule_triggers)
        origins_score = self._score_origins(product.origins, reasons, rule_triggers)

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
            rule_triggers.append(self._rule("low_confidence_product_data", "confidence", 0, "Product data confidence is below 0.4."))

        return ScoreResult(
            total_score=max(0, min(total, 100)),
            subscores=subscores,
            flags=sorted(set(flags)),
            deterministic_reasons=reasons,
            rule_triggers=rule_triggers,
        )

    def _score_nutrition(self, nutriments: Dict[str, object], reasons: List[str], flags: List[str], triggers: List[Dict[str, object]]) -> int:
        score = NEUTRAL_SUBSCORES["nutrition"]
        sugar = self._as_float(nutriments.get("sugars_100g"))
        salt = self._as_float(nutriments.get("salt_100g"))
        fat = self._as_float(nutriments.get("fat_100g"))
        fiber = self._as_float(nutriments.get("fiber_100g"))
        proteins = self._as_float(nutriments.get("proteins_100g"))

        if sugar is not None:
            if sugar <= NUTRITION_THRESHOLDS["sugar_low"]:
                score += 15
                reasons.append("Low sugar content improves the nutrition subscore.")
                triggers.append(self._rule("low_sugar", "nutrition", 15, "Low sugar content improves the nutrition subscore."))
            elif sugar >= NUTRITION_THRESHOLDS["sugar_high"]:
                score -= 20
                flags.append("high_sugar")
                reasons.append("High sugar content penalizes the nutrition subscore.")
                triggers.append(self._rule("high_sugar", "nutrition", -20, "High sugar content penalizes the nutrition subscore."))

        if salt is not None:
            if salt <= NUTRITION_THRESHOLDS["salt_low"]:
                score += 10
                triggers.append(self._rule("low_salt", "nutrition", 10, "Low salt content improves the nutrition subscore."))
            elif salt >= NUTRITION_THRESHOLDS["salt_high"]:
                score -= 15
                flags.append("high_salt")
                reasons.append("High salt content penalizes the nutrition subscore.")
                triggers.append(self._rule("high_salt", "nutrition", -15, "High salt content penalizes the nutrition subscore."))

        if fat is not None and fat >= NUTRITION_THRESHOLDS["fat_high"]:
            score -= 10
            reasons.append("High fat content slightly reduces the nutrition subscore.")
            triggers.append(self._rule("high_fat", "nutrition", -10, "High fat content reduces the nutrition subscore."))

        if fiber is not None and fiber >= NUTRITION_THRESHOLDS["fiber_good"]:
            score += 10
            reasons.append("Fiber content improves the nutrition subscore.")
            triggers.append(self._rule("high_fiber", "nutrition", 10, "Fiber content improves the nutrition subscore."))

        if proteins is not None and proteins >= NUTRITION_THRESHOLDS["proteins_good"]:
            score += 5
            triggers.append(self._rule("protein_bonus", "nutrition", 5, "Protein content improves the nutrition subscore."))

        return max(0, min(score, 100))

    def _score_ingredients(self, ingredients_text: Optional[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not ingredients_text:
            reasons.append("Missing ingredients list keeps the ingredients subscore neutral.")
            triggers.append(self._rule("ingredients_missing", "ingredients", 0, "Ingredients data is missing."))
            return NEUTRAL_SUBSCORES["ingredients"]

        ingredient_count = len([part.strip() for part in ingredients_text.split(",") if part.strip()])
        score = 80 if ingredient_count <= 5 else 60 if ingredient_count <= 10 else 40
        triggers.append(self._rule("ingredient_count", "ingredients", score - NEUTRAL_SUBSCORES["ingredients"], "Ingredient list length affects the ingredients subscore."))
        if "palm" in ingredients_text.lower():
            score -= 15
            reasons.append("Palm oil detected in ingredients reduces the ingredients subscore.")
            triggers.append(self._rule("palm_oil", "ingredients", -15, "Palm oil reduces the ingredients subscore."))
        if "additive" in ingredients_text.lower():
            score -= 10
            triggers.append(self._rule("additive_detected", "ingredients", -10, "Additives reduce the ingredients subscore."))
        reasons.append("Ingredient list length contributes to the ingredients subscore.")
        return max(0, min(score, 100))

    def _score_packaging(self, packaging: Optional[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not packaging:
            triggers.append(self._rule("packaging_missing", "packaging", 0, "Packaging data is missing."))
            return NEUTRAL_SUBSCORES["packaging"]
        normalized = packaging.lower()
        score = 50
        if any(token in normalized for token in ("glass", "paper", "carton")):
            score += 30
            reasons.append("Recyclable packaging materials increase the packaging subscore.")
            triggers.append(self._rule("recyclable_packaging", "packaging", 30, "Recyclable packaging increases the packaging subscore."))
        if any(token in normalized for token in ("plastic", "multilayer")):
            score -= 15
            reasons.append("Plastic-heavy packaging lowers the packaging subscore.")
            triggers.append(self._rule("plastic_packaging", "packaging", -15, "Plastic-heavy packaging lowers the packaging subscore."))
        return max(0, min(score, 100))

    def _score_labels(self, labels_tags: list[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not labels_tags:
            triggers.append(self._rule("labels_missing", "labels", 0, "Labels data is missing."))
            return NEUTRAL_SUBSCORES["labels"]
        score = 40
        if any("organic" in tag.lower() for tag in labels_tags):
            score += 35
            reasons.append("Organic labels improve the labels subscore.")
            triggers.append(self._rule("organic_label", "labels", 35, "Organic labels improve the labels subscore."))
        if any("fair-trade" in tag.lower() or "fairtrade" in tag.lower() for tag in labels_tags):
            score += 20
            triggers.append(self._rule("fairtrade_label", "labels", 20, "Fairtrade labels improve the labels subscore."))
        return max(0, min(score, 100))

    def _score_origins(self, origins: Optional[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not origins:
            triggers.append(self._rule("origins_missing", "origins", 0, "Origins data is missing."))
            return NEUTRAL_SUBSCORES["origins"]
        normalized = origins.lower()
        score = 50
        if "ital" in normalized or "europe" in normalized:
            score += 25
            reasons.append("Shorter supply-chain origin information increases the origins subscore.")
            triggers.append(self._rule("local_origin", "origins", 25, "Local or European origin improves the origins subscore."))
        if "world" in normalized or "," in normalized:
            score -= 10
            triggers.append(self._rule("broad_origin", "origins", -10, "Broad origin reduces the origins subscore."))
        return max(0, min(score, 100))

    @staticmethod
    def _as_float(value: object) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            match = re.search(r"[-+]?\d+(?:[.,]\d+)?", value)
            if not match:
                return None
            try:
                return float(match.group(0).replace(",", "."))
            except ValueError:
                return None
        return None

    @staticmethod
    def _rule(code: str, category: str, impact: int, message: str) -> Dict[str, object]:
        return {"code": code, "category": category, "impact": impact, "message": message}
