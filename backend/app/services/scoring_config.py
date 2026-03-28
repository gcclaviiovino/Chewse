from __future__ import annotations

DEFAULT_WEIGHTS = {
    "nutrition": 40,
    "ingredients": 25,
    "packaging": 15,
    "labels": 10,
    "origins": 10,
}

NUTRITION_THRESHOLDS = {
    "sugar_low": 5.0,
    "sugar_high": 15.0,
    "salt_low": 0.3,
    "salt_high": 1.5,
    "fat_high": 20.0,
    "fiber_good": 3.0,
    "proteins_good": 8.0,
}

NEUTRAL_SUBSCORES = {
    "nutrition": 50,
    "ingredients": 45,
    "packaging": 40,
    "labels": 45,
    "origins": 40,
}
