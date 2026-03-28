from __future__ import annotations

import json


def test_alternatives_endpoint_prefers_candidates_matching_preferences(api_client, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")

    compatible_candidate = {
        "status": 1,
        "product": {
            "code": "9999999999991",
            "product_name": "Biscotti Avena Integrali",
            "brands": "Green Brand",
            "ingredients_text": "oat flour, whole wheat flour, sunflower oil",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "240 g",
            "ecoscore_score": 78,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.1}},
        },
    }
    incompatible_candidate = {
        "status": 1,
        "product": {
            "code": "9999999999992",
            "product_name": "Biscotti Crema",
            "brands": "Creamy Brand",
            "ingredients_text": "wheat flour, sugar, cream, butter",
            "packaging": "plastic tray",
            "labels_tags": [],
            "categories_tags": ["breakfasts"],
            "quantity": "250 g",
            "ecoscore_score": 80,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.0}},
        },
    }
    (settings.off_data_dir / "9999999999991.json").write_text(json.dumps(compatible_candidate), encoding="utf-8")
    (settings.off_data_dir / "9999999999992.json").write_text(json.dumps(incompatible_candidate), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "preferences_markdown": "- no dairy\n- senza plastica\n- solo bio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_candidate"]["suggestion"]["candidate_barcode"] == "9999999999991"
    assert payload["selected_candidate"]["is_preference_compatible"] is True
    assert payload["requires_disclaimer"] is False
    assert payload["impact_comparison"]["candidate_barcode"] == "9999999999991"


def test_alternatives_endpoint_falls_back_with_disclaimer_when_no_candidate_matches(api_client, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")

    for index in range(3):
        payload = {
            "status": 1,
            "product": {
                "code": "999999999999{}".format(index),
                "product_name": "Biscotti Burro {}".format(index),
                "brands": "Butter Brand",
                "ingredients_text": "wheat flour, sugar, butter, cream",
                "packaging": "plastic tray",
                "labels_tags": [],
                "categories_tags": ["breakfasts"],
                "quantity": "250 g",
                "ecoscore_score": 70 + index,
                "ecoscore_grade": "a",
                "ecoscore_data": {"agribalyse": {"co2_total": 1.2 - (index * 0.05)}},
            },
        }
        (settings.off_data_dir / "999999999999{}.json".format(index)).write_text(json.dumps(payload), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "preferences_markdown": "- no dairy\n- senza plastica\n- solo bio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requires_disclaimer"] is True
    assert len(payload["candidates"]) == 3
    assert all(candidate["requires_disclaimer"] is True for candidate in payload["candidates"])
    assert all(candidate["is_preference_compatible"] is False for candidate in payload["candidates"])
