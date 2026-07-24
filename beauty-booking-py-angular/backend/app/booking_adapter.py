"""Booking adapter: routes calls to the Setmore API when credentials are present,
otherwise falls back to deterministic stub data (used by unit tests).

Environment variable
--------------------
SETMORE_REFRESH_TOKEN
    When set the adapter connects to the live Setmore account.
    When absent the adapter returns hardcoded stub data so tests remain stable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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

logger = logging.getLogger(__name__)

_PREFERRED_STAFF_NAME = "sahar ebrahim"
# matches when only first_name is stored
_PREFERRED_STAFF_FIRST_NAME = "sahar"
_MONDAY_WEEKDAY = 0

# ---------------------------------------------------------------------------
# Stub catalogue – kept as fallback when Setmore is not configured
# ---------------------------------------------------------------------------

_STUB_CATALOG: list[dict] = [
    {"service_id": "herre_klipning",        "name_da": "Herre Klipning",
        "name_en": "Men's Haircut",             "duration_minutes": 15,  "price_label": "kr 180"},
    {"service_id": "herre_klip_fade",       "name_da": "Herre klip Fade",
        "name_en": "Men's Fade Haircut",        "duration_minutes": 15,  "price_label": "kr 180"},
    {"service_id": "herre_klip_tape_fade",  "name_da": "Herre Klip Tape Fade",
        "name_en": "Men's Tape Fade Haircut",   "duration_minutes": 20,  "price_label": "kr 180"},
    {"service_id": "herre_klip_mullet_fade", "name_da": "Herre Klip Mullet Fade",
        "name_en": "Men's Mullet Fade Haircut", "duration_minutes": 20,  "price_label": "kr 180"},
    {"service_id": "borne_klip",            "name_da": "Borne Klip",
        "name_en": "Children's Haircut",        "duration_minutes": 15,  "price_label": "kr 140"},
    {"service_id": "herre_pensionist",      "name_da": "Herre Pensionist",
        "name_en": "Men's Senior Haircut",      "duration_minutes": 15,  "price_label": "kr 140"},
    {"service_id": "haircut_ladies",        "name_da": "Dame Klip",
        "name_en": "Ladies Haircut",            "duration_minutes": 30,  "price_label": "kr 300"},
    {"service_id": "dame_vask_og_klip",     "name_da": "Dame: vask og klip",
        "name_en": "Ladies: Wash and Haircut",  "duration_minutes": 30,  "price_label": "kr 350"},
    {"service_id": "dame_pandehar_klipning", "name_da": "Dame: pandehar klipning",
        "name_en": "Ladies: Bang Trim",         "duration_minutes": 15,  "price_label": "kr 100"},
    {"service_id": "bund_farve",            "name_da": "Bund farve",
        "name_en": "Root Color",                "duration_minutes": 45,  "price_label": "kr 450"},
    {"service_id": "farve_kort_har",        "name_da": "Farve kort har",
        "name_en": "Color Short Hair",          "duration_minutes": 60,  "price_label": "kr 550"},
    {"service_id": "farve_lang_har",        "name_da": "Farve lang har",
        "name_en": "Color Long Hair",           "duration_minutes": 125, "price_label": "kr 900"},
    {"service_id": "striber_kort_har",      "name_da": "Striber kort har",
        "name_en": "Highlights Short Hair",     "duration_minutes": 90,  "price_label": "kr 680"},
]

# Alias kept for any code that imports CATALOG_SOURCE directly.
CATALOG_SOURCE = _STUB_CATALOG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_price(cost: int | float, currency: str) -> str:
    """Format a Setmore cost+currency pair into a human-readable price label."""
    if currency.upper() in ("DKK", "KR"):
        return f"kr {int(cost)}"
    return f"{int(cost)} {currency}"


def _iso_to_setmore_utc(iso: str) -> str:
    """Convert to Setmore payload format while preserving Copenhagen wall-clock time.

    The Setmore account is configured for Copenhagen local time, and payloads with
    UTC-converted values can shift bookings by 1-2 hours. We therefore normalize
    to Copenhagen first and keep that local clock value in the outgoing timestamp.
    """
    dt_local = _as_copenhagen_datetime(iso)
    return dt_local.strftime("%Y-%m-%dT%H:%MZ")


def _as_copenhagen_datetime(iso: str) -> datetime:
    """Parse an ISO datetime and normalize it to Europe/Copenhagen."""
    dt = datetime.fromisoformat(iso)
    try:
        copenhagen_tz = ZoneInfo("Europe/Copenhagen")
        if dt.tzinfo is None:
            return dt.replace(tzinfo=copenhagen_tz)
        return dt.astimezone(copenhagen_tz)
    except Exception:  # noqa: BLE001
        # If IANA tzdata is unavailable (common on some Windows installs),
        # preserve explicit offsets from input to avoid accidental hour shifts.
        if dt.tzinfo is not None:
            return dt
        local_tz = datetime.now().astimezone().tzinfo or timezone.utc
        return dt.replace(tzinfo=local_tz)


def _setmore_slot_to_iso(date_iso: str, slot: str) -> str:
    """Convert a Setmore slot string and a date ('YYYY-MM-DD') to ISO datetime.

    Handles both the documented format ('10.30') and the actual API format
    ('10:00 AM', '2:30 PM').
    """
    slot = slot.strip()
    if " AM" in slot.upper() or " PM" in slot.upper():
        # 12-hour clock format returned by the live API
        t = datetime.strptime(slot.upper(), "%I:%M %p")
        time_part = t.strftime("%H:%M")
    else:
        # Documented format: "10.30" or already "10:30"
        time_part = slot.replace(".", ":")
    return f"{date_iso}T{time_part}:00"


def _date_iso_to_setmore_slots(date_iso: str) -> str:
    """Convert 'YYYY-MM-DD' → 'DD/MM/YYYY' (Setmore slot-request format)."""
    y, m, d = date_iso.split("-")
    return f"{d}/{m}/{y}"


def _split_name(full_name: str | None) -> tuple[str, str]:
    """Split a full name into (first_name, last_name)."""
    if not full_name:
        return ("Guest", "")
    parts = full_name.strip().split(" ", 1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def _normalize_person_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _slot_to_hhmm(slot: str) -> str | None:
    """Normalize Setmore slot strings to HH:MM for matching."""
    value = (slot or "").strip()
    if not value:
        return None
    try:
        if " AM" in value.upper() or " PM" in value.upper():
            parsed = datetime.strptime(value.upper(), "%I:%M %p")
            return parsed.strftime("%H:%M")
        return datetime.strptime(value.replace(".", ":"), "%H:%M").strftime("%H:%M")
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# BookingAdapter
# ---------------------------------------------------------------------------

CATALOG_SOURCE = _STUB_CATALOG  # noqa: F811  (re-assign to keep single name)


class BookingAdapter:
    """Adapter that routes to Setmore API when credentials are available,
    falling back to deterministic stub data otherwise."""

    def __init__(self) -> None:
        # Try to create the Setmore client; silently disable if token absent.
        refresh_token = os.environ.get("SETMORE_REFRESH_TOKEN", "")
        self._setmore = None
        if refresh_token:
            try:
                from .setmore_client import SetmoreClient
                self._setmore = SetmoreClient(refresh_token)
                logger.info("Setmore API integration enabled.")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to initialise SetmoreClient: %s", exc)

        # Stub-mode state
        self._stub_catalog_cache: list[dict] = []
        self._stub_next_refresh_at: datetime | None = None

        # Setmore-mode state
        self._sm_services: list[dict] = []
        self._sm_staff: list[dict] = []
        self._sm_next_refresh_at: datetime | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_services(self, language: str) -> list[ServiceSummary]:
        if self._setmore:
            self._ensure_setmore_cache()
            return self._map_setmore_services(language)
        self._ensure_stub_cache()
        return self._map_stub_services(language)

    def get_price_overview(self, language: str) -> str:
        services = self.list_services(language=language)
        joined = "; ".join(f"{s.name}: {s.price_label}" for s in services)
        if language.startswith("da"):
            return f"Her er priserne fra bookingsiden: {joined}."
        if language.startswith("fr"):
            return f"Voici les prix de la page de reservation : {joined}."
        if language.startswith("de"):
            return f"Hier sind die Preise von der Buchungsseite: {joined}."
        if language.startswith("zh"):
            return f"以下是预约页面上的价格：{joined}。"
        return f"Here are the prices from the booking page: {joined}."

    def get_availability(self, service_id: str, date: str) -> AvailabilityResponse:
        if self._setmore:
            response = self._setmore_get_availability(service_id, date)
        else:
            response = AvailabilityResponse(
                service_id=service_id,
                date=date,
                slots=[
                    AvailabilitySlot(start_time=f"{date}T10:00:00"),
                    AvailabilitySlot(start_time=f"{date}T13:00:00"),
                ],
            )

        response.slots = self._filter_past_slots_for_today(
            response.date, response.slots)
        return response

    def get_staff_availability_detail(self, service_id: str, date: str) -> dict[str, list[str]]:
        """Return {staff_display_name: [HH:MM, ...]} for all staff on date."""
        if self._setmore:
            return self._setmore_staff_availability_detail(service_id, date)
        return self._stub_staff_availability_detail(date)

    def create_booking(self, request: BookingRequest) -> BookingResponse:
        if self._setmore:
            return self._setmore_create_booking(request)
        return self._stub_create_booking(request)

    def verify_cancellation(self, request: CancelVerifyRequest) -> CancelVerifyResponse:
        if not request.booking_reference and not (request.service_id and request.start_time):
            return CancelVerifyResponse(
                verified=False,
                message="Provide booking_reference or service_id with start_time.",
            )
        if self._setmore:
            return self._setmore_verify_cancellation(request)
        return self._stub_verify_cancellation(request)

    def confirm_cancellation(self, booking_id: str) -> CancelConfirmResponse:
        # The Setmore beta API does not expose a cancellation endpoint.
        if self._setmore:
            return CancelConfirmResponse(
                status="canceled",
                cancellation_reference=f"cancel-{booking_id}",
                message=(
                    "Cancellations cannot be processed automatically at this time. "
                    "Please call the salon directly at +45 41 42 33 33 to cancel."
                ),
            )
        return self._stub_confirm_cancellation(booking_id)

    # ------------------------------------------------------------------
    # Setmore cache management
    # ------------------------------------------------------------------

    def _ensure_setmore_cache(self) -> None:
        now = self._now_in_copenhagen()
        if (
            not self._sm_services
            or self._sm_next_refresh_at is None
            or now >= self._sm_next_refresh_at
        ):
            assert self._setmore is not None
            self._sm_services = self._setmore.list_services()
            self._sm_staff = self._setmore.list_staff()
            self._sm_next_refresh_at = self._compute_next_sunday_morning(now)
            logger.info(
                "Setmore cache refreshed: %d services, %d staff",
                len(self._sm_services),
                len(self._sm_staff),
            )

    # ------------------------------------------------------------------
    # Setmore service mapping
    # ------------------------------------------------------------------

    def _map_setmore_services(self, language: str) -> list[ServiceSummary]:
        use_danish = language.startswith("da")
        # Build a lookup from normalised Danish name → English name from the stub catalogue.
        _da_to_en: dict[str, str] = {
            item["name_da"].lower(): item["name_en"] for item in _STUB_CATALOG
        }
        result = []
        for svc in self._sm_services:
            cost = svc.get("cost", 0)
            currency = svc.get("currency", "DKK")
            raw_name: str = svc["service_name"]
            if use_danish:
                display_name = raw_name
            else:
                display_name = _da_to_en.get(raw_name.lower(), raw_name)
            result.append(
                ServiceSummary(
                    service_id=svc["key"],
                    name=display_name,
                    duration_minutes=int(svc.get("duration", 30)),
                    price_label=_format_price(cost, currency),
                    language=language,
                )
            )
        return result

    def _find_setmore_service(self, service_id: str) -> dict | None:
        for svc in self._sm_services:
            if svc["key"] == service_id:
                return svc
        return None

    def _staff_display_name(self, staff: dict) -> str:
        return (
            staff.get("full_name")
            or staff.get("name")
            or staff.get("staff_name")
            or f"{staff.get('first_name', '')} {staff.get('last_name', '')}".strip()
            or "Unknown"
        )

    def _find_staff_key_by_name(self, target_name: str) -> str | None:
        norm = _normalize_person_name(target_name)
        # Exact match first
        for staff in self._sm_staff:
            if _normalize_person_name(self._staff_display_name(staff)) == norm:
                return staff.get("key")
        # Partial / first-name-only fallback (Setmore may store only first names)
        for staff in self._sm_staff:
            display = _normalize_person_name(self._staff_display_name(staff))
            if norm in display or display in norm:
                return staff.get("key")
        return None

    def _setmore_staff_availability_detail(self, service_id: str, date: str) -> dict[str, list[str]]:
        self._ensure_setmore_cache()
        service = self._find_setmore_service(service_id)
        if not service:
            return {}
        staff_keys = self._staff_keys_for_service(service, date_iso=date)
        slots_by_staff = self._fetch_slots_by_staff_for_date(
            service_id, date, staff_keys)
        key_to_name = {s["key"]: self._staff_display_name(
            s) for s in self._sm_staff}
        result: dict[str, list[str]] = {}
        for sk in staff_keys:
            raw_slots = slots_by_staff.get(sk, [])
            hhmm = [h for h in (_slot_to_hhmm(s) for s in raw_slots) if h]
            if hhmm:
                result[key_to_name.get(sk, sk)] = sorted(hhmm)
        return result

    def _stub_staff_availability_detail(self, date: str) -> dict[str, list[str]]:
        """Stub: Sahar is always the only available stylist."""
        now_local = self._now_in_copenhagen()
        candidate_slots = ["10:00", "13:00"]
        if date == now_local.date().isoformat():
            now_hhmm = now_local.strftime("%H:%M")
            candidate_slots = [t for t in candidate_slots if t > now_hhmm]
        return {"Sahar Ebrahim": candidate_slots} if candidate_slots else {}

    def _staff_keys_for_service(self, service: dict, date_iso: str | None = None) -> list[str]:
        keys = service.get("staff_keys", [])
        candidate_keys = keys if keys else [
            s["key"] for s in self._sm_staff[:1]]
        if not candidate_keys:
            return []

        preferred_key = self._preferred_staff_key(candidate_keys)
        if preferred_key is None or date_iso is None:
            return candidate_keys

        try:
            is_monday = datetime.fromisoformat(
                date_iso).weekday() == _MONDAY_WEEKDAY
        except ValueError:
            return candidate_keys

        ordered = [k for k in candidate_keys if k != preferred_key]
        if is_monday:
            return [preferred_key, *ordered]
        return [*ordered, preferred_key]

    def _preferred_staff_key(self, candidate_keys: list[str]) -> str | None:
        if not candidate_keys:
            return None
        by_key = {staff.get("key"): staff for staff in self._sm_staff}
        for key in candidate_keys:
            staff = by_key.get(key)
            if not staff:
                continue
            if self._staff_is_preferred(staff):
                return key
        return None

    def _staff_is_preferred(self, staff: dict) -> bool:
        # Setmore payloads can vary, so check multiple possible name shapes.
        full_name = (
            staff.get("full_name")
            or staff.get("name")
            or staff.get("staff_name")
            or f"{staff.get('first_name', '')} {staff.get('last_name', '')}".strip()
        )
        norm = _normalize_person_name(full_name)
        # Accept full-name match OR first-name-only match (Setmore often omits last name).
        return norm == _PREFERRED_STAFF_NAME or norm == _PREFERRED_STAFF_FIRST_NAME

    def _prioritize_staff_by_open_calendar(
        self,
        staff_keys: list[str],
        slots_by_staff: dict[str, list[str]],
    ) -> list[str]:
        open_calendar = [key for key in staff_keys if slots_by_staff.get(key)]
        closed_calendar = [
            key for key in staff_keys if not slots_by_staff.get(key)]
        return [*open_calendar, *closed_calendar]

    def _fetch_slots_by_staff_for_date(
        self,
        service_id: str,
        date_iso: str,
        staff_keys: list[str],
    ) -> dict[str, list[str]]:
        assert self._setmore is not None
        setmore_date = _date_iso_to_setmore_slots(date_iso)  # DD/MM/YYYY
        slots_by_staff: dict[str, list[str]] = {}
        for staff_key in staff_keys:
            try:
                slots_by_staff[staff_key] = self._setmore.get_slots(
                    staff_key=staff_key,
                    service_key=service_id,
                    selected_date=setmore_date,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("get_slots failed for staff %s: %s",
                             staff_key, exc)
                slots_by_staff[staff_key] = []
        return slots_by_staff

    # ------------------------------------------------------------------
    # Setmore availability
    # ------------------------------------------------------------------

    def _setmore_get_availability(self, service_id: str, date: str) -> AvailabilityResponse:
        assert self._setmore is not None
        self._ensure_setmore_cache()
        service = self._find_setmore_service(service_id)
        if not service:
            logger.warning(
                "Service key %s not found in Setmore cache", service_id)
            return AvailabilityResponse(service_id=service_id, date=date, slots=[])

        staff_keys = self._staff_keys_for_service(service, date_iso=date)
        slots_by_staff = self._fetch_slots_by_staff_for_date(
            service_id,
            date,
            staff_keys,
        )
        staff_keys = self._prioritize_staff_by_open_calendar(
            staff_keys, slots_by_staff)

        seen: set[str] = set()
        slots: list[AvailabilitySlot] = []
        for sk in staff_keys:
            for slot_str in slots_by_staff.get(sk, []):
                iso = _setmore_slot_to_iso(date, slot_str)
                if iso not in seen:
                    seen.add(iso)
                    slots.append(AvailabilitySlot(start_time=iso))

        slots.sort(key=lambda s: s.start_time)
        return AvailabilityResponse(service_id=service_id, date=date, slots=slots)

    # ------------------------------------------------------------------
    # Setmore booking creation
    # ------------------------------------------------------------------

    def _setmore_create_booking(self, request: BookingRequest) -> BookingResponse:
        assert self._setmore is not None
        self._ensure_setmore_cache()

        service = self._find_setmore_service(request.service_id)
        if not service:
            raise ValueError(f"Unknown service_id: {request.service_id}")

        booking_date_iso = _as_copenhagen_datetime(
            request.start_time
        ).date().isoformat()
        staff_keys = self._staff_keys_for_service(
            service,
            date_iso=booking_date_iso,
        )
        slots_by_staff = self._fetch_slots_by_staff_for_date(
            request.service_id,
            booking_date_iso,
            staff_keys,
        )
        staff_keys = self._prioritize_staff_by_open_calendar(
            staff_keys, slots_by_staff)
        if not staff_keys:
            raise ValueError("No staff available for this service")

        requested_hhmm = _as_copenhagen_datetime(
            request.start_time).strftime("%H:%M")
        staff_key = ""

        # If a specific staff member was requested by the agent, honour it.
        if request.staff_name:
            key_by_name = self._find_staff_key_by_name(request.staff_name)
            if key_by_name and key_by_name in staff_keys:
                staff_key = key_by_name
                logger.info("Using requested staff %s (%s)",
                            request.staff_name, staff_key)

        if not staff_key:
            for candidate in staff_keys:
                slot_values = slots_by_staff.get(candidate, [])
                if any(_slot_to_hhmm(slot) == requested_hhmm for slot in slot_values):
                    staff_key = candidate
                    break

        if not staff_key:
            staff_key = staff_keys[0]
            logger.warning(
                "Requested time %s not found in staff slots; falling back to first available staff %s",
                requested_hhmm,
                staff_key,
            )

        # Resolve or create the customer
        first_name, last_name = _split_name(request.customer_name)
        customer = self._setmore.find_customer(
            first_name=first_name,
            phone=request.customer_phone,
        )
        if customer is None:
            customer = self._setmore.create_customer(
                first_name=first_name,
                last_name=last_name,
                phone=request.customer_phone,
            )
            logger.info("Created new Setmore customer: %s",
                        customer.get("key"))
        else:
            logger.info("Found existing Setmore customer: %s",
                        customer.get("key"))

        customer_key = customer["key"]
        duration_minutes = int(service.get("duration", 30))

        # Normalize to Copenhagen wall-clock before sending to Setmore.
        dt_start_local = _as_copenhagen_datetime(request.start_time)
        start_utc = _iso_to_setmore_utc(request.start_time)
        dt_end_local = dt_start_local + timedelta(minutes=duration_minutes)
        end_utc = dt_end_local.strftime("%Y-%m-%dT%H:%MZ")

        appt = self._setmore.create_appointment(
            staff_key=staff_key,
            service_key=request.service_id,
            customer_key=customer_key,
            start_time=start_utc,
            end_time=end_utc,
        )
        logger.info("Setmore appointment created: %s", appt.get("key"))

        normalized_start_time = dt_start_local.isoformat(timespec="seconds")
        booked_staff_name = self._staff_display_name(
            next((s for s in self._sm_staff if s.get("key") == staff_key), {})
        )
        return BookingResponse(
            status="confirmed",
            booking_id=appt["key"],
            service_name=service["service_name"],
            start_time=normalized_start_time,
            staff_name=booked_staff_name,
            confirmation_text=self._confirmation_text(
                request.language, normalized_start_time),
        )

    # ------------------------------------------------------------------
    # Setmore cancellation lookup
    # ------------------------------------------------------------------

    def _setmore_verify_cancellation(self, request: CancelVerifyRequest) -> CancelVerifyResponse:
        assert self._setmore is not None
        self._ensure_setmore_cache()

        # Search a 60-day window centred on today
        today = datetime.now(tz=timezone.utc)
        start_str = (today - timedelta(days=30)).strftime("%d-%m-%Y")
        end_str = (today + timedelta(days=30)).strftime("%d-%m-%Y")

        try:
            appts = self._setmore.get_appointments(
                start_date=start_str,
                end_date=end_str,
                customer_details=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("get_appointments failed: %s", exc)
            return CancelVerifyResponse(
                verified=False,
                message="Could not retrieve appointments. Please try again.",
            )

        if request.booking_reference:
            for a in appts:
                if a.get("key") == request.booking_reference:
                    return self._appt_to_cancel_response(a)
            return CancelVerifyResponse(
                verified=False,
                message=f"No appointment found with reference {request.booking_reference}.",
            )

        for a in appts:
            if (
                a.get("service_key") == request.service_id
                and request.start_time
                and request.start_time[:16] in a.get("start_time", "")
            ):
                return self._appt_to_cancel_response(a)

        return CancelVerifyResponse(verified=False, message="No matching appointment found.")

    def _appt_to_cancel_response(self, appt: dict) -> CancelVerifyResponse:
        svc = self._find_setmore_service(appt.get("service_key", ""))
        service_name = svc["service_name"] if svc else appt.get(
            "service_key", "Unknown")
        return CancelVerifyResponse(
            verified=True,
            booking=CancellationCandidate(
                booking_id=appt["key"],
                service_name=service_name,
                start_time=appt.get("start_time", ""),
            ),
        )

    # ------------------------------------------------------------------
    # Stub-mode implementations
    # ------------------------------------------------------------------

    def _ensure_stub_cache(self) -> None:
        now = self._now_in_copenhagen()
        if (
            not self._stub_catalog_cache
            or self._stub_next_refresh_at is None
            or now >= self._stub_next_refresh_at
        ):
            self._stub_catalog_cache = list(self._load_catalog_source())
            self._stub_next_refresh_at = self._compute_next_sunday_morning(now)

    def _load_catalog_source(self) -> list[dict]:
        """Return the raw stub catalog. Override in tests via monkeypatch."""
        return _STUB_CATALOG

    def _map_stub_services(self, language: str) -> list[ServiceSummary]:
        use_danish = language.startswith("da")
        return [
            ServiceSummary(
                service_id=item["service_id"],
                name=item["name_da"] if use_danish else item["name_en"],
                duration_minutes=item["duration_minutes"],
                price_label=item["price_label"],
                language=language,
            )
            for item in self._stub_catalog_cache
        ]

    def _stub_service_name(self, service_id: str, language: str) -> str:
        self._ensure_stub_cache()
        use_danish = language.startswith("da")
        for item in self._stub_catalog_cache:
            if item["service_id"] == service_id:
                return item["name_da"] if use_danish else item["name_en"]
        return "Dame Klip" if use_danish else "Ladies Haircut"

    def _stub_create_booking(self, request: BookingRequest) -> BookingResponse:
        self._ensure_stub_cache()
        normalized_start_time = _as_copenhagen_datetime(
            request.start_time
        ).isoformat(timespec="seconds")
        return BookingResponse(
            status="confirmed",
            booking_id="stub-booking-001",
            service_name=self._stub_service_name(
                request.service_id, request.language),
            start_time=normalized_start_time,
            staff_name=request.staff_name or "Sahar Ebrahim",
            confirmation_text=self._confirmation_text(
                request.language, normalized_start_time),
        )

    def _stub_verify_cancellation(self, request: CancelVerifyRequest) -> CancelVerifyResponse:
        language = "da"
        if request.service_id and request.service_id != "haircut_ladies":
            language = "en"
        return CancelVerifyResponse(
            verified=True,
            booking=CancellationCandidate(
                booking_id=request.booking_reference or "stub-booking-001",
                service_name=self._stub_service_name(
                    service_id=request.service_id or "haircut_ladies",
                    language=language,
                ),
                start_time=request.start_time or "2026-07-08T13:00:00+02:00",
            ),
        )

    def _stub_confirm_cancellation(self, booking_id: str) -> CancelConfirmResponse:
        return CancelConfirmResponse(
            status="canceled",
            cancellation_reference=f"cancel-{booking_id}",
            message="Booking canceled.",
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _confirmation_text(self, language: str, start_time: str) -> str:
        if language.startswith("da"):
            return f"Din tid er reserveret {start_time}."
        if language.startswith("fr"):
            return f"Votre rendez-vous est reserve pour {start_time}."
        if language.startswith("de"):
            return f"Ihr Termin wurde fur {start_time} reserviert."
        if language.startswith("zh"):
            return f"您的预约时间已预留：{start_time}。"
        return f"Your appointment has been reserved for {start_time}."

    def _now_in_copenhagen(self) -> datetime:
        try:
            return datetime.now(ZoneInfo("Europe/Copenhagen"))
        except Exception:  # noqa: BLE001
            # Windows Python may lack IANA tzdata; fall back to local timezone.
            return datetime.now().astimezone()

    def _filter_past_slots_for_today(
        self,
        date_iso: str,
        slots: list[AvailabilitySlot],
    ) -> list[AvailabilitySlot]:
        """Keep only future slots when availability is requested for today."""
        now_local = self._now_in_copenhagen()
        if date_iso != now_local.date().isoformat():
            return slots

        filtered: list[AvailabilitySlot] = []
        for slot in slots:
            try:
                slot_start = datetime.fromisoformat(slot.start_time)
            except ValueError:
                # Unknown format; keep it rather than dropping possibly valid data.
                filtered.append(slot)
                continue

            if slot_start.tzinfo is None:
                slot_start = slot_start.replace(tzinfo=now_local.tzinfo)
            else:
                slot_start = slot_start.astimezone(now_local.tzinfo)

            if slot_start > now_local:
                filtered.append(slot)

        return filtered

    def _compute_next_sunday_morning(self, now: datetime) -> datetime:
        days_until_sunday = (6 - now.weekday()) % 7
        next_refresh = now.replace(
            hour=8, minute=0, second=0, microsecond=0
        ) + timedelta(days=days_until_sunday)
        if next_refresh <= now:
            next_refresh += timedelta(days=7)
        return next_refresh
