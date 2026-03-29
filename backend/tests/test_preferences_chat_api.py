from __future__ import annotations

import json


def test_preferences_chat_requests_input_when_memory_missing(api_client) -> None:
    response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "new-user",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preference_source"] == "none"
    assert payload["needs_preference_input"] is True
    assert "preferenze" in payload["assistant_message"].lower()


def test_preferences_chat_saves_global_preferences(api_client, settings) -> None:
    memory_path = settings.off_data_dir.parent / "data" / "agent_memory" / "alice.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        "# User preferences memory\n\n"
        "Last updated: 2026-03-29T09:06:33+00:00\n\n"
        "## category: biscuits\n"
        "- no dairy\n",
        encoding="utf-8",
    )
    response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "alice",
            "user_message": "Per i biscotti sono vegana e senza lattosio",
            "chat_history": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preference_source"] == "user_message_extracted"
    assert "## category: biscuits" in payload["applied_preferences_markdown"]
    assert "- vegan" in payload["applied_preferences_markdown"]
    assert "- no dairy" in payload["applied_preferences_markdown"]
    assert payload["preference_category"] is None
    assert "memoria" in payload["assistant_message"].lower()


def test_preferences_chat_can_recall_saved_memory(api_client, settings) -> None:
    memory_path = settings.off_data_dir.parent / "data" / "agent_memory" / "alice.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        "# User preferences memory\n\n"
        "Last updated: 2026-03-29T09:06:33+00:00\n\n"
        "## category: biscuits\n"
        "- no dairy\n",
        encoding="utf-8",
    )
    save_response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "alice",
            "user_message": "Per i biscotti sono vegana e senza lattosio",
            "chat_history": [],
        },
    )
    assert save_response.status_code == 200

    recall_response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "alice",
            "user_message": "Dimmi cosa hai in memoria al momento",
            "chat_history": [
                {"role": "assistant", "content": save_response.json()["assistant_message"]},
                {"role": "user", "content": "Sono vegana e senza lattosio"},
            ],
        },
    )
    assert recall_response.status_code == 200
    recall_payload = recall_response.json()
    assert recall_payload["preference_source"] == "memory_markdown"
    assert "## category: biscuits" in recall_payload["applied_preferences_markdown"]
    assert "vegan" in recall_payload["assistant_message"].lower()


def test_preferences_chat_returns_full_memory_document(api_client, settings) -> None:
    memory_path = settings.off_data_dir.parent / "data" / "agent_memory" / "mvp-default-user.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        "# User preferences memory\n\n"
        "Last updated: 2026-03-29T09:06:33+00:00\n\n"
        "## category: biscuits\n"
        "- no dairy\n\n"
        "## category: spreads\n"
        "- nessuna preferenza\n",
        encoding="utf-8",
    )

    response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "mvp-default-user",
            "user_message": "Dimmi cosa hai in memoria al momento",
            "chat_history": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "## category: biscuits" in payload["applied_preferences_markdown"]
    assert "## category: spreads" in payload["applied_preferences_markdown"]


def test_preferences_chat_does_not_create_generic_category(api_client, settings) -> None:
    memory_path = settings.off_data_dir.parent / "data" / "agent_memory" / "mvp-default-user.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        "# User preferences memory\n\n"
        "Last updated: 2026-03-29T09:06:33+00:00\n\n"
        "## category: biscuits\n"
        "- no dairy\n\n"
        "## category: spreads\n"
        "- nessuna preferenza\n",
        encoding="utf-8",
    )

    response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "mvp-default-user",
            "user_message": "Sono vegana",
            "chat_history": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["preference_source"] == "memory_markdown"
    assert "generic" not in (payload["applied_preferences_markdown"] or "").lower()
    assert "categoria" in payload["assistant_message"].lower()


def test_alternatives_endpoint_uses_global_preferences_from_home_chat(api_client, settings, sample_off_payload) -> None:
    base_barcode = sample_off_payload["product"]["code"]
    (settings.off_data_dir / f"{base_barcode}.json").write_text(json.dumps(sample_off_payload), encoding="utf-8")
    memory_path = settings.off_data_dir.parent / "data" / "agent_memory" / "alice.md"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        "# User preferences memory\n\n"
        "Last updated: 2026-03-29T09:06:33+00:00\n\n"
        "## category: breakfasts\n"
        "- no dairy\n",
        encoding="utf-8",
    )

    pref_response = api_client.post(
        "/preferences/chat",
        json={
            "user_id": "alice",
            "user_message": "Per la colazione sono vegana e senza lattosio",
            "chat_history": [],
        },
    )
    assert pref_response.status_code == 200

    alternatives = api_client.post(
        "/alternatives/from-barcode",
        json={
            "barcode": base_barcode,
            "locale": "it-IT",
            "user_id": "alice",
        },
    )
    assert alternatives.status_code == 200
    payload = alternatives.json()
    assert payload["preference_source"] == "memory_markdown"
    assert "- vegan" in payload["applied_preferences_markdown"]
    assert "- no dairy" in payload["applied_preferences_markdown"]
    assert payload["needs_preference_input"] is False
