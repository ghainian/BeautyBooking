from datetime import datetime, timedelta, timezone

import pytest

from app.booking_adapter import (
    BookingAdapter,
    _date_iso_to_setmore_slots,
    _iso_to_setmore_utc,
    _normalize_person_name,
    _slot_to_hhmm,
    _split_name,
)
from app.booking_models import BookingRequest, CancelVerifyRequest


@pytest.fixture(autouse=True)
def _force_stub_mode(monkeypatch) -> None:
    monkeypatch.delenv("SETMORE_REFRESH_TOKEN", raising=False)


def test_list_services_returns_all_catalog_entries_with_prices() -> None:
    adapter = BookingAdapter()

    services = adapter.list_services(language="da")

    assert len(services) == 13
    assert [service.service_id for service in services] == [
        "herre_klipning",
        "herre_klip_fade",
        "herre_klip_tape_fade",
        "herre_klip_mullet_fade",
        "borne_klip",
        "herre_pensionist",
        "haircut_ladies",
        "dame_vask_og_klip",
        "dame_pandehar_klipning",
        "bund_farve",
        "farve_kort_har",
        "farve_lang_har",
        "striber_kort_har",
    ]
    assert [service.price_label for service in services] == [
        "kr 180",
        "kr 180",
        "kr 180",
        "kr 180",
        "kr 140",
        "kr 140",
        "kr 300",
        "kr 350",
        "kr 100",
        "kr 450",
        "kr 550",
        "kr 900",
        "kr 680",
    ]


def test_get_price_overview_contains_booking_page_prices() -> None:
    adapter = BookingAdapter()

    overview = adapter.get_price_overview(language="da")

    assert "Herre Klipning: kr 180" in overview
    assert "Borne Klip: kr 140" in overview
    assert "Dame Klip: kr 300" in overview
    assert "Dame: vask og klip: kr 350" in overview
    assert "Bund farve: kr 450" in overview


def test_catalog_cache_refreshes_on_sunday_morning(monkeypatch) -> None:
    adapter = BookingAdapter()
    copenhagen_offset = timezone(timedelta(hours=2))
    times = [
        datetime(2026, 7, 18, 9, 0, tzinfo=copenhagen_offset),
        datetime(2026, 7, 18, 12, 0, tzinfo=copenhagen_offset),
        datetime(2026, 7, 19, 8, 1, tzinfo=copenhagen_offset),
    ]
    load_calls = {"count": 0}

    def fake_now() -> datetime:
        return times.pop(0)

    def fake_load() -> list[dict]:
        load_calls["count"] += 1
        return [
            {
                "service_id": "haircut_ladies",
                "name_da": "Dame Klip",
                "name_en": "Ladies Haircut",
                "duration_minutes": 30,
                "price_label": "kr 300",
            }
        ]

    monkeypatch.setattr(adapter, "_now_in_copenhagen", fake_now)
    monkeypatch.setattr(adapter, "_load_catalog_source", fake_load)

    adapter.list_services(language="da")
    adapter.list_services(language="da")
    adapter.list_services(language="da")

    assert load_calls["count"] == 2


def test_get_availability_filters_past_slots_for_today(monkeypatch) -> None:
    adapter = BookingAdapter()

    copenhagen_offset = timezone(timedelta(hours=2))
    now = datetime(2026, 7, 22, 11, 10, tzinfo=copenhagen_offset)
    monkeypatch.setattr(adapter, "_now_in_copenhagen", lambda: now)

    response = adapter.get_availability(
        service_id="herre_klipning", date="2026-07-22")

    assert [slot.start_time for slot in response.slots] == [
        "2026-07-22T13:00:00"
    ]


def test_get_availability_keeps_all_slots_for_future_date(monkeypatch) -> None:
    adapter = BookingAdapter()

    copenhagen_offset = timezone(timedelta(hours=2))
    now = datetime(2026, 7, 22, 11, 10, tzinfo=copenhagen_offset)
    monkeypatch.setattr(adapter, "_now_in_copenhagen", lambda: now)

    response = adapter.get_availability(
        service_id="herre_klipning", date="2026-07-23")

    assert [slot.start_time for slot in response.slots] == [
        "2026-07-23T10:00:00",
        "2026-07-23T13:00:00",
    ]


def test_setmore_payload_time_keeps_copenhagen_wall_clock() -> None:
    assert _iso_to_setmore_utc(
        "2026-07-22T11:10:00+02:00") == "2026-07-22T11:10Z"
    assert _iso_to_setmore_utc(
        "2026-12-22T11:10:00+01:00") == "2026-12-22T11:10Z"


def test_stub_booking_normalizes_naive_start_time_to_copenhagen() -> None:
    adapter = BookingAdapter()

    response = adapter.create_booking(
        BookingRequest(
            customer_phone="23391178",
            service_id="herre_klipning",
            start_time="2026-07-22T11:10:00",
            language="da",
            customer_name="Ali Hassan",
            idempotency_key="test-1",
        )
    )

    assert response.start_time == "2026-07-22T11:10:00+02:00"


def test_staff_priority_prefers_sahar_ebrahim_on_monday() -> None:
    adapter = BookingAdapter()
    adapter._sm_staff = [
        {"key": "staff-1", "full_name": "Other Barber"},
        {"key": "staff-2", "full_name": "Sahar Ebrahim"},
    ]
    service = {"staff_keys": ["staff-1", "staff-2"]}

    ordered = adapter._staff_keys_for_service(service, date_iso="2026-07-20")

    assert ordered == ["staff-2", "staff-1"]


def test_staff_priority_deprioritizes_sahar_ebrahim_on_non_monday() -> None:
    adapter = BookingAdapter()
    adapter._sm_staff = [
        {"key": "staff-2", "full_name": "Sahar Ebrahim"},
        {"key": "staff-1", "full_name": "Other Barber"},
    ]
    service = {"staff_keys": ["staff-2", "staff-1"]}

    ordered = adapter._staff_keys_for_service(service, date_iso="2026-07-21")

    assert ordered == ["staff-1", "staff-2"]


def test_prioritize_staff_by_open_calendar_moves_closed_staff_last() -> None:
    adapter = BookingAdapter()

    ordered = adapter._prioritize_staff_by_open_calendar(
        ["staff-sahar", "staff-other", "staff-third"],
        {
            "staff-sahar": [],
            "staff-other": ["10:00 AM"],
            "staff-third": ["11:00 AM"],
        },
    )

    assert ordered == ["staff-other", "staff-third", "staff-sahar"]


def test_setmore_booking_chooses_staff_with_open_requested_slot() -> None:
    adapter = BookingAdapter()

    class FakeSetmore:
        def __init__(self) -> None:
            self.appointment_calls: list[dict] = []

        def get_slots(self, staff_key: str, service_key: str, selected_date: str, timezone: str = "Europe/Copenhagen") -> list[str]:
            if staff_key == "staff-sahar":
                return []
            if staff_key == "staff-other":
                return ["10:00 AM"]
            return []

        def find_customer(self, first_name: str, phone: str = "", email: str = "") -> dict:
            return {"key": "customer-1"}

        def create_customer(self, first_name: str, last_name: str = "", phone: str = "", email: str = "") -> dict:
            return {"key": "customer-1"}

        def create_appointment(
            self,
            staff_key: str,
            service_key: str,
            customer_key: str,
            start_time: str,
            end_time: str,
            comment: str = "",
        ) -> dict:
            self.appointment_calls.append(
                {
                    "staff_key": staff_key,
                    "service_key": service_key,
                    "customer_key": customer_key,
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            return {"key": "appointment-1"}

    fake_setmore = FakeSetmore()
    adapter._setmore = fake_setmore
    adapter._sm_services = [
        {
            "key": "haircut_ladies",
            "service_name": "Ladies Haircut",
            "duration": 30,
            "staff_keys": ["staff-sahar", "staff-other"],
        }
    ]
    adapter._sm_staff = [
        {"key": "staff-sahar", "full_name": "Sahar Ebrahim"},
        {"key": "staff-other", "full_name": "Other Barber"},
    ]
    adapter._ensure_setmore_cache = lambda: None

    response = adapter.create_booking(
        BookingRequest(
            customer_phone="23391178",
            service_id="haircut_ladies",
            start_time="2026-07-20T10:00:00+02:00",
            language="da",
            customer_name="Ali Hassan",
            idempotency_key="test-2",
        )
    )

    assert response.status == "confirmed"
    assert fake_setmore.appointment_calls[0]["staff_key"] == "staff-other"


# ---------------------------------------------------------------------------
# Helper function unit tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("slot,expected", [
    ("10:00 AM", "10:00"),
    ("2:30 PM",  "14:30"),
    ("12:00 PM", "12:00"),
    ("12:00 AM", "00:00"),
    ("9:45 AM",  "09:45"),
    ("10.30",    "10:30"),
    ("09.00",    "09:00"),
])
def test_slot_to_hhmm_parses_various_formats(slot: str, expected: str) -> None:
    assert _slot_to_hhmm(slot) == expected


def test_slot_to_hhmm_returns_none_for_garbage() -> None:
    assert _slot_to_hhmm("not-a-time") is None
    assert _slot_to_hhmm("") is None


@pytest.mark.parametrize("full_name,expected_first,expected_last", [
    ("Ali Hassan",         "Ali",   "Hassan"),
    ("Mehran",             "Mehran", ""),
    ("Maria De La Cruz",   "Maria", "De La Cruz"),
    (None,                 "Guest", ""),
    ("",                   "Guest", ""),
])
def test_split_name_various_inputs(full_name, expected_first, expected_last) -> None:
    first, last = _split_name(full_name)
    assert first == expected_first
    assert last == expected_last


@pytest.mark.parametrize("value,expected", [
    ("Sahar Ebrahim",      "sahar ebrahim"),
    ("  Sahar  Ebrahim  ", "sahar ebrahim"),
    ("SAHAR EBRAHIM",      "sahar ebrahim"),
    ("",                   ""),
])
def test_normalize_person_name(value: str, expected: str) -> None:
    assert _normalize_person_name(value) == expected


@pytest.mark.parametrize("date_iso,expected", [
    ("2026-07-22", "22/07/2026"),
    ("2026-01-05", "05/01/2026"),
    ("2026-12-31", "31/12/2026"),
])
def test_date_iso_to_setmore_slots_format(date_iso: str, expected: str) -> None:
    assert _date_iso_to_setmore_slots(date_iso) == expected


# ---------------------------------------------------------------------------
# _confirmation_text for all supported languages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language,expected_fragment", [
    ("da",    "Din tid er reserveret"),
    ("da-DK", "Din tid er reserveret"),
    ("en",    "Your appointment has been reserved"),
    ("en-GB", "Your appointment has been reserved"),
    ("fr",    "Votre rendez-vous est reserve"),
    ("fr-FR", "Votre rendez-vous est reserve"),
    ("de",    "Ihr Termin wurde fur"),
    ("de-DE", "Ihr Termin wurde fur"),
    ("zh",    "您的预约时间已预留"),
    ("zh-CN", "您的预约时间已预留"),
    ("es",    "Your appointment has been reserved"),  # unknown → English
])
def test_confirmation_text_per_language(language: str, expected_fragment: str) -> None:
    adapter = BookingAdapter()
    result = adapter._confirmation_text(language, "2026-07-27T09:45:00+02:00")
    assert expected_fragment in result
    assert "2026-07-27T09:45:00+02:00" in result


# ---------------------------------------------------------------------------
# Stub service name lookup
# ---------------------------------------------------------------------------

def test_stub_service_name_returns_danish_for_da() -> None:
    adapter = BookingAdapter()
    assert adapter._stub_service_name(
        "herre_klipning", "da") == "Herre Klipning"
    assert adapter._stub_service_name("haircut_ladies", "da") == "Dame Klip"


def test_stub_service_name_returns_english_for_en() -> None:
    adapter = BookingAdapter()
    assert adapter._stub_service_name(
        "herre_klipning", "en") == "Men's Haircut"
    assert adapter._stub_service_name(
        "haircut_ladies", "en") == "Ladies Haircut"


def test_stub_service_name_fallback_for_unknown_id_danish() -> None:
    adapter = BookingAdapter()
    assert adapter._stub_service_name(
        "nonexistent_service", "da") == "Dame Klip"


def test_stub_service_name_fallback_for_unknown_id_english() -> None:
    adapter = BookingAdapter()
    assert adapter._stub_service_name(
        "nonexistent_service", "en") == "Ladies Haircut"


# ---------------------------------------------------------------------------
# Stub booking – confirmation text language
# ---------------------------------------------------------------------------

def test_stub_booking_confirmation_text_is_english_for_en() -> None:
    adapter = BookingAdapter()
    response = adapter.create_booking(BookingRequest(
        customer_phone="23391178",
        service_id="herre_klipning",
        start_time="2026-07-27T09:45:00",
        language="en",
        customer_name="Test User",
        idempotency_key="ct-en",
    ))
    assert "Your appointment has been reserved" in response.confirmation_text


def test_stub_booking_confirmation_text_is_danish_for_da() -> None:
    adapter = BookingAdapter()
    response = adapter.create_booking(BookingRequest(
        customer_phone="23391178",
        service_id="herre_klipning",
        start_time="2026-07-27T09:45:00",
        language="da",
        customer_name="Test User",
        idempotency_key="ct-da",
    ))
    assert "Din tid er reserveret" in response.confirmation_text


def test_stub_booking_returns_stub_booking_id() -> None:
    adapter = BookingAdapter()
    response = adapter.create_booking(BookingRequest(
        customer_phone="23391178",
        service_id="haircut_ladies",
        start_time="2026-07-27T10:00:00",
        language="en",
        idempotency_key="bid-test",
    ))
    assert response.booking_id == "stub-booking-001"
    assert response.status == "confirmed"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------

def test_stub_confirm_cancellation_returns_canceled_status() -> None:
    adapter = BookingAdapter()
    result = adapter.confirm_cancellation("stub-booking-001")
    assert result.status == "canceled"
    assert "stub-booking-001" in result.cancellation_reference
    assert result.message == "Booking canceled."


def test_verify_cancellation_with_no_fields_returns_not_verified() -> None:
    adapter = BookingAdapter()
    result = adapter.verify_cancellation(CancelVerifyRequest(
        customer_phone="23391178",
    ))
    assert result.verified is False
    assert "booking_reference" in result.message.lower(
    ) or "service_id" in result.message.lower()


def test_verify_cancellation_stub_with_reference_returns_verified() -> None:
    adapter = BookingAdapter()
    result = adapter.verify_cancellation(CancelVerifyRequest(
        customer_phone="23391178",
        booking_reference="stub-booking-001",
    ))
    assert result.verified is True
    assert result.booking is not None
    assert result.booking.booking_id == "stub-booking-001"


def test_setmore_confirm_cancellation_returns_call_salon_message() -> None:
    adapter = BookingAdapter()
    adapter._setmore = object()  # type: ignore[assignment]
    result = adapter.confirm_cancellation("appt-key-123")
    assert result.status == "canceled"
    assert "+45 41 42 33 33" in result.message
    assert "cancel-appt-key-123" == result.cancellation_reference


# ---------------------------------------------------------------------------
# Cache TTL – no unnecessary reload within the same window
# ---------------------------------------------------------------------------

def test_catalog_cache_does_not_reload_within_ttl(monkeypatch) -> None:
    adapter = BookingAdapter()
    copenhagen_offset = timezone(timedelta(hours=2))
    load_calls = {"count": 0}

    def fake_now() -> datetime:
        return datetime(2026, 7, 22, 10, 0, tzinfo=copenhagen_offset)

    def fake_load() -> list[dict]:
        load_calls["count"] += 1
        return [{"service_id": "x", "name_da": "X", "name_en": "X", "duration_minutes": 15, "price_label": "kr 1"}]

    monkeypatch.setattr(adapter, "_now_in_copenhagen", fake_now)
    monkeypatch.setattr(adapter, "_load_catalog_source", fake_load)

    for _ in range(5):
        adapter.list_services(language="da")

    assert load_calls["count"] == 1


# ---------------------------------------------------------------------------
# _staff_is_preferred – various name key shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("staff_dict", [
    {"full_name": "Sahar Ebrahim"},
    {"name": "Sahar Ebrahim"},
    {"staff_name": "Sahar Ebrahim"},
    {"first_name": "Sahar", "last_name": "Ebrahim"},
])
def test_staff_is_preferred_recognises_sahar_in_all_name_shapes(staff_dict: dict) -> None:
    adapter = BookingAdapter()
    assert adapter._staff_is_preferred(staff_dict) is True


def test_staff_is_preferred_returns_false_for_other_staff() -> None:
    adapter = BookingAdapter()
    assert adapter._staff_is_preferred({"full_name": "Other Barber"}) is False


def test_preferred_staff_key_returns_none_for_empty_candidates() -> None:
    adapter = BookingAdapter()
    adapter._sm_staff = [{"key": "s1", "full_name": "Sahar Ebrahim"}]
    assert adapter._preferred_staff_key([]) is None


def test_staff_keys_for_service_falls_back_to_first_staff_when_no_keys() -> None:
    adapter = BookingAdapter()
    adapter._sm_staff = [{"key": "staff-1"}, {"key": "staff-2"}]
    service = {"staff_keys": []}

    keys = adapter._staff_keys_for_service(service, date_iso=None)

    assert keys == ["staff-1"]


# ---------------------------------------------------------------------------
# get_availability – both slots filtered when after both today
# ---------------------------------------------------------------------------

def test_get_availability_returns_empty_when_all_slots_past(monkeypatch) -> None:
    adapter = BookingAdapter()
    copenhagen_offset = timezone(timedelta(hours=2))
    now = datetime(2026, 7, 22, 14, 0, tzinfo=copenhagen_offset)
    monkeypatch.setattr(adapter, "_now_in_copenhagen", lambda: now)

    response = adapter.get_availability(
        service_id="herre_klipning", date="2026-07-22")

    assert response.slots == []
