"""Tests for date-range validation in booking tools and phone-verified cancellation.

All tests run against the stub BookingAdapter (no SETMORE_REFRESH_TOKEN) and
drive the dispatch table returned by _build_dispatch() directly — no LLM calls.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from app.booking_adapter import BookingAdapter
from app.booking_models import BookingRequest
from app.foundry_agent import _build_dispatch


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _force_stub_mode(monkeypatch) -> None:
    monkeypatch.delenv("SETMORE_REFRESH_TOKEN", raising=False)


@pytest.fixture()
def dispatch():
    return _build_dispatch(BookingAdapter())


@pytest.fixture()
def adapter():
    return BookingAdapter()


@pytest.fixture()
def dispatch_with_adapter(adapter):
    return _build_dispatch(adapter), adapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def today_iso() -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        return datetime.now(ZoneInfo("Europe/Copenhagen")).date().isoformat()
    except Exception:
        return date.today().isoformat()


def days_from_today(n: int) -> str:
    return (date.fromisoformat(today_iso()) + timedelta(days=n)).isoformat()


# ===========================================================================
# DATE VALIDATION — get_availability
# ===========================================================================

class TestGetAvailabilityDateValidation:

    def test_rejects_clearly_past_date(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", "2020-01-01"))
        assert result.get("error") == "past_date"
        assert "past" in result["message"].lower()

    def test_rejects_yesterday(self, dispatch):
        yesterday = days_from_today(-1)
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", yesterday))
        assert result.get("error") == "past_date"

    def test_accepts_today(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", today_iso()))
        # Should return available_times (even if empty after filtering) — no error
        assert "error" not in result
        assert "available_times" in result

    def test_accepts_tomorrow(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", days_from_today(1)))
        assert "error" not in result
        assert "available_times" in result

    def test_accepts_31_days_from_today(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", days_from_today(31)))
        assert "error" not in result

    def test_rejects_32_days_from_today(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", days_from_today(32)))
        assert result.get("error") == "too_far_future"
        assert "31" in result["message"] or "month" in result["message"].lower(
        )

    def test_rejects_one_year_ahead(self, dispatch):
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", days_from_today(365)))
        assert result.get("error") == "too_far_future"


# ===========================================================================
# DATE VALIDATION — get_staff_availability
# ===========================================================================

class TestGetStaffAvailabilityDateValidation:

    def test_rejects_past_date(self, dispatch):
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", "2020-06-15"))
        assert result.get("error") == "past_date"

    def test_rejects_too_far_future(self, dispatch):
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", days_from_today(45)))
        assert result.get("error") == "too_far_future"

    def test_accepts_valid_date(self, dispatch):
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", days_from_today(3)))
        # Stub returns {"Sahar Ebrahim": [...]} — no error key
        assert "error" not in result


# ===========================================================================
# DATE VALIDATION — create_booking
# ===========================================================================

class TestCreateBookingDateValidation:

    def test_rejects_past_date(self, dispatch):
        result = json.loads(dispatch["create_booking"](
            service_id="herre_klipning",
            date="2020-03-10",
            time="10:00",
            phone="23391178",
        ))
        assert result.get("error") == "past_date"

    def test_rejects_too_far_future(self, dispatch):
        result = json.loads(dispatch["create_booking"](
            service_id="herre_klipning",
            date=days_from_today(60),
            time="10:00",
            phone="23391178",
        ))
        assert result.get("error") == "too_far_future"

    def test_accepts_valid_future_date(self, dispatch_with_adapter):
        dispatch, _ = dispatch_with_adapter
        result = json.loads(dispatch["create_booking"](
            service_id="herre_klipning",
            date=days_from_today(2),
            time="10:00",
            phone="23391178",
            language="en",
            customer_name="Test User",
        ))
        assert "error" not in result
        assert result.get("status") == "confirmed"

    def test_accepts_tomorrow(self, dispatch_with_adapter):
        dispatch, _ = dispatch_with_adapter
        result = json.loads(dispatch["create_booking"](
            service_id="haircut_ladies",
            date=days_from_today(1),
            time="13:00",
            phone="23391178",
            language="da",
        ))
        assert "error" not in result
        assert result.get("status") == "confirmed"

    def test_booking_response_includes_staff_name(self, dispatch_with_adapter):
        dispatch, _ = dispatch_with_adapter
        result = json.loads(dispatch["create_booking"](
            service_id="herre_klipning",
            date=days_from_today(2),
            time="10:00",
            phone="23391178",
            staff_name="Sahar",
        ))
        assert "error" not in result
        assert result.get("staff_name") is not None


# ===========================================================================
# CANCELLATION — phone verification
# ===========================================================================

class TestCancellationPhoneVerification:

    def _book(self, dispatch, adapter, phone: str = "23391178") -> str:
        """Create a stub booking and return its booking_id."""
        result = json.loads(dispatch["create_booking"](
            service_id="herre_klipning",
            date=days_from_today(2),
            time="10:00",
            phone=phone,
            language="en",
            customer_name="Test User",
        ))
        assert result.get("status") == "confirmed"
        return result["booking_id"]

    def test_cancel_succeeds_with_correct_phone(self, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        booking_id = self._book(dispatch, adapter, phone="23391178")

        result = json.loads(dispatch["cancel_booking"](
            booking_reference=booking_id,
            customer_phone="23391178",
        ))
        assert "error" not in result
        assert result.get("status") == "canceled"

    def test_cancel_succeeds_with_correct_phone_formatted_differently(self, dispatch_with_adapter):
        """Phone numbers with spaces/plus should match stripped versions."""
        dispatch, adapter = dispatch_with_adapter
        booking_id = self._book(dispatch, adapter, phone="+45 23 39 11 78")

        result = json.loads(dispatch["cancel_booking"](
            booking_reference=booking_id,
            customer_phone="4523391178",
        ))
        assert "error" not in result
        assert result.get("status") == "canceled"

    def test_cancel_fails_with_wrong_phone(self, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        booking_id = self._book(dispatch, adapter, phone="23391178")

        result = json.loads(dispatch["cancel_booking"](
            booking_reference=booking_id,
            customer_phone="99999999",
        ))
        assert result.get("error") == "phone_mismatch"
        assert "does not match" in result["message"].lower()

    def test_cancel_fails_with_empty_wrong_phone(self, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        booking_id = self._book(dispatch, adapter, phone="23391178")

        # Completely wrong number
        result = json.loads(dispatch["cancel_booking"](
            booking_reference=booking_id,
            customer_phone="11111111",
        ))
        assert result.get("error") == "phone_mismatch"

    def test_cancel_without_phone_still_proceeds(self, dispatch_with_adapter):
        """If no phone is provided (empty), verification is skipped."""
        dispatch, adapter = dispatch_with_adapter
        self._book(dispatch, adapter, phone="23391178")

        result = json.loads(dispatch["cancel_booking"](
            booking_reference="stub-booking-001",
            customer_phone="",
        ))
        # No phone → no check → proceeds to cancellation
        assert "error" not in result
        assert result.get("status") == "canceled"

    def test_cancel_unknown_booking_still_reports_canceled(self, dispatch_with_adapter):
        """For unknown references (no stored phone), verification skips and cancels."""
        dispatch, _ = dispatch_with_adapter
        result = json.loads(dispatch["cancel_booking"](
            booking_reference="unknown-ref-xyz",
            customer_phone="23391178",
        ))
        # Stub always returns verified=True for unknown refs (no stored phone to compare)
        assert result.get("status") == "canceled"


# ===========================================================================
# BOUNDARY: exact 31-day limit
# ===========================================================================

class TestDateBoundary:

    @pytest.mark.parametrize("days,should_pass", [
        (0,  True),   # today
        (1,  True),   # tomorrow
        (30, True),   # 30 days out
        (31, True),   # exactly 31 days — still allowed
        (32, False),  # 32 days — over limit
        (90, False),  # 3 months out
    ])
    def test_boundary_days(self, dispatch, days: int, should_pass: bool) -> None:
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", days_from_today(days)))
        if should_pass:
            assert "error" not in result, f"Expected no error for {days} days ahead, got {result}"
        else:
            assert result.get("error") == "too_far_future", (
                f"Expected too_far_future for {days} days ahead, got {result}"
            )


# ===========================================================================
# PAST-TIME FILTERING — stub adapter (get_availability dispatch)
# ===========================================================================

class TestPastTimeFilteringDispatch:
    """Tests that the dispatch-level get_availability strips past slots for today."""

    def test_today_all_slots_future_returns_slots(self, monkeypatch, dispatch_with_adapter):
        """When it's early morning, today's slots should all be present."""
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        # 08:00 Copenhagen — both 10:00 and 13:00 are in the future
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 8, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        assert "10:00" in result["available_times"]
        assert "13:00" in result["available_times"]

    def test_today_past_noon_filters_morning_slot(self, monkeypatch, dispatch_with_adapter):
        """After 11:00, the 10:00 stub slot must be removed."""
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 11, 10, tzinfo=cph_offset))
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        assert "10:00" not in result["available_times"]
        assert "13:00" in result["available_times"]

    def test_today_after_all_slots_returns_empty(self, monkeypatch, dispatch_with_adapter):
        """After 14:00, both stub slots have passed — empty list expected."""
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 14, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        assert result["available_times"] == []

    def test_future_date_returns_all_slots(self, monkeypatch, dispatch_with_adapter):
        """For a future date, no time filtering should occur."""
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 14, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_availability"](
            "herre_klipning", "2026-07-26"))
        assert "error" not in result
        assert "10:00" in result["available_times"]
        assert "13:00" in result["available_times"]


# ===========================================================================
# PAST-TIME FILTERING — stub adapter (get_staff_availability dispatch)
# ===========================================================================

class TestPastTimeFilteringStaffDispatch:

    def test_today_early_morning_returns_all_staff_slots(self, monkeypatch, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 8, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        slots = list(result.values())[0]
        assert "10:00" in slots
        assert "13:00" in slots

    def test_today_after_10_hides_past_slot(self, monkeypatch, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 11, 30, tzinfo=cph_offset))
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        if result:  # may be empty dict if all slots filtered
            slots = list(result.values())[0]
            assert "10:00" not in slots
            assert "13:00" in slots

    def test_today_all_slots_past_returns_empty_dict(self, monkeypatch, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 14, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", "2026-07-25"))
        assert "error" not in result
        assert result == {}

    def test_future_date_not_filtered(self, monkeypatch, dispatch_with_adapter):
        dispatch, adapter = dispatch_with_adapter
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 17, 0, tzinfo=cph_offset))
        result = json.loads(dispatch["get_staff_availability"](
            "herre_klipning", "2026-07-26"))
        assert "error" not in result
        assert result  # non-empty
        slots = list(result.values())[0]
        assert "10:00" in slots
        assert "13:00" in slots


# ===========================================================================
# PAST-TIME FILTERING — adapter directly (_stub_staff_availability_detail)
# ===========================================================================

class TestStubStaffAvailabilityDetailFiltering:

    def test_before_first_slot_returns_both(self, monkeypatch):
        adapter = BookingAdapter()
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 9, 0, tzinfo=cph_offset))
        result = adapter._stub_staff_availability_detail("2026-07-25")
        assert result  # not empty
        slots = list(result.values())[0]
        assert "10:00" in slots
        assert "13:00" in slots

    def test_between_slots_returns_only_second(self, monkeypatch):
        adapter = BookingAdapter()
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 12, 0, tzinfo=cph_offset))
        result = adapter._stub_staff_availability_detail("2026-07-25")
        assert result
        slots = list(result.values())[0]
        assert "10:00" not in slots
        assert "13:00" in slots

    def test_after_both_slots_returns_empty_dict(self, monkeypatch):
        adapter = BookingAdapter()
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 15, 0, tzinfo=cph_offset))
        result = adapter._stub_staff_availability_detail("2026-07-25")
        assert result == {}

    def test_future_date_not_filtered(self, monkeypatch):
        adapter = BookingAdapter()
        from datetime import datetime, timezone, timedelta
        cph_offset = timezone(timedelta(hours=2))
        monkeypatch.setattr(adapter, "_now_in_copenhagen",
                            lambda: datetime(2026, 7, 25, 23, 59, tzinfo=cph_offset))
        result = adapter._stub_staff_availability_detail("2026-07-26")
        assert result
        slots = list(result.values())[0]
        assert "10:00" in slots
        assert "13:00" in slots
