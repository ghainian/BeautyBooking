from .config import settings
from .models import CallEventEnvelope, IncomingCallEvent, VoiceStatusResponse


class VoiceOrchestrator:
    """Minimal orchestration stub for inbound voice flows."""

    def handle_incoming_call(self, event: IncomingCallEvent) -> VoiceStatusResponse:
        # In production this method will answer the ACS call and start the first speech turn.
        call_id = event.call_id or "unknown-call"
        return VoiceStatusResponse(
            status="accepted",
            message=(
                f"Inbound call {call_id} accepted for {settings.booking_provider}; "
                f"fallback transfer is {settings.fallback_transfer_number}."
            ),
        )

    def handle_call_event(self, event: CallEventEnvelope) -> VoiceStatusResponse:
        # Event dispatch will eventually branch by recognition/transfer/playback event types.
        event_type = event.event_type or "unknown-event"
        return VoiceStatusResponse(
            status="ok",
            message=f"Processed call event: {event_type}",
        )


orchestrator = VoiceOrchestrator()
