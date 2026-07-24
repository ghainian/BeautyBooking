"""Tests for service-name translation in booking_adapter.

Covers the feature that maps Danish Setmore names → English (or raw fallback)
for non-Danish language requests, and verifies stub-mode also returns correct
names per language.
"""

import pytest

from app.booking_adapter import BookingAdapter, _STUB_CATALOG
from app.booking_models import BookingRequest


@pytest.fixture(autouse=True)
def _force_stub_mode(monkeypatch) -> None:
    monkeypatch.delenv("SETMORE_REFRESH_TOKEN", raising=False)


# ---------------------------------------------------------------------------
# Setmore path – _map_setmore_services
# ---------------------------------------------------------------------------

def _adapter_with_setmore_services(services: list[dict]) -> BookingAdapter:
    """Return a stub-free adapter wired with fake Setmore state."""
    adapter = BookingAdapter()
    adapter._sm_services = services
    adapter._sm_staff = []
    adapter._ensure_setmore_cache = lambda: None  # type: ignore[method-assign]
    # Force Setmore path by pretending _setmore is truthy
    adapter._setmore = object()  # type: ignore[assignment]
    return adapter


def test_setmore_services_returns_danish_names_for_da_language() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Herre Klipning",
            "cost": 180, "currency": "DKK", "duration": 15},
        {"key": "svc-2", "service_name": "Dame Klip",
            "cost": 300, "currency": "DKK", "duration": 30},
    ])

    services = adapter._map_setmore_services("da")

    assert [s.name for s in services] == ["Herre Klipning", "Dame Klip"]


def test_setmore_services_returns_english_names_for_en_language() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Herre Klipning",
            "cost": 180, "currency": "DKK", "duration": 15},
        {"key": "svc-2", "service_name": "Dame Klip",
            "cost": 300, "currency": "DKK", "duration": 30},
        {"key": "svc-3", "service_name": "Borne Klip",
            "cost": 140, "currency": "DKK", "duration": 15},
    ])

    services = adapter._map_setmore_services("en")

    assert [s.name for s in services] == [
        "Men's Haircut", "Ladies Haircut", "Children's Haircut"]


def test_setmore_services_returns_english_names_for_fr_language() -> None:
    """French and other non-da languages should receive English names (LLM translates further)."""
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Herre Klipning",
            "cost": 180, "currency": "DKK", "duration": 15},
    ])

    services = adapter._map_setmore_services("fr")

    assert services[0].name == "Men's Haircut"


def test_setmore_services_returns_english_names_for_de_language() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Bund farve",
            "cost": 450, "currency": "DKK", "duration": 45},
    ])

    services = adapter._map_setmore_services("de")

    assert services[0].name == "Root Color"


def test_setmore_services_falls_back_to_raw_name_when_not_in_catalog() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-x", "service_name": "Speciel Behandling",
            "cost": 500, "currency": "DKK", "duration": 60},
    ])

    services = adapter._map_setmore_services("en")

    assert services[0].name == "Speciel Behandling"


def test_setmore_services_name_lookup_is_case_insensitive() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "HERRE KLIPNING",
            "cost": 180, "currency": "DKK", "duration": 15},
    ])

    services = adapter._map_setmore_services("en")

    assert services[0].name == "Men's Haircut"


def test_setmore_services_preserves_price_and_duration() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Herre Klipning",
            "cost": 200, "currency": "DKK", "duration": 20},
    ])

    services = adapter._map_setmore_services("en")

    assert services[0].price_label == "kr 200"
    assert services[0].duration_minutes == 20


def test_setmore_services_handles_non_dkk_currency() -> None:
    adapter = _adapter_with_setmore_services([
        {"key": "svc-1", "service_name": "Herre Klipning",
            "cost": 25, "currency": "EUR", "duration": 15},
    ])

    services = adapter._map_setmore_services("en")

    assert services[0].price_label == "25 EUR"


def test_setmore_services_returns_empty_for_empty_service_list() -> None:
    adapter = _adapter_with_setmore_services([])

    services = adapter._map_setmore_services("en")

    assert services == []


# ---------------------------------------------------------------------------
# Stub path – _map_stub_services
# ---------------------------------------------------------------------------

def test_stub_services_returns_danish_names_for_da() -> None:
    adapter = BookingAdapter()
    services = adapter.list_services(language="da")

    assert services[0].name == "Herre Klipning"
    assert services[6].name == "Dame Klip"


def test_stub_services_returns_english_names_for_en() -> None:
    adapter = BookingAdapter()
    services = adapter.list_services(language="en")

    assert services[0].name == "Men's Haircut"
    assert services[6].name == "Ladies Haircut"


def test_stub_services_returns_english_names_for_non_da_language() -> None:
    """Any language other than da should receive English names."""
    adapter = BookingAdapter()
    for lang in ("fr", "de", "zh", "es", "ar"):
        services = adapter.list_services(language=lang)
        assert services[0].name == "Men's Haircut", f"Failed for language={lang}"


def test_stub_services_name_covers_full_catalog() -> None:
    """Every entry in _STUB_CATALOG must have non-empty da and en names."""
    for item in _STUB_CATALOG:
        assert item["name_da"].strip(
        ), f"Empty name_da for {item['service_id']}"
        assert item["name_en"].strip(
        ), f"Empty name_en for {item['service_id']}"


# ---------------------------------------------------------------------------
# get_price_overview translations
# ---------------------------------------------------------------------------

def test_price_overview_english_uses_english_service_names() -> None:
    adapter = BookingAdapter()
    overview = adapter.get_price_overview(language="en")

    assert "Here are the prices" in overview
    assert "Men's Haircut" in overview
    assert "Ladies Haircut" in overview
    assert "Herre Klipning" not in overview


def test_price_overview_danish_uses_danish_service_names() -> None:
    adapter = BookingAdapter()
    overview = adapter.get_price_overview(language="da")

    assert "Her er priserne" in overview
    assert "Herre Klipning" in overview
    assert "Dame Klip" in overview


def test_price_overview_french_prefix() -> None:
    adapter = BookingAdapter()
    overview = adapter.get_price_overview(language="fr")

    assert overview.startswith("Voici les prix")


def test_price_overview_german_prefix() -> None:
    adapter = BookingAdapter()
    overview = adapter.get_price_overview(language="de")

    assert overview.startswith("Hier sind die Preise")


def test_price_overview_chinese_prefix() -> None:
    adapter = BookingAdapter()
    overview = adapter.get_price_overview(language="zh")

    assert overview.startswith("以下是预约页面上的价格")


# ---------------------------------------------------------------------------
# Stub booking – service_name in confirmation
# ---------------------------------------------------------------------------

def test_stub_booking_service_name_is_english_when_language_en() -> None:
    adapter = BookingAdapter()
    response = adapter.create_booking(BookingRequest(
        customer_phone="23391178",
        service_id="herre_klipning",
        start_time="2026-07-27T09:45:00",
        language="en",
        customer_name="Test User",
        idempotency_key="trans-test-1",
    ))

    assert response.service_name == "Men's Haircut"


def test_stub_booking_service_name_is_danish_when_language_da() -> None:
    adapter = BookingAdapter()
    response = adapter.create_booking(BookingRequest(
        customer_phone="23391178",
        service_id="herre_klipning",
        start_time="2026-07-27T09:45:00",
        language="da",
        customer_name="Test User",
        idempotency_key="trans-test-2",
    ))

    assert response.service_name == "Herre Klipning"
