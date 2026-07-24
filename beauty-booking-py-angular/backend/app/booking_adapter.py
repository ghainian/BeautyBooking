from datetime import datetime, timedelta

from .booking_models import (
    AvailabilityResponse,
    AvailabilitySlot,
    BookingRequest,
    BookingResponse,
    CancelConfirmResponse,
    CancelVerifyRequest,
    CancelVerifyResponse,
    CancellationCandidate,
    ServiceSummary,
)


CATALOG_SOURCE = [
    {
        "service_id": "herre_klipning",
        "name_da": "Herre Klipning",
        "name_en": "Men's Haircut",
        "duration_minutes": 15,
        "price_label": "kr 180",
    },
    {
        "service_id": "herre_klip_fade",
        "name_da": "Herre klip Fade",
        "name_en": "Men's Fade Haircut",
        "duration_minutes": 15,
        "price_label": "kr 180",
    },
    {
        "service_id": "herre_klip_tape_fade",
        "name_da": "Herre Klip Tape Fade",
        "name_en": "Men's Tape Fade Haircut",
        "duration_minutes": 20,
        "price_label": "kr 180",
    },
    {
        "service_id": "herre_klip_mullet_fade",
        "name_da": "Herre Klip Mullet Fade",
        "name_en": "Men's Mullet Fade Haircut",
        "duration_minutes": 20,
        "price_label": "kr 180",
    },
    {
        "service_id": "borne_klip",
        "name_da": "Borne Klip",
        "name_en": "Children's Haircut",
        "duration_minutes": 15,
        "price_label": "kr 140",
    },
    {
        "service_id": "herre_pensionist",
        "name_da": "Herre Pensionist",
        "name_en": "Men's Senior Haircut",
        "duration_minutes": 15,
        "price_label": "kr 140",
    },
    {
        "service_id": "haircut_ladies",
        "name_da": "Dame Klip",
        "name_en": "Ladies Haircut",
        "duration_minutes": 30,
        "price_label": "kr 300",
    },
    {
        "service_id": "dame_vask_og_klip",
        "name_da": "Dame: vask og klip",
        "name_en": "Ladies: Wash and Haircut",
        "duration_minutes": 30,
        "price_label": "kr 350",
    },
    {
        "service_id": "dame_pandehar_klipning",
        "name_da": "Dame: pandehar klipning",
        "name_en": "Ladies: Bang Trim",
        "duration_minutes": 15,
        "price_label": "kr 100",
    },
    {
        "service_id": "bund_farve",
        "name_da": "Bund farve",
        "name_en": "Root Color",
        "duration_minutes": 45,
        "price_label": "kr 450",
    },
    {
        "service_id": "farve_kort_har",
        "name_da": "Farve kort har",
        "name_en": "Color Short Hair",
        "duration_minutes": 60,
        "price_label": "kr 550",
    },
    {
        "service_id": "farve_lang_har",
        "name_da": "Farve lang har",
        "name_en": "Color Long Hair",
        "duration_minutes": 125,
        "price_label": "kr 900",
    },
    {
        "service_id": "striber_kort_har",
        "name_da": "Striber kort har",
        "name_en": "Highlights Short Hair",
        "duration_minutes": 90,
        "price_label": "kr 680",
    },
]


class BookingAdapter:
    """Temporary adapter contract for the launch booking provider.

    Keep all booking-provider specifics in this class so route handlers stay stable
    when the implementation switches from stub data to a real API client.
    """

    def __init__(self) -> None:
        self._catalog_cache: list[dict] = []
        self._catalog_cached_at: datetime | None = None
        self._next_cache_refresh_at: datetime | None = None

    def list_services(self, language: str) -> list[ServiceSummary]:
        self._refresh_catalog_if_needed()
        use_danish = language.startswith("da")
        return [
            ServiceSummary(
                service_id=item["service_id"],
                name=item["name_da"] if use_danish else item["name_en"],
                duration_minutes=item["duration_minutes"],
                price_label=item["price_label"],
                language=language,
            )
            for item in self._catalog_cache
        ]

    def get_price_overview(self, language: str) -> str:
        services = self.list_services(language=language)
        joined_prices = "; ".join(
            f"{service.name}: {service.price_label}" for service in services
        )
        if language.startswith("da"):
            return f"Her er priserne fra bookingsiden: {joined_prices}."
        if language.startswith("fr"):
            return f"Voici les prix de la page de reservation : {joined_prices}."
        if language.startswith("de"):
            return f"Hier sind die Preise von der Buchungsseite: {joined_prices}."
        if language.startswith("zh"):
            return f"以下是预约页面上的价格：{joined_prices}。"
        return f"Here are the prices from the booking page: {joined_prices}."

    def get_availability(self, service_id: str, date: str) -> AvailabilityResponse:
        # Deterministic slots make contract tests stable while integration is pending.
        return AvailabilityResponse(
            service_id=service_id,
            date=date,
            slots=[
                AvailabilitySlot(start_time=f"{date}T10:00:00+02:00"),
                AvailabilitySlot(start_time=f"{date}T13:00:00+02:00"),
            ],
        )

    def create_booking(self, request: BookingRequest) -> BookingResponse:
        self._refresh_catalog_if_needed()
        service_name = self._service_name_for_id(
            service_id=request.service_id,
            language=request.language,
        )
        confirmation_text = (
            f"Din tid er reserveret {request.start_time}."
            if request.language.startswith("da")
            else (
                f"Votre rendez-vous est reserve pour {request.start_time}."
                if request.language.startswith("fr")
                else (
                    f"Ihr Termin wurde fur {request.start_time} reserviert."
                    if request.language.startswith("de")
                    else (
                        f"您的预约时间已预留：{request.start_time}。"
                        if request.language.startswith("zh")
                        else f"Your appointment has been reserved for {request.start_time}."
                    )
                )
            )
        )
        return BookingResponse(
            status="confirmed",
            booking_id="stub-booking-001",
            service_name=service_name,
            start_time=request.start_time,
            confirmation_text=confirmation_text,
        )

    def verify_cancellation(self, request: CancelVerifyRequest) -> CancelVerifyResponse:
        if not request.booking_reference and not (request.service_id and request.start_time):
            return CancelVerifyResponse(
                verified=False,
                message="Provide booking_reference or service_id with start_time.",
            )

        language = "da"
        if request.service_id and request.service_id != "haircut_ladies":
            language = "en"

        return CancelVerifyResponse(
            verified=True,
            booking=CancellationCandidate(
                booking_id=request.booking_reference or "stub-booking-001",
                service_name=self._service_name_for_id(
                    service_id=request.service_id or "haircut_ladies",
                    language=language,
                ),
                start_time=request.start_time or "2026-07-08T13:00:00+02:00",
            ),
        )

    def confirm_cancellation(self, booking_id: str) -> CancelConfirmResponse:
        return CancelConfirmResponse(
            status="canceled",
            cancellation_reference=f"cancel-{booking_id}",
            message="Booking canceled.",
        )

    def _refresh_catalog_if_needed(self) -> None:
        now = self._now_in_copenhagen()
        should_refresh = (
            not self._catalog_cache
            or self._next_cache_refresh_at is None
            or now >= self._next_cache_refresh_at
        )
        if not should_refresh:
            return

        self._catalog_cache = list(self._load_catalog_source())
        self._catalog_cached_at = now
        self._next_cache_refresh_at = self._compute_next_sunday_morning(now)

    def _load_catalog_source(self) -> list[dict]:
        return CATALOG_SOURCE

    def _service_name_for_id(self, service_id: str, language: str) -> str:
        self._refresh_catalog_if_needed()
        use_danish = language.startswith("da")
        for item in self._catalog_cache:
            if item["service_id"] == service_id:
                return item["name_da"] if use_danish else item["name_en"]
        return "Dame Klip" if use_danish else "Ladies Haircut"

    def _now_in_copenhagen(self) -> datetime:
        return datetime.now().astimezone()

    def _compute_next_sunday_morning(self, now: datetime) -> datetime:
        days_until_sunday = (6 - now.weekday()) % 7
        next_refresh = now.replace(
            hour=8, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
        if next_refresh <= now:
            next_refresh = next_refresh + timedelta(days=7)
        return next_refresh
