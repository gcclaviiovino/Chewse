from __future__ import annotations

import re
from typing import Iterable, List


_CATEGORY_PRIORITY = {
    "spreads": 10,
    "biscuits": 20,
    "cakes": 20,
    "cereals": 20,
    "cheese": 20,
    "desserts": 30,
    "legumes": 30,
    "fruits": 30,
    "vegetables": 30,
    "fish": 30,
    "meat": 30,
    "dairy": 40,
    "snacks": 60,
    "breakfasts": 80,
}

_CATEGORY_ALIASES = {
    "biscuit": "biscuits",
    "biscuits": "biscuits",
    "cookie": "biscuits",
    "cookies": "biscuits",
    "spread": "spreads",
    "spreads": "spreads",
    "sweet spread": "spreads",
    "sweet spreads": "spreads",
    "chocolate spread": "spreads",
    "chocolate spreads": "spreads",
    "nut spread": "spreads",
    "nut spreads": "spreads",
    "cracker": "snacks",
    "crackers": "snacks",
    "snack": "snacks",
    "snacks": "snacks",
    "sweet snack": "sweet snacks",
    "sweet snacks": "sweet snacks",
    "savory snack": "snacks",
    "savory snacks": "snacks",
    "breakfast": "breakfasts",
    "breakfasts": "breakfasts",
    "dessert": "desserts",
    "desserts": "desserts",
    "cake": "cakes",
    "cakes": "cakes",
    "cereal": "cereals",
    "cereals": "cereals",
    "fruit": "fruits",
    "fruits": "fruits",
    "vegetable": "vegetables",
    "vegetables": "vegetables",
    "legume": "legumes",
    "legumes": "legumes",
    "bean": "legumes",
    "beans": "legumes",
    "dairy": "dairy",
    "cheese": "cheese",
    "fish": "fish",
    "seafood": "fish",
    "meat": "meat",
}

_CATEGORY_GROUPS = {
    "spreads": ["spreads", "chocolate spreads", "sweet spreads"],
    "biscuits": ["biscuits", "cookies", "sweet snacks"],
    "snacks": ["snacks", "savory snacks", "crackers"],
    "breakfasts": ["breakfasts", "cereals", "biscuits"],
    "desserts": ["desserts", "cakes", "sweet snacks"],
    "fruits": ["fruits", "fruit"],
    "vegetables": ["vegetables", "vegetable"],
    "legumes": ["legumes", "beans"],
}


def canonicalize_category(value: str) -> str:
    normalized = _normalize_raw_category(value)
    if not normalized:
        return ""
    if normalized in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[normalized]
    singular = _singularize(normalized)
    if singular in _CATEGORY_ALIASES:
        return _CATEGORY_ALIASES[singular]
    plural = _pluralize(singular)
    return _CATEGORY_ALIASES.get(plural, plural)


def canonicalize_categories(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        canonical = canonicalize_category(value)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return result


def prioritize_categories(values: Iterable[str]) -> List[str]:
    canonical = canonicalize_categories(values)
    ranked = list(enumerate(canonical))
    ranked.sort(key=lambda item: (_category_priority(item[1]), item[0]))
    return [value for _, value in ranked]


def select_primary_category(values: Iterable[str]) -> str:
    prioritized = prioritize_categories(values)
    return prioritized[0] if prioritized else ""


def aliases_for_category(value: str) -> List[str]:
    canonical = canonicalize_category(value)
    if not canonical:
        return []
    aliases: List[str] = []
    seen: set[str] = set()
    for alias in _CATEGORY_GROUPS.get(canonical, [canonical]):
        normalized = _normalize_raw_category(alias)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        aliases.append(normalized)
    return aliases


def category_search_aliases(values: Iterable[str]) -> List[str]:
    canonical = prioritize_categories(values)
    aliases: List[str] = []
    seen: set[str] = set()
    for item in canonical:
        for normalized in aliases_for_category(item):
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            aliases.append(normalized)
    return aliases


def humanize_category(value: str) -> str:
    canonical = canonicalize_category(value)
    return canonical.replace("-", " ").strip()


def _normalize_raw_category(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[1]
    normalized = normalized.replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _singularize(value: str) -> str:
    if value.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"
    if value.endswith("ses") and len(value) > 3:
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss") and len(value) > 3:
        return value[:-1]
    return value


def _pluralize(value: str) -> str:
    if value.endswith("y") and len(value) > 1 and value[-2] not in "aeiou":
        return value[:-1] + "ies"
    if value.endswith("s"):
        return value
    return value + "s"


def _category_priority(value: str) -> int:
    return _CATEGORY_PRIORITY.get(value, 50)
