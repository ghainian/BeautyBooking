"""Thread-safe HTTP client for the Setmore booking API (v1 beta).

Authentication:
    Setmore uses a two-step OAuth-like flow:
      1. Exchange a long-lived refresh token for a short-lived access token.
      2. Send the access token as a Bearer header on every API request.
    This client handles token caching and automatic refresh transparently.

Environment variable:
    SETMORE_REFRESH_TOKEN – the refresh token issued by Setmore.
"""

from __future__ import annotations

import logging
import os
import threading
import time

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://developer.setmore.com"
# Refresh the access token this many seconds before it actually expires,
# to avoid using a token that expires mid-request.
_EXPIRY_BUFFER_SECONDS = 120


class SetmoreClient:
    """Thread-safe Setmore REST API client with automatic token refresh."""

    def __init__(self, refresh_token: str | None = None) -> None:
        token = refresh_token or os.environ.get("SETMORE_REFRESH_TOKEN", "")
        if not token:
            raise ValueError(
                "Setmore refresh token is required. "
                "Set the SETMORE_REFRESH_TOKEN environment variable."
            )
        self._refresh_token = token
        self._access_token: str | None = None
        self._token_expires_at: float = 0.0  # monotonic timestamp
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def _ensure_token(self) -> str:
        with self._lock:
            if self._access_token and time.monotonic() < self._token_expires_at:
                return self._access_token
            self._do_refresh()
        return self._access_token  # type: ignore[return-value]

    def _do_refresh(self) -> None:
        url = f"{_BASE_URL}/api/v1/o/oauth2/token"
        resp = httpx.get(
            url, params={"refreshToken": self._refresh_token}, timeout=15)
        resp.raise_for_status()
        body = resp.json()
        if not body.get("response"):
            raise RuntimeError(f"Setmore token refresh failed: {body}")
        token_data = body["data"]["token"]
        self._access_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 3600))
        self._token_expires_at = (
            time.monotonic() + expires_in - _EXPIRY_BUFFER_SECONDS
        )
        logger.info(
            "Setmore access token refreshed (expires_in=%d s)", expires_in)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._ensure_token()}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------

    def list_services(self) -> list[dict]:
        """Return all services from the Setmore account."""
        resp = httpx.get(
            f"{_BASE_URL}/api/v1/bookingapi/services",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["services"]

    # ------------------------------------------------------------------
    # Staff
    # ------------------------------------------------------------------

    def list_staff(self) -> list[dict]:
        """Return all staff members (up to 50 in the first batch)."""
        resp = httpx.get(
            f"{_BASE_URL}/api/v1/bookingapi/staffs",
            headers=self._headers(),
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["staffs"]

    # ------------------------------------------------------------------
    # Availability slots
    # ------------------------------------------------------------------

    def get_slots(
        self,
        staff_key: str,
        service_key: str,
        selected_date: str,  # DD/MM/YYYY
        timezone: str = "Europe/Copenhagen",
    ) -> list[str]:
        """Return available slot strings like '10.00', '10.30' for a given staff/service/date."""
        payload = {
            "staff_key": staff_key,
            "service_key": service_key,
            "selected_date": selected_date,
            "timezone": timezone,
        }
        resp = httpx.post(
            f"{_BASE_URL}/api/v1/bookingapi/slots",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        # Setmore returns data as a plain list
        if isinstance(data, list):
            return data
        return data.get("slots", [])

    # ------------------------------------------------------------------
    # Customers
    # ------------------------------------------------------------------

    def find_customer(
        self,
        first_name: str,
        phone: str = "",
        email: str = "",
    ) -> dict | None:
        """Search for an existing customer; returns the best match or None."""
        params: dict[str, str] = {"firstname": first_name}
        if phone:
            params["phone"] = phone
        if email:
            params["email"] = email
        resp = httpx.get(
            f"{_BASE_URL}/api/v1/bookingapi/customer",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        customers = resp.json().get("data", {}).get("customer", [])
        if not customers:
            return None
        # Prefer an exact phone match
        if phone:
            clean = phone.replace(" ", "").replace("-", "")
            for c in customers:
                c_phone = c.get("cell_phone", "").replace(
                    " ", "").replace("-", "")
                if c_phone and c_phone == clean:
                    return c
        return customers[0]

    def create_customer(
        self,
        first_name: str,
        last_name: str = "",
        phone: str = "",
        email: str = "",
    ) -> dict:
        """Create a new customer and return the created customer dict."""
        payload: dict[str, str] = {"first_name": first_name}
        if last_name:
            payload["last_name"] = last_name
        if phone:
            payload["cell_phone"] = phone
        if email:
            payload["email_id"] = email
        resp = httpx.post(
            f"{_BASE_URL}/api/v1/bookingapi/customer/create",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["customer"]

    # ------------------------------------------------------------------
    # Appointments
    # ------------------------------------------------------------------

    def create_appointment(
        self,
        staff_key: str,
        service_key: str,
        customer_key: str,
        start_time: str,  # yyyy-MM-ddTHH:mmZ  (UTC)
        end_time: str,    # yyyy-MM-ddTHH:mmZ  (UTC)
        comment: str = "",
    ) -> dict:
        """Book an appointment and return the created appointment dict."""
        payload: dict[str, str] = {
            "staff_key": staff_key,
            "service_key": service_key,
            "customer_key": customer_key,
            "start_time": start_time,
            "end_time": end_time,
        }
        if comment:
            payload["comment"] = comment
        resp = httpx.post(
            f"{_BASE_URL}/api/v1/bookingapi/appointment/create",
            headers=self._headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["data"]["appointment"]

    def get_appointments(
        self,
        start_date: str,  # dd-mm-yyyy
        end_date: str,    # dd-mm-yyyy
        staff_key: str | None = None,
        customer_details: bool = True,
    ) -> list[dict]:
        """Fetch appointments in a date range (max 150 per request)."""
        params: dict[str, str] = {
            "startDate": start_date,
            "endDate": end_date,
            "customerDetails": "true" if customer_details else "false",
        }
        if staff_key:
            params["staff_key"] = staff_key
        resp = httpx.get(
            f"{_BASE_URL}/api/v1/bookingapi/appointments",
            headers=self._headers(),
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("data", {}).get("appointments", [])
