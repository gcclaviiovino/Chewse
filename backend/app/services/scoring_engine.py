from __future__ import annotations

from typing import Dict, List, Optional

from app.schemas.pipeline import ProductData, ScoreResult
from app.services.scoring_config import DEFAULT_WEIGHTS, NEUTRAL_SUBSCORES

_LOW_IMPACT_CATEGORY_HINTS = (
    "vegetable",
    "vegetables",
    "fruit",
    "fruits",
    "legume",
    "legumes",
    "beans",
    "lentils",
    "wholegrain",
    "whole-grain",
    "cereals",
)
_MEDIUM_IMPACT_CATEGORY_HINTS = (
    "biscuits",
    "cakes",
    "snacks",
    "bread",
    "pasta",
    "breakfasts",
    "desserts",
)
_HIGH_IMPACT_CATEGORY_HINTS = (
    "beef",
    "meat",
    "cheese",
    "butter",
    "cream",
    "dairy",
    "fish",
    "seafood",
)

_HOTSPOT_INGREDIENT_RULES = (
    ("beef", -35, "Very high-impact beef ingredients reduce the ingredients subscore.", "high_impact_beef"),
    ("veal", -35, "Very high-impact beef ingredients reduce the ingredients subscore.", "high_impact_beef"),
    ("lamb", -30, "High-impact ruminant meat ingredients reduce the ingredients subscore.", "high_impact_ruminant"),
    ("butter", -18, "Butter increases the ingredients environmental impact.", "high_impact_dairy"),
    ("cream", -18, "Cream increases the ingredients environmental impact.", "high_impact_dairy"),
    ("milk", -14, "Dairy ingredients increase the ingredients environmental impact.", "high_impact_dairy"),
    ("cheese", -18, "Cheese ingredients increase the ingredients environmental impact.", "high_impact_dairy"),
    ("palm", -20, "Palm oil reduces the ingredients subscore due to sourcing risk.", "palm_oil"),
    ("cocoa", -10, "Cocoa is treated as an ecological hotspot ingredient.", "cocoa_hotspot"),
    ("coffee", -10, "Coffee is treated as an ecological hotspot ingredient.", "coffee_hotspot"),
    ("rice", -8, "Rice is treated as a moderate ecological hotspot ingredient.", "rice_hotspot"),
    ("almond", -8, "Almonds are treated as a moderate ecological hotspot ingredient.", "almond_hotspot"),
    ("fish", -16, "Fish ingredients increase sourcing impact uncertainty.", "fish_hotspot"),
)

_POSITIVE_LABEL_RULES = (
    ("organic", 25, "Organic labels improve the labels subscore.", "organic_label"),
    ("fair-trade", 18, "Fairtrade labels improve the labels subscore.", "fairtrade_label"),
    ("fairtrade", 18, "Fairtrade labels improve the labels subscore.", "fairtrade_label"),
    ("msc", 12, "Certified fishery labels improve the labels subscore.", "msc_label"),
    ("asc", 10, "Aquaculture stewardship labels improve the labels subscore.", "asc_label"),
    ("rainforest", 12, "Rainforest Alliance labels improve the labels subscore.", "rainforest_alliance_label"),
    ("fsc", 8, "FSC labels improve the labels subscore.", "fsc_label"),
    ("no-palm-oil", 10, "No-palm-oil labels slightly improve the labels subscore.", "no_palm_oil_label"),
)


class ScoringEngine:
    def __init__(self, weights: Optional[Dict[str, int]] = None) -> None:
        self.weights = weights or DEFAULT_WEIGHTS

    def compute_score(self, product: ProductData) -> ScoreResult:
        reasons: List[str] = []
        flags: List[str] = []
        rule_triggers: List[Dict[str, object]] = []

        category_score = self._score_category_baseline(product.categories_tags, reasons, flags, rule_triggers)
        ingredients_score = self._score_ingredients(
            product.ingredients_text,
            product.eco_ingredient_signals,
            product.labels_tags,
            reasons,
            flags,
            rule_triggers,
        )
        packaging_score = self._score_packaging(product.packaging, reasons, flags, rule_triggers)
        labels_score = self._score_labels(product.labels_tags, reasons, rule_triggers)
        origins_score = self._score_origins(product.origins, reasons, rule_triggers)

        subscores = {
            "nutrition": category_score,
            "ingredients": ingredients_score,
            "packaging": packaging_score,
            "labels": labels_score,
            "origins": origins_score,
        }

        local_total = 0
        for key, value in subscores.items():
            local_total += int((value / 100) * self.weights[key])

        if product.confidence < 0.4:
            flags.append("low_confidence_product_data")
            reasons.append("Product data confidence is low, so ecological conclusions are less reliable.")
            rule_triggers.append(self._rule("low_confidence_product_data", "confidence", 0, "Product data confidence is below 0.4."))

        official_score = product.ecoscore_score
        total_score = max(0, min(local_total, 100))
        score_source: str = "local_fallback"

        if official_score is not None:
            local_weight = self._local_integration_weight(product)
            if local_weight > 0:
                total_score = round((official_score * (1 - local_weight)) + (local_total * local_weight))
                score_source = "off_plus_local"
                reasons.append("Open Food Facts Eco-Score is the primary score, adjusted with locally recovered ecological data.")
                rule_triggers.append(
                    self._rule(
                        "off_plus_local",
                        "score",
                        total_score - official_score,
                        "OFF Eco-Score is integrated with locally recovered ecological signals.",
                    )
                )
            else:
                total_score = official_score
                score_source = "off_ecoscore"
                reasons.append("Open Food Facts Eco-Score is used as the primary environmental score.")
                rule_triggers.append(
                    self._rule(
                        "off_ecoscore",
                        "score",
                        0,
                        "Open Food Facts Eco-Score is used as the primary environmental score.",
                    )
                )

        return ScoreResult(
            total_score=max(0, min(total_score, 100)),
            official_score=official_score,
            local_score=max(0, min(local_total, 100)),
            score_source=score_source,
            co2e_kg_per_kg=product.co2e_kg_per_kg,
            co2e_source=product.co2e_source,
            subscores=subscores,
            flags=sorted(set(flags)),
            deterministic_reasons=reasons,
            rule_triggers=rule_triggers,
        )

    def _local_integration_weight(self, product: ProductData) -> float:
        if product.ecoscore_score is None:
            return 0.0
        if not product.ecoscore_data:
            return 0.25

        weight = 0.0
        missing = product.ecoscore_data.get("missing")
        if isinstance(missing, dict):
            if missing.get("ingredients") and (product.ingredients_text or product.eco_ingredient_signals):
                weight += 0.2
            if missing.get("packagings") and product.packaging:
                weight += 0.1
            if missing.get("origins") and product.origins:
                weight += 0.1

        adjustments = product.ecoscore_data.get("adjustments")
        if isinstance(adjustments, dict):
            packaging_adjustment = adjustments.get("packaging")
            if isinstance(packaging_adjustment, dict) and packaging_adjustment.get("warning") == "packaging_data_missing" and product.packaging:
                weight = max(weight, 0.1)

            threatened_species = adjustments.get("threatened_species")
            if isinstance(threatened_species, dict) and threatened_species.get("warning") == "ingredients_missing" and (product.ingredients_text or product.eco_ingredient_signals):
                weight = max(weight, 0.2)

            origins_adjustment = adjustments.get("origins_of_ingredients")
            if isinstance(origins_adjustment, dict) and origins_adjustment.get("warning") == "origins_are_100_percent_unknown" and product.origins:
                weight = max(weight, 0.1)

        return min(weight, 0.45)

    def _score_category_baseline(
        self,
        categories_tags: List[str],
        reasons: List[str],
        flags: List[str],
        triggers: List[Dict[str, object]],
    ) -> int:
        if not categories_tags:
            triggers.append(self._rule("category_missing", "nutrition", 0, "Category data is missing."))
            return NEUTRAL_SUBSCORES["nutrition"]

        normalized = " ".join(tag.lower() for tag in categories_tags)
        score = NEUTRAL_SUBSCORES["nutrition"]
        if any(token in normalized for token in _LOW_IMPACT_CATEGORY_HINTS):
            score += 20
            reasons.append("Lower-impact product categories improve the category baseline.")
            triggers.append(self._rule("low_impact_category", "nutrition", 20, "Lower-impact categories improve the category baseline."))
        elif any(token in normalized for token in _HIGH_IMPACT_CATEGORY_HINTS):
            score -= 25
            flags.append("high_impact_category")
            reasons.append("High-impact product categories reduce the category baseline.")
            triggers.append(self._rule("high_impact_category", "nutrition", -25, "High-impact categories reduce the category baseline."))
        elif any(token in normalized for token in _MEDIUM_IMPACT_CATEGORY_HINTS):
            score -= 5
            reasons.append("Processed snack and dessert categories slightly reduce the category baseline.")
            triggers.append(self._rule("processed_category", "nutrition", -5, "Processed snack and dessert categories slightly reduce the category baseline."))
        return max(0, min(score, 100))

    def _score_ingredients(
        self,
        ingredients_text: Optional[str],
        eco_ingredient_signals: List[Dict[str, object]],
        labels_tags: List[str],
        reasons: List[str],
        flags: List[str],
        triggers: List[Dict[str, object]],
    ) -> int:
        if not ingredients_text and not eco_ingredient_signals:
            score = NEUTRAL_SUBSCORES["ingredients"]
            triggers.append(self._rule("ingredients_missing", "ingredients", 0, "Ingredients data is missing."))
            if any("no-palm-oil" in tag.lower() for tag in labels_tags):
                score += 10
                reasons.append("The no-palm-oil label slightly improves the ingredients subscore despite missing ingredients.")
                triggers.append(self._rule("no_palm_oil_without_ingredients", "ingredients", 10, "Explicit no-palm-oil labeling slightly improves the ingredients subscore."))
            else:
                reasons.append("Missing ingredients list keeps the ingredients subscore conservative.")
            return max(0, min(score, 100))

        normalized = (ingredients_text or "").lower()
        score = 60
        matched_codes: set[str] = set()

        if eco_ingredient_signals:
            for signal in eco_ingredient_signals:
                if not isinstance(signal, dict):
                    continue
                signal_id = str(signal.get("id") or "").strip().lower()
                present = signal.get("present")
                if signal_id == "palm_oil" and present is False:
                    score += 8
                    reasons.append("Structured no-palm-oil signal slightly improves the ingredients subscore.")
                    triggers.append(self._rule("no_palm_oil_signal", "ingredients", 8, "Structured no-palm-oil signal slightly improves the ingredients subscore."))
                    continue
                if not present:
                    continue
                if signal_id == "beef":
                    score -= 35
                    flags.append("high_impact_beef")
                    reasons.append("Very high-impact beef ingredients reduce the ingredients subscore.")
                    triggers.append(self._rule("high_impact_beef", "ingredients", -35, "Very high-impact beef ingredients reduce the ingredients subscore."))
                    matched_codes.add("high_impact_beef")
                elif signal_id in {"lamb"}:
                    score -= 30
                    flags.append("high_impact_ruminant")
                    reasons.append("High-impact ruminant meat ingredients reduce the ingredients subscore.")
                    triggers.append(self._rule("high_impact_ruminant", "ingredients", -30, "High-impact ruminant meat ingredients reduce the ingredients subscore."))
                    matched_codes.add("high_impact_ruminant")
                elif signal_id in {"milk", "cream", "butter", "cheese"} and "high_impact_dairy" not in matched_codes:
                    score -= 18
                    flags.append("high_impact_dairy")
                    reasons.append("Dairy ingredients increase the ingredients environmental impact.")
                    triggers.append(self._rule("high_impact_dairy", "ingredients", -18, "Dairy ingredients increase the ingredients environmental impact."))
                    matched_codes.add("high_impact_dairy")
                elif signal_id == "palm_oil" and "palm_oil" not in matched_codes:
                    score -= 20
                    flags.append("palm_oil")
                    reasons.append("Palm oil reduces the ingredients subscore due to sourcing risk.")
                    triggers.append(self._rule("palm_oil", "ingredients", -20, "Palm oil reduces the ingredients subscore due to sourcing risk."))
                    matched_codes.add("palm_oil")
                elif signal_id == "cocoa" and "cocoa_hotspot" not in matched_codes:
                    score -= 10
                    reasons.append("Cocoa is treated as an ecological hotspot ingredient.")
                    triggers.append(self._rule("cocoa_hotspot", "ingredients", -10, "Cocoa is treated as an ecological hotspot ingredient."))
                    matched_codes.add("cocoa_hotspot")
                elif signal_id == "coffee" and "coffee_hotspot" not in matched_codes:
                    score -= 10
                    reasons.append("Coffee is treated as an ecological hotspot ingredient.")
                    triggers.append(self._rule("coffee_hotspot", "ingredients", -10, "Coffee is treated as an ecological hotspot ingredient."))
                    matched_codes.add("coffee_hotspot")
                elif signal_id == "rice" and "rice_hotspot" not in matched_codes:
                    score -= 8
                    reasons.append("Rice is treated as a moderate ecological hotspot ingredient.")
                    triggers.append(self._rule("rice_hotspot", "ingredients", -8, "Rice is treated as a moderate ecological hotspot ingredient."))
                    matched_codes.add("rice_hotspot")
                elif signal_id == "almonds" and "almond_hotspot" not in matched_codes:
                    score -= 8
                    reasons.append("Almonds are treated as a moderate ecological hotspot ingredient.")
                    triggers.append(self._rule("almond_hotspot", "ingredients", -8, "Almonds are treated as a moderate ecological hotspot ingredient."))
                    matched_codes.add("almond_hotspot")
                elif signal_id == "fish" and "fish_hotspot" not in matched_codes:
                    score -= 16
                    reasons.append("Fish ingredients increase sourcing impact uncertainty.")
                    triggers.append(self._rule("fish_hotspot", "ingredients", -16, "Fish ingredients increase sourcing impact uncertainty."))
                    matched_codes.add("fish_hotspot")

        for token, impact, message, code in _HOTSPOT_INGREDIENT_RULES:
            if token not in normalized or code in matched_codes:
                continue
            score += impact
            matched_codes.add(code)
            reasons.append(message)
            triggers.append(self._rule(code, "ingredients", impact, message))
            if impact <= -18:
                flags.append(code)

        if any("palm" in normalized for _ in [0]) is False and any("no-palm-oil" in tag.lower() for tag in labels_tags):
            score += 8
            reasons.append("Explicit no-palm-oil labeling slightly improves the ingredients subscore.")
            triggers.append(self._rule("no_palm_oil_label", "ingredients", 8, "Explicit no-palm-oil labeling slightly improves the ingredients subscore."))

        return max(0, min(score, 100))

    def _score_packaging(
        self,
        packaging: Optional[str],
        reasons: List[str],
        flags: List[str],
        triggers: List[Dict[str, object]],
    ) -> int:
        if not packaging:
            triggers.append(self._rule("packaging_missing", "packaging", 0, "Packaging data is missing."))
            return NEUTRAL_SUBSCORES["packaging"]

        normalized = packaging.lower()
        score = 45
        if any(token in normalized for token in ("glass", "paper", "cardboard", "carton", "aluminum", "aluminium", "metal")):
            score += 20
            reasons.append("More recyclable packaging materials improve the packaging subscore.")
            triggers.append(self._rule("recyclable_packaging", "packaging", 20, "More recyclable packaging materials improve the packaging subscore."))
        if any(token in normalized for token in ("plastic", "multilayer", "multi-layer", "composite")):
            score -= 20
            flags.append("plastic_packaging")
            reasons.append("Plastic or multilayer packaging lowers the packaging subscore.")
            triggers.append(self._rule("plastic_packaging", "packaging", -20, "Plastic or multilayer packaging lowers the packaging subscore."))
        if any(token in normalized for token in ("bag", "sachet", "wrapper", "single-use")):
            score -= 5
            triggers.append(self._rule("single_use_packaging", "packaging", -5, "Single-use packaging slightly lowers the packaging subscore."))
        return max(0, min(score, 100))

    def _score_labels(self, labels_tags: list[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not labels_tags:
            triggers.append(self._rule("labels_missing", "labels", 0, "Labels data is missing."))
            return NEUTRAL_SUBSCORES["labels"]

        score = 40
        normalized_tags = [tag.lower() for tag in labels_tags]
        seen_codes: set[str] = set()
        for token, impact, message, code in _POSITIVE_LABEL_RULES:
            if code in seen_codes:
                continue
            if not any(token in tag for tag in normalized_tags):
                continue
            score += impact
            seen_codes.add(code)
            reasons.append(message)
            triggers.append(self._rule(code, "labels", impact, message))
        return max(0, min(score, 100))

    def _score_origins(self, origins: Optional[str], reasons: List[str], triggers: List[Dict[str, object]]) -> int:
        if not origins:
            triggers.append(self._rule("origins_missing", "origins", 0, "Origins data is missing."))
            return NEUTRAL_SUBSCORES["origins"]

        normalized = origins.lower()
        score = 45
        if any(token in normalized for token in ("italy", "italia", "ital", "local", "regional")):
            score += 25
            reasons.append("Local or national origin information improves the origins subscore.")
            triggers.append(self._rule("local_origin", "origins", 25, "Local or national origin information improves the origins subscore."))
        elif any(token in normalized for token in ("europe", "eu", "ue")):
            score += 10
            reasons.append("Regional origin information slightly improves the origins subscore.")
            triggers.append(self._rule("regional_origin", "origins", 10, "Regional origin information slightly improves the origins subscore."))

        if "world" in normalized or "," in normalized:
            score -= 10
            reasons.append("Broad or mixed origin information reduces the origins subscore.")
            triggers.append(self._rule("broad_origin", "origins", -10, "Broad or mixed origin information reduces the origins subscore."))

        return max(0, min(score, 100))

    @staticmethod
    def _rule(code: str, category: str, impact: int, message: str) -> Dict[str, object]:
        return {"code": code, "category": category, "impact": impact, "message": message}
