from datetime import datetime, timedelta, timezone

from app.booking_adapter import BookingAdapter


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
