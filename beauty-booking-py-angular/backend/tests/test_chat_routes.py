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
    if tomorrow.weekday() == 6:  # Sunday — salon is closed, booking is correctly rejected
        pytest.skip(
            "Tomorrow is Sunday (salon closed); booking rejection is tested separately")
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


def test_chat_endpoint_rejects_sunday_booking(client) -> None:
    """Booking on a Sunday must be rejected with a closed-day message."""
    # Find the next Sunday from today.
    today = datetime.now(timezone.utc).date()
    days_until_sunday = (6 - today.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    next_sunday = today + timedelta(days=days_until_sunday)
    response = client.post(
        "/api/chat",
        json={
            "message": f"Book ladies haircut {next_sunday.isoformat()} at 10 my phone is +45 22334455",
            "language": "en",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["booking"] is None
    reply_lower = payload["reply"].lower()
    assert "sunday" in reply_lower or "closed" in reply_lower

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


# ---------------------------------------------------------------------------
# Language-detection: reply language must match the language of the last
# user message regardless of the `language` field or the session history.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message, no_language_field, expected_fragments",
    [
        # Danish — default; typical Danish keyword triggers DA reply
        ("Hvad koster en dame klip?", True, ["kr", "dame klip"]),
        # English — pure English message must yield English reply
        ("What are your opening hours?", True, ["opening hours", "mon"]),
        # French — single clear French greeting
        ("Bonjour, quels sont vos horaires ?", True, ["horaires"]),
        # German — German opening-hours keyword
        ("Was sind eure Offnungszeiten?", True, ["offnungszeiten"]),
        # Chinese — CJK characters trigger Chinese reply
        ("你们的营业时间是什么？", True, ["营业时间"]),
    ],
    ids=["da-prices", "en-hours", "fr-hours", "de-hours", "zh-hours"],
)
def test_reply_language_matches_message_language(
    client, message: str, no_language_field: bool, expected_fragments: list[str]
) -> None:
    """Reply must be in the same language as the incoming message."""
    payload_in: dict = {"message": message}
    if not no_language_field:
        payload_in["language"] = "da"

    response = client.post("/api/chat", json=payload_in)
    assert response.status_code == 200
    reply = response.json()["reply"]
    for fragment in expected_fragments:
        assert fragment in reply.lower() if fragment.isascii() else fragment in reply, (
            f"Expected {fragment!r} in reply {reply!r}"
        )


@pytest.mark.parametrize(
    "message, lang_field, expected_fragments",
    [
        # lang field says "da" but message is English → must reply in English
        ("What are your opening hours?", "da", ["opening hours"]),
        # lang field says "en" but message is Danish → must reply in Danish
        ("Hvad er jeres abningstider?", "en", ["abningstider"]),
        # lang field says "da" but message is French → must reply in French
        ("Bonjour, quels sont vos horaires ?", "da", ["horaires"]),
        # lang field says "en" but message is German → must reply in German
        ("Was sind eure Offnungszeiten?", "en", ["offnungszeiten"]),
    ],
    ids=["en-msg-da-field", "da-msg-en-field",
         "fr-msg-da-field", "de-msg-en-field"],
)
def test_reply_language_ignores_language_field_when_message_language_is_clear(
    client, message: str, lang_field: str, expected_fragments: list[str]
) -> None:
    """The `language` field is only a fallback; message language always wins."""
    response = client.post(
        "/api/chat", json={"message": message, "language": lang_field})
    assert response.status_code == 200
    reply = response.json()["reply"]
    for fragment in expected_fragments:
        assert fragment in reply.lower(), (
            f"Expected {fragment!r} in reply {reply!r}"
        )


def test_reply_language_defaults_to_danish_for_ambiguous_message(client) -> None:
    """A message with no detectable language cues should fall back to Danish."""
    response = client.post(
        "/api/chat",
        json={"message": "42"},  # purely numeric — no language signal
    )
    assert response.status_code == 200
    reply = response.json()["reply"]
    # Danish fallback reply contains Danish booking/price guidance words
    assert any(word in reply.lower() for word in ("booking", "priser", "bestil", "telefonnummer", "dato")), (
        f"Expected Danish fallback reply, got: {reply!r}"
    )


@pytest.mark.parametrize(
    "messages",
    [
        # Session starts Danish, switches to English → last reply must be English
        [
            ("Hvad koster en dame klip?", "da", ["kr", "dame klip"]),
            ("What are your opening hours?", None, ["opening hours"]),
        ],
        # Session starts English, switches to French → last reply must be French
        [
            ("What are your opening hours?", "en", ["opening hours"]),
            ("Bonjour, quels sont vos horaires ?", None, ["horaires"]),
        ],
        # Session starts German, switches to Danish → last reply must be Danish
        [
            ("Was sind eure Offnungszeiten?", "de", ["offnungszeiten"]),
            ("Hvad er jeres abningstider?", None, ["abningstider"]),
        ],
    ],
    ids=["da-then-en", "en-then-fr", "de-then-da"],
)
def test_reply_language_switches_within_session(client, messages: list) -> None:
    """Each turn must reply in the language of *that* turn's message."""
    session_id: str | None = None
    for message, lang_field, expected_fragments in messages:
        payload_in: dict = {"message": message}
        if lang_field:
            payload_in["language"] = lang_field
        if session_id:
            payload_in["session_id"] = session_id

        response = client.post("/api/chat", json=payload_in)
        assert response.status_code == 200
        data = response.json()
        session_id = data["session_id"]
        reply = data["reply"]
        for fragment in expected_fragments:
            assert fragment in reply.lower(), (
                f"Expected {fragment!r} in reply {reply!r} (message={message!r})"
            )


def test_english_message_sunday_booking_is_rejected_in_english() -> None:
    """
    Regression test for the exact scenario reported by the user:

      User:    "i want to book a time on sunday 10 oclock for herre klipning"
      Before:  chatbot replied in Danish ("Jeg mangler: telefonnummer") and
               then silently confirmed a booking on a closed day.
      After:   chatbot must (1) reply in English because the message is in
               English, and (2) refuse the Sunday date with a clear
               closed-day message — no booking created.

    The `language` field is intentionally omitted to mimic the default "da"
    sent by the frontend, proving that message language overrides the field.
    """
    from starlette.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    today = datetime.now(timezone.utc).date()
    days_until_sunday = (6 - today.weekday()) % 7 or 7
    next_sunday = today + timedelta(days=days_until_sunday)

    # Build a message that looks exactly like the user's original input,
    # but with an absolute date so Sunday is always targeted regardless of
    # which day the test runs.
    message = (
        f"i want to book a time on {next_sunday.isoformat()} "
        "10 oclock for herre klipning"
    )

    response = client.post(
        "/api/chat",
        json={"message": message},   # no "language" field → defaults to "da"
    )

    assert response.status_code == 200
    payload = response.json()

    # 1. No booking must be created.
    assert payload["booking"] is None, (
        f"Expected no booking for a Sunday, got: {payload['booking']}"
    )

    reply = payload["reply"]

    # 2. Reply must be in English (detected from the message content).
    assert any(word in reply.lower() for word in ("sunday", "closed", "monday", "open")), (
        f"Expected English closed-day reply, got: {reply!r}"
    )
    assert not any(danish in reply.lower() for danish in ("lukket", "sondag", "søndag", "mandag")), (
        f"Reply should be in English, not Danish. Got: {reply!r}"
    )


def test_unavailable_time_rejection_uses_or_not_range_format(client) -> None:
    """Regression: available times must be presented with 'or'/'eller', NOT as a
    comma-separated pair that reads like a range (e.g. '10:00, 13:00' → user
    misreads as 'from 10 to 13' and then asks for 10:30 which is also rejected).

    The fix requires:
    1. Rejection message uses 'eller' / 'or' between slots (no ambiguous range).
    2. service_time is cleared from state after rejection, so asking for an
       in-range but unlisted slot (10:30) is re-rejected with the same clear
       list (not silently accepted because a stale time remains in state).
    """
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    if tomorrow.weekday() == 6:
        pytest.skip("Tomorrow is Sunday; booking rejection tested separately")

    # Step 1: request an unavailable time (14:00 → only 10:00 and 13:00 exist).
    first = client.post(
        "/api/chat",
        json={
            "message": "bestil herre klipning i morgen klokken 14 mit nummer er 23391178",
            "language": "da",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert "ikke ledigt" in first_payload["reply"].lower(), (
        f"Expected rejection for 14:00, got: {first_payload['reply']!r}"
    )
    reply = first_payload["reply"]
    # Slots must be joined with 'eller', not just a comma that looks like a range.
    assert " eller " in reply, (
        f"Expected ' eller ' between available slots to avoid range ambiguity, got: {reply!r}"
    )
    assert "10:00" in reply and "13:00" in reply

    # Step 2: ask for 10:30 – a time inside the apparent "range" but not a real slot.
    second = client.post(
        "/api/chat",
        json={
            "message": "tag klokken 10:30",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["booking"] is None, (
        "10:30 must not be confirmed — it is not in the available slots"
    )
    assert "ikke ledigt" in second_payload["reply"].lower(), (
        f"Expected second rejection for 10:30, got: {second_payload['reply']!r}"
    )

    # Step 3: ask for a genuinely available time (10:00) — booking must succeed.
    third = client.post(
        "/api/chat",
        json={
            "message": "tag klokken 10",
            "language": "da",
            "session_id": first_payload["session_id"],
        },
    )
    assert third.status_code == 200
    third_payload = third.json()
    assert third_payload["booking"] is not None and third_payload["booking"]["status"] == "confirmed", (
        f"Expected booking confirmation for 10:00 after correcting the time, got: {third_payload['reply']!r}"
    )


def test_unavailable_time_rejection_uses_or_in_english(client) -> None:
    """Same regression as above but in English — 'or' must separate available slots."""
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    if tomorrow.weekday() == 6:
        pytest.skip("Tomorrow is Sunday; booking rejection tested separately")

    first = client.post(
        "/api/chat",
        json={
            "message": "book herre klipning tomorrow at 10:30 my phone is 23391178",
            "language": "en",
        },
    )
    assert first.status_code == 200
    first_payload = first.json()
    reply = first_payload["reply"]
    assert "not available" in reply.lower(), (
        f"Expected rejection for 10:30, got: {reply!r}"
    )
    assert " or " in reply, (
        f"Expected ' or ' between available slots in English reply, got: {reply!r}"
    )


def test_booking_completes_when_service_given_conversationally_with_klip_in_message(client) -> None:
    """Regression: when a booking is in progress and the user provides the
    service name in a message containing 'klip' (e.g. 'Herre klipning,
    23391178'), the chatbot must NOT show the services list — it must extract
    the service + phone and finalize the booking.

    Scenario matches the exact user-reported flow:
      1. User asks for tomorrow at 10:00 → bot asks for service + phone
      2. User replies 'Herre klipning, 23391178' → booking confirmed
    """
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    if tomorrow.weekday() == 6:
        pytest.skip("Tomorrow is Sunday; booking rejection tested separately")

    # Turn 1: give date + time; service and phone are still missing.
    turn1 = client.post(
        "/api/chat",
        json={
            "message": "can i take a time tomorrow at 10",
            "language": "en",
        },
    )
    assert turn1.status_code == 200
    t1 = turn1.json()
    assert "service" in t1["reply"].lower() or "phone" in t1["reply"].lower(), (
        f"Expected bot to ask for missing fields, got: {t1['reply']!r}"
    )
    session_id = t1["session_id"]

    # Turn 2: user provides service name containing 'klip' and phone together.
    turn2 = client.post(
        "/api/chat",
        json={
            "message": "Herre klipning, 23391178",
            "language": "en",
            "session_id": session_id,
        },
    )
    assert turn2.status_code == 200
    t2 = turn2.json()
    # Must NOT return the services catalogue.
    assert "her er vores behandlinger" not in t2["reply"].lower(), (
        "Bot incorrectly returned the service list instead of completing the booking"
    )
    assert "here are our services" not in t2["reply"].lower(), (
        "Bot incorrectly returned the service list instead of completing the booking"
    )
    # Must confirm the booking.
    assert t2["booking"] is not None and t2["booking"]["status"] == "confirmed", (
        f"Expected booking confirmation, got reply: {t2['reply']!r}"
    )


def test_booking_completes_when_service_given_in_danish_conversationally(client) -> None:
    """Same scenario in Danish: 'jeg vil gerne herre klipning' after date+time
    are already captured must complete the booking, not list services."""
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    if tomorrow.weekday() == 6:
        pytest.skip("Tomorrow is Sunday; booking rejection tested separately")

    turn1 = client.post(
        "/api/chat",
        json={
            "message": "kan jeg få en tid i morgen klokken 10 mit nummer er 23391178",
            "language": "da",
        },
    )
    assert turn1.status_code == 200
    t1 = turn1.json()
    session_id = t1["session_id"]

    turn2 = client.post(
        "/api/chat",
        json={
            "message": "jeg vil gerne herre klipning",
            "language": "da",
            "session_id": session_id,
        },
    )
    assert turn2.status_code == 200
    t2 = turn2.json()
    assert "her er vores behandlinger" not in t2["reply"].lower(), (
        "Bot incorrectly returned the service list instead of completing the booking"
    )
    assert t2["booking"] is not None and t2["booking"]["status"] == "confirmed", (
        f"Expected booking confirmation, got reply: {t2['reply']!r}"
    )
