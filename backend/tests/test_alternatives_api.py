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
    assert payload["preference_source"] == "inline_markdown"
    assert payload["needs_preference_input"] is False


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


def test_alternatives_endpoint_asks_preferences_when_memory_missing(api_client, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "user_id": "missing-memory-user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preference_source"] == "none"
    assert payload["needs_preference_input"] is True
    assert payload["assistant_message"]
    assert "preferenze" in payload["assistant_message"].lower()


def test_alternatives_endpoint_reuses_memory_after_user_message(api_client, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / "{}.json".format(base_barcode)).write_text(json.dumps(sample_off_payload), encoding="utf-8")

    first = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "user_id": "alice",
            "user_message": "Per i biscotti sono vegana e intollerante al lattosio",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["preference_source"] == "user_message_extracted"
    assert first_payload["applied_preferences_markdown"]
    assert first_payload["needs_preference_input"] is False

    second = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "user_id": "alice",
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["preference_source"] == "memory_markdown"
    assert second_payload["applied_preferences_markdown"]
    assert second_payload["needs_preference_input"] is False


def test_alternatives_endpoint_supports_product_context_without_barcode(api_client, settings) -> None:
    compatible_candidate = {
        "status": 1,
        "product": {
            "code": "9999999999991",
            "product_name": "Crackers Integrali Bio",
            "brands": "Green Brand",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["snacks"],
            "quantity": "200 g",
            "ecoscore_score": 82,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.8}},
        },
    }
    (settings.off_data_dir / "9999999999991.json").write_text(json.dumps(compatible_candidate), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "product_name": "Crackers Integrali",
            "brand": "Local Test",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["snacks"],
            "quantity": "200g",
            "locale": "it-IT",
            "preferences_markdown": "- senza plastica\n- solo bio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["base_product"]["product_name"] == "Crackers Integrali"
    assert payload["selected_candidate"]["suggestion"]["candidate_barcode"] == "9999999999991"
    assert payload["selected_candidate"]["is_preference_compatible"] is True


def test_alternatives_endpoint_falls_back_to_three_scored_candidates_when_no_better_match_exists(
    api_client, settings
) -> None:
    base_payload = {
        "status": 1,
        "product": {
            "code": "1234567890123",
            "product_name": "Crackers Integrali Premium",
            "brands": "Base Brand",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["snacks"],
            "quantity": "200 g",
            "ecoscore_score": 92,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.7}},
        },
    }
    (settings.off_data_dir / "1234567890123.json").write_text(json.dumps(base_payload), encoding="utf-8")

    for index, score in enumerate((70, 66, 61), start=1):
        payload = {
            "status": 1,
            "product": {
                "code": "999999999999{}".format(index),
                "product_name": "Crackers Integrali {}".format(index),
                "brands": "Fallback Brand {}".format(index),
                "ingredients_text": "whole wheat flour, butter, cream",
                "packaging": "plastic tray",
                "labels_tags": [],
                "categories_tags": ["snacks"],
                "quantity": "200 g",
                "ecoscore_score": score,
                "ecoscore_grade": "b",
                "ecoscore_data": {"agribalyse": {"co2_total": 1.0 + (index * 0.1)}},
            },
        }
        (settings.off_data_dir / "999999999999{}.json".format(index)).write_text(json.dumps(payload), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": "1234567890123",
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
    assert payload["selected_candidate"]["suggestion"]["title"] in {
        "Alternativa in linea con le preferenze",
        "Alternativa valutata con scoring locale",
    }


def test_alternatives_endpoint_uses_preference_aware_supplement_before_disclaimer(
    api_client, settings
) -> None:
    base_payload = {
        "status": 1,
        "product": {
            "code": "1234567890123",
            "product_name": "Biscotti Integrali",
            "brands": "Base Brand",
            "ingredients_text": "whole wheat flour, olive oil, salt",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "250 g",
            "ecoscore_score": 90,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.8}},
        },
    }
    compatible_but_lower_eco = {
        "status": 1,
        "product": {
            "code": "9999999999991",
            "product_name": "Biscotti Avena Bio",
            "brands": "Green Brand",
            "ingredients_text": "oat flour, sunflower oil",
            "packaging": "paper",
            "labels_tags": ["organic"],
            "categories_tags": ["breakfasts"],
            "quantity": "250 g",
            "ecoscore_score": 72,
            "ecoscore_grade": "b",
            "ecoscore_data": {"agribalyse": {"co2_total": 1.1}},
        },
    }
    incompatible_better_eco = {
        "status": 1,
        "product": {
            "code": "9999999999992",
            "product_name": "Biscotti Crema",
            "brands": "Creamy Brand",
            "ingredients_text": "wheat flour, butter, cream",
            "packaging": "plastic tray",
            "labels_tags": [],
            "categories_tags": ["breakfasts"],
            "quantity": "250 g",
            "ecoscore_score": 95,
            "ecoscore_grade": "a",
            "ecoscore_data": {"agribalyse": {"co2_total": 0.7}},
        },
    }
    (settings.off_data_dir / "1234567890123.json").write_text(json.dumps(base_payload), encoding="utf-8")
    (settings.off_data_dir / "9999999999991.json").write_text(json.dumps(compatible_but_lower_eco), encoding="utf-8")
    (settings.off_data_dir / "9999999999992.json").write_text(json.dumps(incompatible_better_eco), encoding="utf-8")

    response = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": "1234567890123",
            "locale": "it-IT",
            "preferences_markdown": "- no dairy\n- senza plastica\n- solo bio",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_candidate"]["suggestion"]["candidate_barcode"] == "9999999999991"
    assert payload["selected_candidate"]["is_preference_compatible"] is True
    assert payload["requires_disclaimer"] is False
