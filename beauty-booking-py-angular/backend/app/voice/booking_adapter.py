from .models import (
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


class BookingAdapter:
    """Temporary adapter contract for the launch booking provider.

    Keep all booking-provider specifics in this class so route handlers stay stable
    when the implementation switches from stub data to a real API client.
    """

    def list_services(self, language: str) -> list[ServiceSummary]:
        # Bilingual placeholder until service catalog is loaded from provider.
        service_name = "Dameklip" if language.startswith(
            "da") else "Ladies haircut"
        return [
            ServiceSummary(
                service_id="haircut_ladies",
                name=service_name,
                duration_minutes=60,
                language=language,
            )
        ]

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
        # This simulates the final confirmation payload returned to voice orchestration.
        service_name = "Dameklip" if request.language.startswith(
            "da") else "Ladies haircut"
        confirmation_text = (
            f"Din tid er reserveret {request.start_time}."
            if request.language.startswith("da")
            else f"Your appointment has been reserved for {request.start_time}."
        )
        return BookingResponse(
            status="confirmed",
            booking_id="stub-booking-001",
            service_name=service_name,
            start_time=request.start_time,
            confirmation_text=confirmation_text,
        )

    def verify_cancellation(self, request: CancelVerifyRequest) -> CancelVerifyResponse:
        # Cancellation requires either a direct booking reference or service+time proof.
        if not request.booking_reference and not (request.service_id and request.start_time):
            return CancelVerifyResponse(
                verified=False,
                message="Provide booking_reference or service_id with start_time.",
            )

        return CancelVerifyResponse(
            verified=True,
            booking=CancellationCandidate(
                booking_id=request.booking_reference or "stub-booking-001",
                service_name="Dameklip",
                start_time=request.start_time or "2026-07-08T13:00:00+02:00",
            ),
        )

    def confirm_cancellation(self, booking_id: str) -> CancelConfirmResponse:
        return CancelConfirmResponse(
            status="canceled",
            cancellation_reference=f"cancel-{booking_id}",
            message="Booking canceled.",
        )
