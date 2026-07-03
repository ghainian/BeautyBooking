from fastapi import APIRouter, Query

from .booking_adapter import BookingAdapter
from .models import (
    AvailabilityResponse,
    BookingRequest,
    BookingResponse,
    CallEventEnvelope,
    CancelConfirmRequest,
    CancelConfirmResponse,
    CancelVerifyRequest,
    CancelVerifyResponse,
    IncomingCallEvent,
    ServicesResponse,
    VoiceStatusResponse,
)
from .orchestrator import orchestrator

router = APIRouter(prefix="/api/voice", tags=["voice"])
booking_adapter = BookingAdapter()


@router.post("/call/incoming", response_model=VoiceStatusResponse)
def handle_incoming_call(event: IncomingCallEvent) -> VoiceStatusResponse:
    # Thin endpoint: keep HTTP responsibilities here and orchestration logic in orchestrator.
    return orchestrator.handle_incoming_call(event)


@router.post("/call/events", response_model=VoiceStatusResponse)
def handle_call_events(event: CallEventEnvelope) -> VoiceStatusResponse:
    return orchestrator.handle_call_event(event)


@router.get("/services", response_model=ServicesResponse)
def list_services(language: str = Query(default="da")) -> ServicesResponse:
    return ServicesResponse(services=booking_adapter.list_services(language=language))


@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(service_id: str, date: str, language: str = Query(default="da")) -> AvailabilityResponse:
    # Language is kept in the contract now so callers do not need to change later.
    del language
    return booking_adapter.get_availability(service_id=service_id, date=date)


@router.post("/bookings", response_model=BookingResponse)
def create_booking(request: BookingRequest) -> BookingResponse:
    return booking_adapter.create_booking(request)


@router.post("/cancellations/verify", response_model=CancelVerifyResponse)
def verify_cancellation(request: CancelVerifyRequest) -> CancelVerifyResponse:
    return booking_adapter.verify_cancellation(request)


@router.post("/cancellations/confirm", response_model=CancelConfirmResponse)
def confirm_cancellation(request: CancelConfirmRequest) -> CancelConfirmResponse:
    return booking_adapter.confirm_cancellation(request.booking_id)
