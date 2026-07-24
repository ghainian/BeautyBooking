from datetime import datetime, timedelta, timezone

import pytest


def test_chat_endpoint_returns_price_overview(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hvad koster en dame klip?", "language": "da"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"].startswith("chat-")
    assert "priser" in payload["reply"].lower()


def test_chat_endpoint_returns_opening_hours(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "What are your opening hours?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "opening hours" in payload["reply"].lower()


def test_chat_endpoint_can_complete_booking_with_session_context(client) -> None:
    first = client.post(
        "/api/chat",
        json={
            "message": "Book ladies haircut friday at 10",
            "language": "en",
        },
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "phone number" in first_payload["reply"].lower()

    second = client.post(
        "/api/chat",
        json={
            "message": "My phone is +45 22334455",
            "language": "en",
            "session_id": first_payload["session_id"],
        },
    )

    assert second.status_code == 200
    second_payload = second.json()
    assert "confirmed" in second_payload["reply"].lower()
    assert second_payload["booking"]["status"] == "confirmed"


def test_chat_endpoint_accepts_local_8_digit_phone_and_confirms_booking(client) -> None:
    first = client.post(
        "/api/chat",
        json={
            "message": "Bestil herre klipning fredag klokken 10",
            "language": "da",
        },
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "telefonnummer" in first_payload["reply"].lower()

    second = client.post(
        "/api/chat",
        json={
            "message": "23391178",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )

    assert second.status_code == 200
    second_payload = second.json()
    assert "oprettet" in second_payload["reply"].lower()
    assert second_payload["booking"]["status"] == "confirmed"
    assert "telefonnummer" not in second_payload["reply"].lower()


def test_chat_endpoint_returns_fallback_help_for_general_message(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "hej", "language": "da"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "booking" in payload["reply"].lower()
    assert "priser" in payload["reply"].lower()


def test_chat_endpoint_prompts_for_required_fields_on_empty_input(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "", "language": "da"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "telefonnummer" in payload["reply"].lower()
    assert "dato" in payload["reply"].lower()


def test_chat_endpoint_returns_address_phone_and_booking_link(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hvad er jeres adresse og telefon?", "language": "da"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "amagerbrogade 219" in payload["reply"].lower()
    assert "+45 41 42 33 33" in payload["reply"]
    assert "salonanova.setmore.com" in payload["reply"].lower()


def test_chat_endpoint_returns_services_list_from_catalog(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hvilke behandlinger har i?", "language": "da"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "herre klipning" in payload["reply"].lower()
    assert "dame klip" in payload["reply"].lower()
    assert "kr 180" in payload["reply"].lower()


def test_chat_endpoint_returns_english_prices_from_catalog(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "What is the price list?", "language": "en"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "here are the prices" in payload["reply"].lower()
    assert "ladies haircut" in payload["reply"].lower()
    assert "kr 300" in payload["reply"].lower()


def test_chat_endpoint_reports_unavailable_time_and_alternatives(client) -> None:
    first = client.post(
        "/api/chat",
        json={
            "message": "Bestil herre klipning fredag klokken 15",
            "language": "da",
        },
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "telefonnummer" in first_payload["reply"].lower()

    second = client.post(
        "/api/chat",
        json={
            "message": "23391178",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )

    assert second.status_code == 200
    second_payload = second.json()
    assert "ikke ledigt" in second_payload["reply"].lower()
    assert "10:00" in second_payload["reply"]
    assert "13:00" in second_payload["reply"]


def test_chat_endpoint_reset_clears_booking_context(client) -> None:
    first = client.post(
        "/api/chat",
        json={
            "message": "Bestil dame klip fredag klokken 10",
            "language": "da",
        },
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "telefonnummer" in first_payload["reply"].lower()

    reset = client.post(
        "/api/chat",
        json={
            "message": "forfra",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )

    assert reset.status_code == 200
    reset_payload = reset.json()
    assert "starter forfra" in reset_payload["reply"].lower()

    after_reset = client.post(
        "/api/chat",
        json={
            "message": "23391178",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )

    assert after_reset.status_code == 200
    after_reset_payload = after_reset.json()
    assert "jeg mangler" in after_reset_payload["reply"].lower()
    assert "behandling" in after_reset_payload["reply"].lower()


def test_chat_endpoint_auto_detects_french_from_message(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Bonjour, quels sont vos horaires ?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "horaires d'ouverture" in payload["reply"].lower()


def test_chat_endpoint_auto_detects_german_from_message(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Hallo, was sind eure Offnungszeiten?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "offnungszeiten" in payload["reply"].lower()


def test_chat_endpoint_auto_detects_chinese_from_message(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "你们的营业时间是什么？"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "营业时间" in payload["reply"]


def test_chat_endpoint_detects_language_per_message_in_same_session(client) -> None:
    first = client.post(
        "/api/chat",
        json={"message": "Hello"},
    )

    assert first.status_code == 200
    first_payload = first.json()
    assert "i can help" in first_payload["reply"].lower()

    second = client.post(
        "/api/chat",
        json={
            "message": "Bonjour",
            "session_id": first_payload["session_id"],
        },
    )

    assert second.status_code == 200
    second_payload = second.json()
    assert "je peux aider" in second_payload["reply"].lower()


@pytest.mark.parametrize(
    "message, expected_fragment",
    [
        ("Hvornar har I abent?", "abningstider"),
        ("What are your opening hours?", "opening hours"),
        ("Quels sont vos horaires ?", "horaires d'ouverture"),
        ("Was sind eure Offnungszeiten?", "offnungszeiten"),
        ("你们的营业时间是什么？", "营业时间"),
    ],
)
def test_chat_endpoint_answers_opening_hours_in_supported_languages(client, message: str, expected_fragment: str) -> None:
    response = client.post("/api/chat", json={"message": message})

    assert response.status_code == 200
    payload = response.json()
    assert expected_fragment in payload["reply"].lower(
    ) if expected_fragment.isascii() else expected_fragment in payload["reply"]


@pytest.mark.parametrize(
    "message, expected_fragment",
    [
        ("Who works in the salon team?", "experienced stylists"),
        ("Hvem arbejder i salonen?", "erfarne stylister"),
        ("Qui travaille dans le salon ?", "stylistes experimentes"),
        ("Wer arbeitet im Salon?", "erfahrenen stylisten"),
        ("沙龙里有哪些团队成员？", "经验丰富的造型师"),
    ],
)
def test_chat_endpoint_answers_team_questions_without_inventing_names(client, message: str, expected_fragment: str) -> None:
    response = client.post("/api/chat", json={"message": message})

    assert response.status_code == 200
    payload = response.json()
    assert expected_fragment in payload["reply"].lower(
    ) if expected_fragment.isascii() else expected_fragment in payload["reply"]


def _expected_next_week_date(today, weekday: int):
    days_until_next_monday = 7 - today.weekday()
    if days_until_next_monday <= 0:
        days_until_next_monday += 7
    return today + timedelta(days=days_until_next_monday + weekday)


@pytest.mark.parametrize(
    "language, phrase",
    [
        ("da", "i dag"),
        ("en", "today"),
        ("fr", "aujourd'hui"),
        ("de", "heute"),
        ("zh", "今天"),
    ],
)
def test_chat_endpoint_parses_today_for_booking_in_supported_languages(client, language: str, phrase: str) -> None:
    today = datetime.now(timezone.utc).date()
    response = client.post(
        "/api/chat",
        json={
            "message": f"Book ladies haircut {phrase} at 10 my phone is +45 22334455",
            "language": language,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["booking"]["status"] == "confirmed"
    assert today.isoformat() in payload["reply"]


@pytest.mark.parametrize(
    "language, phrase",
    [
        ("da", "i morgen"),
        ("en", "tomorrow"),
        ("fr", "demain"),
        ("de", "morgen"),
        ("zh", "明天"),
    ],
)
def test_chat_endpoint_parses_tomorrow_for_booking_in_supported_languages(client, language: str, phrase: str) -> None:
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    response = client.post(
        "/api/chat",
        json={
            "message": f"Book ladies haircut {phrase} at 10 my phone is +45 22334455",
            "language": language,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["booking"]["status"] == "confirmed"
    assert tomorrow.isoformat() in payload["reply"]


@pytest.mark.parametrize(
    "language, phrase",
    [
        ("da", "naeste uge fredag"),
        ("en", "next week friday"),
        ("fr", "semaine prochaine vendredi"),
        ("de", "naechste woche freitag"),
        ("zh", "下周周五"),
    ],
)
def test_chat_endpoint_parses_next_week_for_booking_in_supported_languages(client, language: str, phrase: str) -> None:
    today = datetime.now(timezone.utc).date()
    expected_date = _expected_next_week_date(today, 4)
    response = client.post(
        "/api/chat",
        json={
            "message": f"Book ladies haircut {phrase} at 10 my phone is +45 22334455",
            "language": language,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["booking"]["status"] == "confirmed"
    assert expected_date.isoformat() in payload["reply"]


def test_chat_endpoint_answers_opening_hours_for_today_query(client) -> None:
    today = datetime.now(timezone.utc).date()
    expected_hours = "09:30-16:00" if today.weekday() == 5 else "09:30-18:00"
    response = client.post(
        "/api/chat",
        json={"message": "Are you open today?"},
    )

    assert response.status_code == 200
    payload = response.json()
    if today.weekday() == 6:
        assert "closed" in payload["reply"].lower()
    else:
        assert expected_hours in payload["reply"]


def test_chat_endpoint_answers_opening_hours_for_next_week_query(client) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "Are you open next week?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "next week" in payload["reply"].lower()
    assert "09:30-18:00" in payload["reply"]
