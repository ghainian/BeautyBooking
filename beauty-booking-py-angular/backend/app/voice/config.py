import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceSettings:
    # Defaults keep local/dev behavior predictable even before cloud secrets are wired.
    default_language: str = os.getenv("VOICE_DEFAULT_LANGUAGE", "da-DK")
    fallback_language: str = os.getenv("VOICE_FALLBACK_LANGUAGE", "en-US")
    fallback_transfer_number: str = os.getenv(
        "VOICE_FALLBACK_TRANSFER_NUMBER", "+4542735479")
    retention_mode: str = os.getenv("VOICE_RETENTION_MODE", "transcript-only")
    booking_provider: str = os.getenv("VOICE_BOOKING_PROVIDER", "setmore")


settings = VoiceSettings()
