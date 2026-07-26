import pytest
from types import SimpleNamespace

from app.foundry_agent import FoundryChatAgent


def _fake_choice(content: str = "", tool_calls: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content, tool_calls=tool_calls or [])
            )
        ]
    )


def _fake_tool_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_fallback_chat_remembers_booking_context_across_turns() -> None:
    agent = object.__new__(FoundryChatAgent)
    agent._model = "gpt-4o-mini"
    agent._assistant_id = None
    agent._threads = {}
    agent._fallback_messages = {}
    agent._fallback_booking_state = {}

    create_booking_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_booking_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"abc123","service_name":"Herre Klipning",'
            '"start_time":"2026-07-22T09:45:00+02:00","confirmation_text":"Din booking er bekr\u00e6ftet."}'
        )

    agent._dispatch = {
        "get_availability": lambda **_: '{"date":"2026-07-22","available_times":["09:45"]}',
        "create_booking": create_booking,
    }

    completion_calls = {"count": 0}

    def create_completion(*, messages, **_kwargs):
        completion_calls["count"] += 1

        if completion_calls["count"] == 1:
            return _fake_choice(
                tool_calls=[
                    _fake_tool_call(
                        "call-1",
                        "get_availability",
                        '{"service_id":"herre_klipning","date":"2026-07-22"}',
                    )
                ]
            )

        if completion_calls["count"] == 2:
            return _fake_choice(
                content="Herre Klipning is available today at 09:45. What is your phone number?"
            )

        if completion_calls["count"] == 3:
            assert len(messages) > 3
            assert any(
                msg.get("role") == "assistant"
                and "What is your phone number?" in msg.get("content", "")
                for msg in messages
            )
            assert any(
                msg.get("role") == "tool" and "09:45" in msg.get("content", "")
                for msg in messages
            )
            return _fake_choice(
                tool_calls=[
                    _fake_tool_call(
                        "call-2",
                        "create_booking",
                        '{"service_id":"herre_klipning","date":"2026-07-22","time":"09:45","phone":"23391178","language":"da"}',
                    )
                ]
            )

        return _fake_choice(content="Din booking er bekr\u00e6ftet.")

    agent._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_completion)
        )
    )
    agent._ensure_assistant_id = lambda: None

    first = agent.answer(
        SimpleNamespace(
            message="what is the earliest time for a herre klipning today?",
            session_id="session-1",
            language="en",
        )
    )

    assert "phone number" in first.reply.lower()

    second = agent.answer(
        SimpleNamespace(
            message="23391178",
            session_id="session-1",
            language="da",
        )
    )

    assert "navnet" in second.reply.lower()

    third = agent.answer(
        SimpleNamespace(
            message="Ali Hassan",
            session_id="session-1",
            language="da",
        )
    )

    assert third.booking is not None
    assert third.booking.status == "confirmed"
    assert create_booking_calls == [
        {
            "service_id": "herre_klipning",
            "date": "2026-07-22",
            "time": "09:45",
            "phone": "23391178",
            "language": "da",
            "customer_name": "Ali Hassan",
        }
    ]
    assert "bekr" in third.reply.lower()


def test_fallback_chat_asks_name_once_and_books_exact_selected_slot() -> None:
    agent = object.__new__(FoundryChatAgent)
    agent._model = "gpt-4o-mini"
    agent._assistant_id = None
    agent._threads = {}
    agent._fallback_messages = {}
    agent._fallback_booking_state = {}

    create_booking_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_booking_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"booking-1","service_name":"Herre Klipning",'
            '"start_time":"2026-07-22T09:45:00+02:00","confirmation_text":"Din tid er reserveret 2026-07-22T09:45:00+02:00."}'
        )

    agent._dispatch = {
        "get_availability": lambda **_: '{"date":"2026-07-22","available_times":["09:45","10:00"]}',
        "create_booking": create_booking,
    }

    completion_calls = {"count": 0}

    def create_completion(*, messages, **_kwargs):
        completion_calls["count"] += 1
        if completion_calls["count"] == 1:
            return _fake_choice(
                tool_calls=[
                    _fake_tool_call(
                        "call-1",
                        "get_availability",
                        '{"service_id":"herre_klipning","date":"2026-07-22"}',
                    )
                ]
            )
        return _fake_choice(content="Den tidligste ledige tid til Herre Klipning i dag er 09:45.")

    agent._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_completion)
        )
    )
    agent._ensure_assistant_id = lambda: None

    first = agent.answer(
        SimpleNamespace(
            message="what is the earliest time for a herre klipning today?",
            session_id="session-2",
            language="da",
        )
    )
    assert "09:45" in first.reply

    second = agent.answer(
        SimpleNamespace(
            message="book it for me my phone number is 23391178",
            session_id="session-2",
            language="da",
        )
    )
    assert "navnet" in second.reply.lower()
    assert create_booking_calls == []

    third = agent.answer(
        SimpleNamespace(
            message="Ali Hassan",
            session_id="session-2",
            language="da",
        )
    )
    assert third.booking is not None
    assert third.booking.start_time == "2026-07-22T09:45:00+02:00"
    assert create_booking_calls == [
        {
            "service_id": "herre_klipning",
            "date": "2026-07-22",
            "time": "09:45",
            "phone": "23391178",
            "language": "da",
            "customer_name": "Ali Hassan",
        }
    ]


# ---------------------------------------------------------------------------
# Helper: reusable minimal agent factory
# ---------------------------------------------------------------------------

def _make_agent(dispatch: dict, completion_fn) -> FoundryChatAgent:
    agent = object.__new__(FoundryChatAgent)
    agent._model = "gpt-4o-mini"
    agent._assistant_id = None
    agent._threads = {}
    agent._fallback_messages = {}
    agent._fallback_booking_state = {}
    agent._dispatch = dispatch
    agent._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=completion_fn)
        )
    )
    agent._ensure_assistant_id = lambda: None
    return agent


# ---------------------------------------------------------------------------
# Language stability: phone number and name must NOT change the language
# ---------------------------------------------------------------------------

def test_language_stays_english_after_phone_number_sent() -> None:
    """Regression: phone number must not flip the conversation language to Danish."""
    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(content="Great — please send your phone number.")
        system_content = messages[0]["content"]
        assert "phone numbers" in system_content.lower() or "digits" in system_content.lower()
        return _fake_choice(content="What is your name?")

    agent = _make_agent(dispatch={}, completion_fn=completion)

    agent.answer(SimpleNamespace(
        message="I want a men's haircut at 09:45", session_id="lang-phone", language="en"))
    reply = agent.answer(SimpleNamespace(
        message="23391178", session_id="lang-phone", language="en"))

    assert reply.reply
    assert reply.session_id == "lang-phone"


def test_language_stays_english_after_name_sent() -> None:
    """Regression: a customer name must not flip the conversation language."""
    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(content="What is your name?")
        return _fake_choice(content="Your appointment is confirmed.")

    agent = _make_agent(dispatch={}, completion_fn=completion)

    agent.answer(SimpleNamespace(
        message="Book 09:45, my phone is 23391178", session_id="lang-name", language="en"))
    reply = agent.answer(SimpleNamespace(
        message="Mehran", session_id="lang-name", language="en"))

    assert reply.reply


# ---------------------------------------------------------------------------
# _is_reset_message
# ---------------------------------------------------------------------------

def test_is_reset_message_recognises_known_phrases() -> None:
    agent = object.__new__(FoundryChatAgent)
    for phrase in ("forfra", "start forfra", "reset", "start over",
                   "RESET", "  forfra  ", "Start Over"):
        assert agent._is_reset_message(
            phrase), f"Expected reset for: {phrase!r}"


def test_is_reset_message_returns_false_for_normal_messages() -> None:
    agent = object.__new__(FoundryChatAgent)
    for phrase in ("hej", "book a haircut", "what time", "23391178", ""):
        assert not agent._is_reset_message(
            phrase), f"Should not be reset: {phrase!r}"


# ---------------------------------------------------------------------------
# _extract_phone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text,expected_digits", [
    ("My phone is +45 22334455", "4522334455"),
    ("Call me on 23391178",      "23391178"),
    ("+4541423333",              "4541423333"),
])
def test_extract_phone_valid_numbers(text: str, expected_digits: str) -> None:
    agent = object.__new__(FoundryChatAgent)
    result = agent._extract_phone(text)
    assert result is not None
    digits = "".join(c for c in result if c.isdigit())
    assert digits == expected_digits


@pytest.mark.parametrize("text", [
    "no phone here",
    "12345",
    "",
    "I want a haircut",
])
def test_extract_phone_returns_none_for_invalid(text: str) -> None:
    agent = object.__new__(FoundryChatAgent)
    assert agent._extract_phone(text) is None


# ---------------------------------------------------------------------------
# _extract_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("My name is Ali Hassan",   "Ali Hassan"),
    ("I am Mehran",             "Mehran"),
    ("i'm Sara",                "Sara"),
    ("Jeg hedder Ali",          "Ali"),
    ("mit navn er Sara Jensen", "Sara Jensen"),
])
def test_extract_name_pattern_matches(text: str, expected: str) -> None:
    agent = object.__new__(FoundryChatAgent)
    result = agent._extract_name(text)
    assert result is not None
    assert result.lower() == expected.lower()


def test_extract_name_returns_none_for_empty() -> None:
    agent = object.__new__(FoundryChatAgent)
    assert agent._extract_name("") is None
    assert agent._extract_name("   ") is None


# ---------------------------------------------------------------------------
# cancel_booking tool dispatch
# ---------------------------------------------------------------------------

def test_cancel_booking_tool_dispatched_and_returns_json() -> None:
    cancel_calls: list[str] = []

    def cancel_booking(booking_reference: str) -> str:
        cancel_calls.append(booking_reference)
        return '{"status":"canceled","cancellation_reference":"cancel-abc","message":"Canceled."}'

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(
                tool_calls=[_fake_tool_call(
                    "c1", "cancel_booking", '{"booking_reference":"abc123"}')]
            )
        return _fake_choice(content="Your booking abc123 has been canceled.")

    agent = _make_agent(
        dispatch={"cancel_booking": cancel_booking}, completion_fn=completion)

    reply = agent.answer(SimpleNamespace(
        message="Cancel my booking abc123", session_id="cancel-1", language="en"))

    assert cancel_calls == ["abc123"]
    assert reply.reply


# ---------------------------------------------------------------------------
# Unknown tool name returns error JSON and does not crash
# ---------------------------------------------------------------------------

def test_unknown_tool_name_returns_error_and_continues() -> None:
    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(
                tool_calls=[_fake_tool_call("c-bad", "nonexistent_tool", "{}")]
            )
        tool_messages = [m for m in messages if m.get("role") == "tool"]
        assert any("Unknown tool" in m.get("content", "")
                   for m in tool_messages)
        return _fake_choice(content="Sorry, I couldn't process that.")

    agent = _make_agent(dispatch={}, completion_fn=completion)

    reply = agent.answer(SimpleNamespace(
        message="do something weird", session_id="bad-tool", language="en"))

    assert "sorry" in reply.reply.lower()


# ---------------------------------------------------------------------------
# list_services tool dispatched with language parameter
# ---------------------------------------------------------------------------

def test_list_services_tool_called_with_conversation_language() -> None:
    list_calls: list[str] = []

    def list_services(language: str = "en") -> str:
        list_calls.append(language)
        return '[{"service_id":"herre_klipning","name":"Men\'s Haircut","duration_minutes":15,"price":"kr 180"}]'

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(
                tool_calls=[_fake_tool_call(
                    "ls1", "list_services", '{"language":"en"}')]
            )
        return _fake_choice(content="Here are the services: Men's Haircut kr 180.")

    agent = _make_agent(
        dispatch={"list_services": list_services}, completion_fn=completion)

    reply = agent.answer(SimpleNamespace(
        message="What services do you offer?", session_id="ls-test", language="en"))

    assert list_calls == ["en"]
    assert "men" in reply.reply.lower()


# ---------------------------------------------------------------------------
# Staff selection: booking must use the staff captured from get_staff_availability
# ---------------------------------------------------------------------------

def test_booking_uses_sahar_when_she_is_available() -> None:
    """When get_staff_availability returns Sahar as available, create_booking
    must be called with staff_name='Sahar Ebrahim' — even when the final booking
    turn is processed by the rule-based _complete_fallback_booking path."""
    create_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"bk-1","service_name":"Men\'s Haircut",'
            '"start_time":"2026-07-24T17:45:00+02:00","staff_name":"Sahar Ebrahim",'
            '"confirmation_text":"Booked with Sahar."}'
        )

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # LLM calls get_staff_availability first
            return _fake_choice(tool_calls=[
                _fake_tool_call("sa1", "get_staff_availability",
                                '{"service_id":"herre_klipning","date":"2026-07-24"}'),
            ])
        if call_count["n"] == 2:
            # LLM presents Sahar's slots and asks for phone
            return _fake_choice(content="Med Sahar er de ledige tider: 17:45. Send dit telefonnummer.")
        # Should NOT be called again — rule-based path handles phone/name turns
        return _fake_choice(content="unexpected")

    agent = _make_agent(
        dispatch={
            "get_staff_availability": lambda **_: '{"Sahar Ebrahim":["17:45"],"Other Barber":["16:00"]}',
            "create_booking": create_booking,
        },
        completion_fn=completion,
    )

    # Turn 1: user asks for a time
    t1 = agent.answer(SimpleNamespace(
        message="bestil herre klipning idag klokken 17:45",
        session_id="staff-test-1", language="da"))
    assert "sahar" in t1.reply.lower()

    # Turn 2: user provides phone number — rule-based path fires → asks for name
    t2 = agent.answer(SimpleNamespace(
        message="23391178", session_id="staff-test-1", language="da"))
    assert t2.booking is None  # name still missing

    # Turn 3: user provides name — rule-based path fires → booking created
    t3 = agent.answer(SimpleNamespace(
        message="Mehran Ghainian", session_id="staff-test-1", language="da"))

    assert t3.booking is not None
    assert t3.booking.status == "confirmed"
    # The booking must have been made with Sahar, not someone else.
    assert len(create_calls) == 1
    assert create_calls[0].get("staff_name") == "Sahar Ebrahim", (
        f"Expected staff_name='Sahar Ebrahim', got: {create_calls[0].get('staff_name')!r}"
    )


def test_booking_uses_chosen_staff_when_sahar_unavailable() -> None:
    """When Sahar is not in get_staff_availability result, the first available
    staff member is stored in state and must be passed to create_booking."""
    create_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"bk-2","service_name":"Men\'s Haircut",'
            '"start_time":"2026-07-24T16:00:00+02:00","staff_name":"Ali Hassan",'
            '"confirmation_text":"Booked with Ali Hassan."}'
        )

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(tool_calls=[
                _fake_tool_call("sa2", "get_staff_availability",
                                '{"service_id":"herre_klipning","date":"2026-07-24"}'),
            ])
        # Sahar not available — agent presents Ali Hassan
        return _fake_choice(content="Sahar er ikke ledig. Ali Hassan er ledig kl. 16:00. Vil du booke med Ali Hassan?")

    agent = _make_agent(
        dispatch={
            "get_staff_availability": lambda **_: '{"Ali Hassan":["16:00"]}',
            "create_booking": create_booking,
        },
        completion_fn=completion,
    )

    # Turn 1: user asks for 16:00 → LLM checks staff, stores Ali Hassan in state
    t1 = agent.answer(SimpleNamespace(
        message="bestil herre klipning idag klokken 16",
        session_id="staff-test-2", language="da"))
    assert "ali" in t1.reply.lower() or "16:00" in t1.reply

    # Turn 2: user gives phone — rule-based path detects it and asks for name
    t2 = agent.answer(SimpleNamespace(
        message="mit nummer er 23391178",
        session_id="staff-test-2", language="da"))
    assert t2.booking is None  # name still missing

    # Turn 3: user gives name — rule-based path books with Ali Hassan from state
    t3 = agent.answer(SimpleNamespace(
        message="Mehran Ghainian",
        session_id="staff-test-2", language="da"))

    assert t3.booking is not None
    assert len(create_calls) == 1
    assert create_calls[0].get("staff_name") == "Ali Hassan", (
        f"Expected staff_name='Ali Hassan', got: {create_calls[0].get('staff_name')!r}"
    )


def test_booking_honors_explicit_requested_teammate() -> None:
    """If the user explicitly asks for Ebrahim, that teammate must be passed to create_booking."""
    create_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"bk-3","service_name":"Men\'s Haircut",'
            '"start_time":"2026-07-24T16:00:00+02:00","staff_name":"Ebrahim",'
            '"confirmation_text":"Booked with Ebrahim."}'
        )

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(tool_calls=[
                _fake_tool_call("sa3", "get_staff_availability",
                                '{"service_id":"herre_klipning","date":"2026-07-24"}'),
            ])
        return _fake_choice(content="Ebrahim er ledig kl. 16:00. Send dit telefonnummer.")

    agent = _make_agent(
        dispatch={
            "get_staff_availability": lambda **_: '{"Ebrahim":["16:00"],"Sahar Ebrahim":["17:00"]}',
            "create_booking": create_booking,
        },
        completion_fn=completion,
    )

    t1 = agent.answer(SimpleNamespace(
        message="book 16:00 with Ebrahim",
        session_id="staff-test-3", language="en"))
    assert "ebrahim" in t1.reply.lower()

    t2 = agent.answer(SimpleNamespace(
        message="my phone number is 23391178",
        session_id="staff-test-3", language="en"))
    assert t2.booking is None

    t3 = agent.answer(SimpleNamespace(
        message="Mehran",
        session_id="staff-test-3", language="en"))

    assert t3.booking is not None
    assert len(create_calls) == 1
    assert create_calls[0].get("staff_name") == "Ebrahim"


# ---------------------------------------------------------------------------
# Teammate announcement and confirmation messaging scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "session_id, language, user_message, staff_payload, llm_announcement, expected_staff, expected_service_name",
    [
        (
            "announce-confirm-1",
            "da",
            "bestil herre klipning idag klokken 17:45",
            '{"Sahar Ebrahim":["17:45"],"Other Barber":["16:00"]}',
            "Med Sahar Ebrahim er de ledige tider: 17:45.",
            "Sahar Ebrahim",
            "Men's Haircut",
        ),
        (
            "announce-confirm-2",
            "da",
            "bestil herre klipning idag klokken 16:00",
            '{"Ali Hassan":["16:00"]}',
            "Sahar er ikke ledig. Ali Hassan er ledig kl. 16:00.",
            "Ali Hassan",
            "Men's Haircut",
        ),
        (
            "announce-confirm-3",
            "en",
            "book 16:00 with Ebrahim",
            '{"Ebrahim":["16:00"],"Sahar Ebrahim":["17:00"]}',
            "Ebrahim is available at 16:00.",
            "Ebrahim",
            "Men's Haircut",
        ),
    ],
)
def test_teammate_announcement_and_confirmation_flow_all_scenarios(
    session_id: str,
    language: str,
    user_message: str,
    staff_payload: str,
    llm_announcement: str,
    expected_staff: str,
    expected_service_name: str,
) -> None:
    """Ensure all booking scenarios communicate teammate name clearly and confirm
    service + time + teammate before/after booking."""
    create_calls: list[dict] = []

    def create_booking(**kwargs) -> str:
        create_calls.append(kwargs)
        return (
            '{"status":"confirmed","booking_id":"bk-confirm","service_name":"Men\'s Haircut",'
            f'"start_time":"2026-07-24T{kwargs["time"]}:00+02:00","staff_name":"{expected_staff}",'
            '"confirmation_text":"legacy-text"}'
        )

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(tool_calls=[
                _fake_tool_call(
                    "sa-all",
                    "get_staff_availability",
                    '{"service_id":"herre_klipning","date":"2026-07-24"}',
                ),
            ])
        return _fake_choice(content=llm_announcement)

    agent = _make_agent(
        dispatch={
            "get_staff_availability": lambda **_: staff_payload,
            "create_booking": create_booking,
        },
        completion_fn=completion,
    )

    first = agent.answer(SimpleNamespace(
        message=user_message,
        session_id=session_id,
        language=language,
    ))
    assert expected_staff.split()[0].lower() in first.reply.lower()

    second = agent.answer(SimpleNamespace(
        message="my phone number is 23391178" if language == "en" else "mit nummer er 23391178",
        session_id=session_id,
        language=language,
    ))
    assert second.booking is None

    third = agent.answer(SimpleNamespace(
        message="Mehran",
        session_id=session_id,
        language=language,
    ))

    assert third.booking is not None
    assert len(create_calls) == 1
    assert create_calls[0].get("staff_name") == expected_staff

    reply_lower = third.reply.lower()
    expected_first_name = expected_staff.split()[0].lower()

    # Pre-book confirmation must include service, time, and teammate.
    if language == "da":
        assert "jeg bekraefter lige" in reply_lower
        assert "jeg booker nu tiden hos" in reply_lower
    else:
        assert "just to confirm:" in reply_lower
        assert "i will now book this time with" in reply_lower

    assert expected_service_name.lower() in reply_lower
    assert "16:00" in third.reply or "17:45" in third.reply
    assert expected_first_name in reply_lower

    # Final confirmation must also include teammate name.
    if language == "da":
        assert "din tid er booket:" in reply_lower
        assert "bookingreference:" in reply_lower
    else:
        assert "your booking is confirmed:" in reply_lower
        assert "booking reference:" in reply_lower
    assert expected_first_name in reply_lower


def test_teammate_unavailable_message_mentions_teammate_and_next_step() -> None:
    """If booking fails for requested teammate/time, user must get a clear teammate-specific message."""

    def create_booking(**_kwargs) -> str:
        raise ValueError(
            "Requested staff 'Ebrahim' is not available at 16:00.")

    call_count = {"n": 0}

    def completion(*, messages, **_):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _fake_choice(tool_calls=[
                _fake_tool_call(
                    "sa-unavailable",
                    "get_staff_availability",
                    '{"service_id":"herre_klipning","date":"2026-07-24"}',
                ),
            ])
        return _fake_choice(content="Ebrahim is available at 16:00.")

    agent = _make_agent(
        dispatch={
            "get_staff_availability": lambda **_: '{"Ebrahim":["16:00"]}',
            "create_booking": create_booking,
        },
        completion_fn=completion,
    )

    agent.answer(SimpleNamespace(
        message="book 16:00 with Ebrahim",
        session_id="staff-unavailable", language="en"))
    agent.answer(SimpleNamespace(
        message="my phone number is 23391178",
        session_id="staff-unavailable", language="en"))
    final = agent.answer(SimpleNamespace(
        message="Mehran",
        session_id="staff-unavailable", language="en"))

    lower = final.reply.lower()
    assert "just to confirm:" in lower
    assert "with ebrahim" in lower
    assert "selected teammate is not available" in lower
    assert "choose another time or teammate" in lower
    assert final.booking is None
