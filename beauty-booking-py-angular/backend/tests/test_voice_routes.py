def test_incoming_call_endpoint_accepts_event_payload(client) -> None:
    response = client.post(
        "/api/voice/call/incoming",
        json={"call_id": "call-123", "from": "+4511111111", "to": "+4522222222"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert "call-123" in payload["message"]


def test_call_events_endpoint_returns_ok(client) -> None:
    response = client.post(
        "/api/voice/call/events",
        json={"call_id": "call-123", "event_type": "recognize_completed"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_services_endpoint_defaults_to_danish(client) -> None:
    response = client.get("/api/voice/services")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"][0]["name"] == "Dameklip"
    assert payload["services"][0]["language"] == "da"


def test_services_endpoint_returns_english_name_when_requested(client) -> None:
    response = client.get("/api/voice/services?language=en")

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"][0]["name"] == "Ladies haircut"
    assert payload["services"][0]["language"] == "en"


def test_availability_endpoint_returns_slots(client) -> None:
    response = client.get(
        "/api/voice/availability?service_id=haircut_ladies&date=2026-07-08")

    assert response.status_code == 200
    payload = response.json()
    assert payload["service_id"] == "haircut_ladies"
    assert payload["date"] == "2026-07-08"
    assert len(payload["slots"]) == 2


def test_booking_endpoint_returns_danish_confirmation_for_da_language(client) -> None:
    response = client.post(
        "/api/voice/bookings",
        json={
            "customer_phone": "+4523391178",
            "service_id": "haircut_ladies",
            "start_time": "2026-07-08T13:00:00+02:00",
            "language": "da",
            "idempotency_key": "booking-da-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "confirmed"
    assert payload["service_name"] == "Dameklip"
    assert "Din tid er reserveret" in payload["confirmation_text"]


def test_booking_endpoint_returns_english_confirmation_for_en_language(client) -> None:
    response = client.post(
        "/api/voice/bookings",
        json={
            "customer_phone": "+4523391178",
            "service_id": "haircut_ladies",
            "start_time": "2026-07-08T13:00:00+02:00",
            "language": "en",
            "idempotency_key": "booking-en-1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["service_name"] == "Ladies haircut"
    assert "Your appointment has been reserved" in payload["confirmation_text"]


def test_booking_endpoint_validates_required_fields(client) -> None:
    response = client.post(
        "/api/voice/bookings",
        json={
            "customer_phone": "+4523391178",
            "service_id": "haircut_ladies",
            "start_time": "2026-07-08T13:00:00+02:00",
            "language": "da",
        },
    )

    assert response.status_code == 422


def test_cancel_verify_endpoint_accepts_booking_reference(client) -> None:
    response = client.post(
        "/api/voice/cancellations/verify",
        json={"customer_phone": "+4523391178", "booking_reference": "BK-123"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
    assert payload["booking"]["booking_id"] == "BK-123"


def test_cancel_verify_endpoint_accepts_service_and_time_match(client) -> None:
    response = client.post(
        "/api/voice/cancellations/verify",
        json={
            "customer_phone": "+4523391178",
            "service_id": "haircut_ladies",
            "start_time": "2026-07-08T13:00:00+02:00",
        },
    )

    assert response.status_code == 200
    assert response.json()["verified"] is True


def test_cancel_verify_endpoint_rejects_missing_proof(client) -> None:
    response = client.post(
        "/api/voice/cancellations/verify",
        json={"customer_phone": "+4523391178"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is False
    assert "Provide booking_reference" in payload["message"]


def test_cancel_confirm_endpoint_returns_canceled_status(client) -> None:
    response = client.post(
        "/api/voice/cancellations/confirm",
        json={"booking_id": "BK-123", "idempotency_key": "cancel-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "canceled"
    assert payload["cancellation_reference"] == "cancel-BK-123"


def test_cancel_confirm_endpoint_validates_required_fields(client) -> None:
    response = client.post(
        "/api/voice/cancellations/confirm",
        json={"booking_id": "BK-123"},
    )

    assert response.status_code == 422
