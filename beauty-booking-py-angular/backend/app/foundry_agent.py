"""Azure OpenAI Assistants-backed booking chat agent.

Replaces the rule-based BookingChatAgent with a GPT agent that:
- Answers general salon questions in any language
- Checks availability and creates/cancels bookings via function tools
- Maintains one thread per session for multi-turn conversation

Required environment variables
--------------------------------
AZURE_OPENAI_ENDPOINT   e.g. https://salonanova-openai.openai.azure.com/
AZURE_OPENAI_API_KEY    resource API key
AZURE_AI_AGENT_MODEL    deployment name, defaults to gpt-4o-mini

Note: AZURE_AI_FOUNDRY_ENDPOINT is accepted as an alias for AZURE_OPENAI_ENDPOINT
for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
import os
import re
import time
import uuid

from openai import AzureOpenAI
from pydantic import BaseModel

from .booking_adapter import BookingAdapter, _normalize_person_name
from .booking_models import BookingRequest, BookingResponse

logger = logging.getLogger(__name__)


@dataclass
class _FallbackBookingState:
    service_id: str | None = None
    date: str | None = None
    available_times: list[str] = field(default_factory=list)
    selected_time: str | None = None
    customer_phone: str | None = None
    customer_name: str | None = None
    staff_name: str | None = None   # stylist chosen for this booking
    awaiting_name: bool = False


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    language: str = "da"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    booking: BookingResponse | None = None


_POLL_INTERVAL = 0.5   # seconds between run status polls
_MAX_POLL = 120        # stop polling after this many seconds

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the friendly booking assistant for Salon Anova, a hair salon in Copenhagen, Denmark.

SALON INFORMATION
- Address: Amagerbrogade 219, 2300 Copenhagen S
- Phone: +45 41 42 33 33
- Online booking: https://salonanova.setmore.com
- Opening hours:
    Monday-Friday  09:30-18:00
    Saturday       09:30-16:00
    Sunday         CLOSED

SERVICES AND PRICES
Call list_services with the language code matching the conversation (e.g. "en", "da", "fr", "de").
Service names will be returned in English for any non-Danish language. Always present them translated into the response language.

IMPORTANT RULES
1. Always reply in the same language as the customer (Danish, English, French, German, Chinese, etc.)
   Determine the language from the first substantive message and keep it for the entire conversation.
   Phone numbers, digits, names, and single words do NOT indicate a language change — ignore them for language detection and continue in the previously established language.
2. Never invent time slots. Always call get_availability BEFORE offering or confirming a time.
3. Booking flow:
   a. Identify the service.
   b. Determine the date:
      - If the customer says "earliest", "soonest", "first available", "as soon as possible", or any equivalent,
        call get_availability(service_id, TODAY) immediately. If no slots are returned, try TOMORROW, then the
        day after, continuing up to 7 days ahead until a slot is found. Do NOT ask the customer for a date.
      - Otherwise ask for their preferred date and time, then call get_availability for that date.
   c. Present only the returned slots (the first available slot for "earliest" requests).
   d. Confirm which slot the customer wants (skip this step for "earliest" if there is only one option).
   e. Ask for the customer's phone number.
   f. Call create_booking to confirm. Pass the conversation language code in the "language" parameter.
   g. After create_booking succeeds, compose your OWN confirmation message in the conversation language
      using the returned service_name, start_time, and booking_id fields.
      Never output the raw "confirmation_text" field — it may be in a different language.
4. Cancellation flow:
   a. Ask for booking reference or service + date.
   b. Call cancel_booking with the reference.
5. Keep answers concise and professional.

STAFF SELECTION
- Sahar Ebrahim is the default stylist for all bookings.
- When you have identified the service and date, call get_staff_availability(service_id, date).
- If Sahar has the requested time slot (or any slot for "earliest" requests): book with Sahar.
  Always mention "with Sahar" in your reply before and after confirming.
- If Sahar does NOT have the requested time: present the names and available times of the
  other staff members returned, ask which one the customer prefers, then proceed.
- Pass the chosen staff name in the "staff_name" field of create_booking.
- Always mention the stylist's name in the booking confirmation.
"""

# ---------------------------------------------------------------------------
# OpenAI function-tool definitions
# ---------------------------------------------------------------------------

_TOOLS_JSON = [
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "Return the list of available services with prices.",
            "parameters": {
                "type": "object",
                "properties": {
                    "language": {
                        "type": "string",
                        "description": "Language code e.g. 'da' or 'en'",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_availability",
            "description": "Return available time slots for a service on a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Service identifier e.g. 'herre_klipning'",
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD",
                    },
                },
                "required": ["service_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_staff_availability",
            "description": "Return which staff members are available for a service on a given date, with their available time slots.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Service identifier e.g. 'herre_klipning'",
                    },
                    "date": {
                        "type": "string",
                        "description": "ISO date YYYY-MM-DD",
                    },
                },
                "required": ["service_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_booking",
            "description": (
                "Create a booking. Only call after confirming the requested "
                "time is in get_availability results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "HH:MM 24-hour"},
                    "phone": {"type": "string"},
                    "language": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "staff_name": {
                        "type": "string",
                        "description": "Full name of the stylist to book with, e.g. 'Sahar Ebrahim'",
                    },
                },
                "required": ["service_id", "date", "time", "phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel an existing booking by its booking reference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "booking_reference": {"type": "string"},
                },
                "required": ["booking_reference"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations — each returns a JSON string consumed by the agent
# ---------------------------------------------------------------------------


def _build_dispatch(adapter: BookingAdapter) -> dict:
    """Return a name -> callable map for the four booking tools."""

    def list_services(language: str = "en") -> str:
        services = adapter.list_services(language=language)
        return json.dumps(
            [
                {
                    "service_id": s.service_id,
                    "name": s.name,
                    "duration_minutes": s.duration_minutes,
                    "price": s.price_label,
                }
                for s in services
            ],
            ensure_ascii=False,
        )

    def get_staff_availability(service_id: str, date: str) -> str:
        detail = adapter.get_staff_availability_detail(
            service_id=service_id, date=date)
        return json.dumps(detail, ensure_ascii=False)

    def get_availability(service_id: str, date: str) -> str:
        result = adapter.get_availability(service_id=service_id, date=date)
        slots = [s.start_time[11:16]
                 for s in result.slots if len(s.start_time) >= 16]
        return json.dumps({"date": date, "available_times": slots}, ensure_ascii=False)

    def create_booking(
        service_id: str,
        date: str,
        time: str,
        phone: str,
        language: str = "en",
        customer_name: str | None = None,
        staff_name: str | None = None,
    ) -> str:
        start_time = f"{date}T{time}:00"
        response = adapter.create_booking(
            BookingRequest(
                customer_phone=phone,
                service_id=service_id,
                start_time=start_time,
                language=language,
                customer_name=customer_name,
                staff_name=staff_name,
                idempotency_key=f"foundry-{uuid.uuid4().hex[:10]}",
            )
        )
        return json.dumps(
            {
                "status": response.status,
                "booking_id": response.booking_id,
                "service_name": response.service_name,
                "start_time": response.start_time,
                "staff_name": response.staff_name,
                "confirmation_text": response.confirmation_text,
            },
            ensure_ascii=False,
        )

    def cancel_booking(booking_reference: str) -> str:
        result = adapter.confirm_cancellation(booking_id=booking_reference)
        return json.dumps(
            {
                "status": result.status,
                "cancellation_reference": result.cancellation_reference,
                "message": result.message,
            },
            ensure_ascii=False,
        )

    return {
        "list_services": list_services,
        "get_staff_availability": get_staff_availability,
        "get_availability": get_availability,
        "create_booking": create_booking,
        "cancel_booking": cancel_booking,
    }


# ---------------------------------------------------------------------------
# FoundryChatAgent
# ---------------------------------------------------------------------------


class FoundryChatAgent:
    """Chat agent backed by Azure OpenAI Assistants API (function tools for booking)."""

    _ASSISTANT_NAME = "salon-anova-booking-agent"

    def __init__(self) -> None:
        endpoint = (
            os.environ.get("AZURE_OPENAI_ENDPOINT")
            or os.environ.get("AZURE_AI_FOUNDRY_ENDPOINT", "")
        ).rstrip("/")
        api_key = os.environ["AZURE_OPENAI_API_KEY"]
        model = os.environ.get("AZURE_AI_AGENT_MODEL", "gpt-4o-mini")

        self._model = model
        self._adapter = BookingAdapter()
        self._dispatch = _build_dispatch(self._adapter)
        self._client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version="2024-05-01-preview",
            max_retries=4,  # auto-retry with backoff on 429 / 5xx
        )
        self._assistant_id: str | None = None
        # session_id -> thread_id
        self._threads: dict[str, str] = {}
        self._fallback_messages: dict[str, list[dict]] = {}
        self._fallback_booking_state: dict[str, _FallbackBookingState] = {}

    # ------------------------------------------------------------------
    # Public interface — same signature as BookingChatAgent.answer
    # ------------------------------------------------------------------

    def answer(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or f"chat-{uuid.uuid4().hex[:12]}"
        assistant_id = self._ensure_assistant_id()
        if assistant_id is None:
            return self._answer_via_chat_completions(request, session_id)

        try:
            thread_id = self._ensure_thread(session_id)

            self._client.beta.threads.messages.create(
                thread_id=thread_id,
                role="user",
                content=request.message or "",
            )

            run = self._client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=assistant_id,
            )

            booking_result: BookingResponse | None = None
            deadline = time.monotonic() + _MAX_POLL

            while time.monotonic() < deadline:
                run = self._client.beta.threads.runs.retrieve(
                    thread_id=thread_id, run_id=run.id
                )
                if run.status == "requires_action":
                    booking_result = self._handle_tool_calls(
                        run, thread_id) or booking_result
                elif run.status in ("completed", "failed", "cancelled", "expired"):
                    break
                else:
                    time.sleep(_POLL_INTERVAL)

            if run.status != "completed":
                logger.error(
                    "Run ended with status=%s error=%s",
                    run.status,
                    getattr(run, "last_error", None),
                )
                return self._answer_via_chat_completions(request, session_id)

            return ChatResponse(
                session_id=session_id,
                reply=self._last_assistant_message(thread_id),
                booking=booking_result,
            )
        except Exception as exc:
            logger.exception(
                "Assistants path failed, using chat fallback: %s", exc)
            return self._answer_via_chat_completions(request, session_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_assistant_id(self) -> str | None:
        if self._assistant_id:
            return self._assistant_id

        try:
            assistant = self._get_or_create_assistant()
            if isinstance(assistant, str) and assistant:
                self._assistant_id = assistant
                return assistant
            if isinstance(assistant, str):
                logger.warning(
                    "Assistant initialization returned an empty id; using chat fallback."
                )
                return None

            assistant_id = getattr(assistant, "id", None)
            if isinstance(assistant_id, str) and assistant_id:
                self._assistant_id = assistant_id
                return assistant_id

            logger.error("Unexpected assistant object type: %s",
                         type(assistant).__name__)
            return None
        except Exception as exc:
            logger.exception("Failed to initialize assistant: %s", exc)
            return None

    def _get_or_create_assistant(self):
        try:
            for asst in self._client.beta.assistants.list(limit=100):
                if asst.name == self._ASSISTANT_NAME:
                    logger.info("Reusing existing assistant id=%s", asst.id)
                    return self._client.beta.assistants.update(
                        asst.id,
                        instructions=_SYSTEM_PROMPT,
                        tools=_TOOLS_JSON,
                        model=self._model,
                    )
        except Exception:
            pass

        asst = self._client.beta.assistants.create(
            name=self._ASSISTANT_NAME,
            instructions=_SYSTEM_PROMPT,
            tools=_TOOLS_JSON,
            model=self._model,
        )
        assistant_id = asst if isinstance(
            asst, str) else getattr(asst, "id", None)
        logger.info("Created assistant id=%s model=%s",
                    assistant_id, self._model)
        return asst

    def _ensure_thread(self, session_id: str) -> str:
        if session_id not in self._threads:
            thread = self._client.beta.threads.create()
            self._threads[session_id] = thread.id
        return self._threads[session_id]

    def _handle_tool_calls(self, run, thread_id: str) -> BookingResponse | None:
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []
        booking_result: BookingResponse | None = None

        for tc in tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments or "{}")
            fn = self._dispatch.get(name)
            if fn is None:
                output = json.dumps({"error": f"Unknown tool: {name}"})
            else:
                try:
                    output = fn(**args)
                    if name == "create_booking":
                        data = json.loads(output)
                        booking_result = BookingResponse(
                            status=data.get("status", "confirmed"),
                            booking_id=data.get("booking_id", ""),
                            service_name=data.get("service_name", ""),
                            start_time=data.get("start_time", ""),
                            confirmation_text=data.get(
                                "confirmation_text", ""),
                        )
                except Exception as exc:
                    logger.exception("Tool %s raised: %s", name, exc)
                    output = json.dumps({"error": str(exc)})
            tool_outputs.append({"tool_call_id": tc.id, "output": output})

        self._client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs,
        )
        return booking_result

    def _last_assistant_message(self, thread_id: str) -> str:
        messages = self._client.beta.threads.messages.list(
            thread_id=thread_id, order="desc", limit=1
        )
        for msg in messages:
            if msg.role == "assistant":
                for block in msg.content:
                    if block.type == "text":
                        return block.text.value
        return ""

    def _fallback_history_for(self, session_id: str) -> list[dict]:
        history = self._fallback_messages.get(session_id)
        if history is None:
            history = [{"role": "system", "content": _SYSTEM_PROMPT}]
            self._fallback_messages[session_id] = history
        return history

    def _fallback_booking_state_for(self, session_id: str) -> _FallbackBookingState:
        state = self._fallback_booking_state.get(session_id)
        if state is None:
            state = _FallbackBookingState()
            self._fallback_booking_state[session_id] = state
        return state

    def _reset_fallback_session(self, session_id: str) -> None:
        self._fallback_messages[session_id] = [
            {"role": "system", "content": _SYSTEM_PROMPT}]
        self._fallback_booking_state[session_id] = _FallbackBookingState()

    def _is_reset_message(self, text: str) -> bool:
        normalized = (text or "").strip().lower()
        return normalized in {"forfra", "start forfra", "reset", "start over"}

    def _extract_phone(self, text: str) -> str | None:
        match = re.search(r"(\+?\d[\d\s]{6,}\d)", text or "")
        if not match:
            return None
        phone = re.sub(r"\s+", "", match.group(1))
        digits_only = re.sub(r"\D", "", phone)
        return phone if len(digits_only) >= 8 else None

    def _extract_name(self, text: str, awaiting_name: bool = False) -> str | None:
        message = (text or "").strip()
        if not message:
            return None

        patterns = [
            r"(?:my name is|i am|i'm)\s+([^\d,.;!?]+)",
            r"(?:jeg hedder|mit navn er|navn er)\s+([^\d,.;!?]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                name = match.group(1).strip(" .,!?:;")
                return name or None

        if awaiting_name and not self._extract_phone(message):
            candidate = message.strip(" .,!?:;")
            if 1 <= len(candidate.split()) <= 4 and not re.search(r"\d", candidate):
                return candidate
        return None

    def _extract_requested_time(self, text: str, state: _FallbackBookingState) -> str | None:
        match = re.search(r"\b(\d{1,2}:\d{2})\b", text or "")
        if not match:
            return None
        value = match.group(1)
        if value in state.available_times:
            return value
        return None

    def _looks_like_booking_confirmation(self, text: str) -> bool:
        normalized = (text or "").lower()
        return any(
            phrase in normalized
            for phrase in ["book it", "book it for me", "reserve it", "bestil", "book", "reserve"]
        )

    def _name_prompt(self, language: str) -> str:
        if language.startswith("da"):
            return "Jeg har dit telefonnummer. Hvad er navnet på personen, der skal bookes til?"
        return "I have your phone number. What is the name of the person for the booking?"

    def _register_available_slots(
        self,
        session_id: str,
        service_id: str,
        date: str,
        available_times: list[str],
    ) -> None:
        state = self._fallback_booking_state_for(session_id)
        state.service_id = service_id
        state.date = date
        state.available_times = list(available_times)
        state.selected_time = None
        state.awaiting_name = False

    def _capture_selected_time_from_reply(self, session_id: str, reply: str) -> None:
        state = self._fallback_booking_state_for(session_id)
        if not state.available_times:
            return
        mentioned = [
            slot for slot in state.available_times if slot in (reply or "")]
        if len(mentioned) == 1:
            state.selected_time = mentioned[0]
        elif state.selected_time is None and len(state.available_times) == 1:
            state.selected_time = state.available_times[0]

    def _complete_fallback_booking(
        self,
        session_id: str,
        request: ChatRequest,
        state: _FallbackBookingState,
    ) -> ChatResponse | None:
        text = request.message or ""
        if self._is_reset_message(text):
            self._reset_fallback_session(session_id)
            return None

        phone = self._extract_phone(text)
        if phone:
            state.customer_phone = phone

        name = self._extract_name(text, awaiting_name=state.awaiting_name)
        if name:
            state.customer_name = name

        explicit_time = self._extract_requested_time(text, state)
        if explicit_time:
            state.selected_time = explicit_time
        elif state.selected_time is None and len(state.available_times) == 1:
            state.selected_time = state.available_times[0]

        if not (state.service_id and state.date and state.selected_time):
            return None

        is_booking_follow_up = bool(
            phone) or state.awaiting_name or self._looks_like_booking_confirmation(text)
        if not is_booking_follow_up:
            return None

        if not state.customer_name:
            state.awaiting_name = True
            return ChatResponse(session_id=session_id, reply=self._name_prompt(request.language))

        if not state.customer_phone:
            return None

        state.awaiting_name = False
        output = self._dispatch["create_booking"](
            service_id=state.service_id,
            date=state.date,
            time=state.selected_time,
            phone=state.customer_phone,
            language=request.language,
            customer_name=state.customer_name,
            staff_name=state.staff_name,
        )
        data = json.loads(output)
        booking = BookingResponse(
            status=data.get("status", "confirmed"),
            booking_id=data.get("booking_id", ""),
            service_name=data.get("service_name", ""),
            start_time=data.get("start_time", ""),
            confirmation_text=data.get("confirmation_text", ""),
            staff_name=data.get("staff_name"),
        )
        self._fallback_booking_state[session_id] = _FallbackBookingState()
        return ChatResponse(
            session_id=session_id,
            reply=data.get("confirmation_text") or booking.confirmation_text,
            booking=booking,
        )

    def _answer_via_chat_completions(self, request: ChatRequest, session_id: str) -> ChatResponse:
        """Fallback path that uses chat completions with tool-calling."""
        resumed = self._complete_fallback_booking(
            session_id,
            request,
            self._fallback_booking_state_for(session_id),
        )
        if resumed is not None:
            return resumed

        messages = list(self._fallback_history_for(session_id))
        messages.append({"role": "user", "content": request.message or ""})
        booking_result: BookingResponse | None = None

        try:
            for _ in range(8):
                completion = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=_TOOLS_JSON,
                    tool_choice="auto",
                    temperature=0.2,
                )
                choice = completion.choices[0].message
                tool_calls = choice.tool_calls or []

                if not tool_calls:
                    messages.append(
                        {
                            "role": "assistant",
                            "content": choice.content or "How can I help you with your booking today?",
                        }
                    )
                    self._capture_selected_time_from_reply(
                        session_id, choice.content or ""
                    )
                    self._fallback_messages[session_id] = messages
                    return ChatResponse(
                        session_id=session_id,
                        reply=choice.content or "How can I help you with your booking today?",
                        booking=booking_result,
                    )

                assistant_message: dict = {
                    "role": "assistant", "content": choice.content or ""}
                assistant_message["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ]
                messages.append(assistant_message)

                for tc in tool_calls:
                    name = tc.function.name
                    args = json.loads(tc.function.arguments or "{}")
                    fn = self._dispatch.get(name)
                    if fn is None:
                        output = json.dumps({"error": f"Unknown tool: {name}"})
                    else:
                        try:
                            output = fn(**args)
                            if name == "get_availability":
                                data = json.loads(output)
                                self._register_available_slots(
                                    session_id,
                                    args.get("service_id", ""),
                                    args.get("date", ""),
                                    data.get("available_times", []),
                                )
                            if name == "get_staff_availability":
                                # Store the preferred staff in booking state so the
                                # rule-based completion path books with the right person.
                                data = json.loads(output)
                                state = self._fallback_booking_state_for(
                                    session_id)
                                # Match on first name OR full name (Setmore often stores first name only)
                                _PREF_TOKENS = {"sahar", "sahar ebrahim"}
                                chosen = next(
                                    (n for n in data
                                     if _normalize_person_name(n) in _PREF_TOKENS),
                                    next(iter(data), None),
                                )
                                if chosen:
                                    state.staff_name = chosen
                                # Also register service/date/slots so the rule-based
                                # path can finalise the booking without another LLM call.
                                all_slots = sorted({
                                    slot for slots in data.values() for slot in slots
                                })
                                self._register_available_slots(
                                    session_id,
                                    args.get("service_id", ""),
                                    args.get("date", ""),
                                    all_slots,
                                )
                            if name == "create_booking":
                                data = json.loads(output)
                                booking_result = BookingResponse(
                                    status=data.get("status", "confirmed"),
                                    booking_id=data.get("booking_id", ""),
                                    service_name=data.get("service_name", ""),
                                    start_time=data.get("start_time", ""),
                                    confirmation_text=data.get(
                                        "confirmation_text", ""),
                                    staff_name=data.get("staff_name"),
                                )
                                self._fallback_booking_state[session_id] = _FallbackBookingState(
                                )
                        except Exception as exc:
                            logger.exception(
                                "Tool %s raised in fallback: %s", name, exc)
                            output = json.dumps({"error": str(exc)})

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": output,
                        }
                    )

            return ChatResponse(
                session_id=session_id,
                reply="Sorry, I could not complete that request right now. Please try again.",
                booking=booking_result,
            )
        except Exception as exc:
            logger.exception("Chat completion fallback failed: %s", exc)
            return ChatResponse(
                session_id=session_id,
                reply=(
                    "The booking assistant is temporarily unavailable. "
                    "Please try again in a moment or book directly at "
                    "https://salonanova.setmore.com."
                ),
                booking=booking_result,
            )
