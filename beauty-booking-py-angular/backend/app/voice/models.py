from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class VoiceStatusResponse(BaseModel):
    status: str
    message: str


class IncomingCallEvent(BaseModel):
    call_id: Optional[str] = None
    from_number: Optional[str] = Field(default=None, alias="from")
    to_number: Optional[str] = Field(default=None, alias="to")
    raw_event: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CallEventEnvelope(BaseModel):
    call_id: Optional[str] = None
    event_type: Optional[str] = None
    operation_context: Optional[str] = None
    raw_event: dict = Field(default_factory=dict)


class ServiceSummary(BaseModel):
    service_id: str
    name: str
    duration_minutes: int
    language: str = "da"


class ServicesResponse(BaseModel):
    services: List[ServiceSummary]


class AvailabilitySlot(BaseModel):
    start_time: str
    end_time: Optional[str] = None
    staff_name: Optional[str] = None


class AvailabilityResponse(BaseModel):
    service_id: str
    date: str
    slots: List[AvailabilitySlot]


class BookingRequest(BaseModel):
    customer_phone: str
    service_id: str
    start_time: str
    language: str = "da"
    customer_name: Optional[str] = None
    idempotency_key: str


class BookingResponse(BaseModel):
    status: Literal["confirmed", "pending"]
    booking_id: str
    service_name: str
    start_time: str
    confirmation_text: str


class CancelVerifyRequest(BaseModel):
    customer_phone: str
    booking_reference: Optional[str] = None
    service_id: Optional[str] = None
    start_time: Optional[str] = None


class CancellationCandidate(BaseModel):
    booking_id: str
    service_name: str
    start_time: str


class CancelVerifyResponse(BaseModel):
    verified: bool
    booking: Optional[CancellationCandidate] = None
    message: Optional[str] = None


class CancelConfirmRequest(BaseModel):
    booking_id: str
    idempotency_key: str


class CancelConfirmResponse(BaseModel):
    status: Literal["canceled"]
    cancellation_reference: str
    message: str
