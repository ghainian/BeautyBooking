import re
import uuid
from datetime import date, datetime, timedelta, timezone

from pydantic import BaseModel

from .booking_adapter import BookingAdapter
from .booking_models import BookingRequest, BookingResponse
from .localization import LANG_MAP


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    language: str = "da"


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    booking: BookingResponse | None = None


class BookingChatAgent:
    def __init__(self) -> None:
        self._adapter = BookingAdapter()
        self._sessions: dict[str, dict[str, str]] = {}
        self._supported_languages = tuple(LANG_MAP.keys())
        self._hour_words_en = {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
            "eleven": 11,
            "twelve": 12,
        }
        self._hour_words_da = {
            "et": 1,
            "to": 2,
            "tre": 3,
            "fire": 4,
            "fem": 5,
            "seks": 6,
            "syv": 7,
            "otte": 8,
            "ni": 9,
            "ti": 10,
            "elleve": 11,
            "tolv": 12,
        }
        self._weekday_da = {
            "mandag": 0,
            "tirsdag": 1,
            "onsdag": 2,
            "torsdag": 3,
            "fredag": 4,
            "lordag": 5,
            "sondag": 6,
        }
        self._weekday_en = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }
        self._weekday_fr = {
            "lundi": 0,
            "mardi": 1,
            "mercredi": 2,
            "jeudi": 3,
            "vendredi": 4,
            "samedi": 5,
            "dimanche": 6,
        }
        self._weekday_de = {
            "montag": 0,
            "dienstag": 1,
            "mittwoch": 2,
            "donnerstag": 3,
            "freitag": 4,
            "samstag": 5,
            "sonntag": 6,
        }
        self._weekday_zh = {
            "星期一": 0,
            "周一": 0,
            "星期二": 1,
            "周二": 1,
            "星期三": 2,
            "周三": 2,
            "星期四": 3,
            "周四": 3,
            "星期五": 4,
            "周五": 4,
            "星期六": 5,
            "周六": 5,
            "星期日": 6,
            "星期天": 6,
            "周日": 6,
            "周天": 6,
        }
        self._today_phrases = (
            "i dag", "idag", "today", "aujourd'hui", "aujourdhui", "heute", "今天",
        )
        self._tomorrow_phrases = (
            "i morgen", "imorgen", "tomorrow", "demain", "morgen", "明天",
        )
        self._next_week_phrases = (
            "naeste uge", "næste uge", "next week", "semaine prochaine",
            "naechste woche", "nächste woche", "下周",
        )
        self._opening_hours_keywords = (
            "opening", "open", "hours", "abning", "åbning", "aabning", "abent",
            "horaire", "horaires", "ouvert", "ouverte", "ferme", "fermé", "fermée",
            "offnungszeiten", "öffnungszeiten", "offen", "geoffnet", "geöffnet", "geschlossen",
            "营业", "营业时间", "开门", "关门",
        )
        self._team_keywords = (
            "team", "staff", "member", "members", "stylist", "stylists", "hairdresser",
            "medarbejder", "medarbejdere", "frisor", "frisør", "stylist",
            "equipe", "équipe", "coiffeur", "coiffeuse", "styliste", "stylistes",
            "teammitglieder", "mitarbeiter", "mitarbeiterinnen", "stylisten",
            "团队", "员工", "发型师", "造型师", "who works", "hvem", "arbejder",
            "qui travaille", "wer arbeitet",
        )
        self._language_cues = {
            "da": (
                "hej", "bestil", "booking", "klokken", "pris", "priser", "abning",
                "åbning", "aabning", "telefonnummer", "behandling", "herre klipning",
                "dame klip", "i morgen", "i dag", "tak", "hvem", "arbejder",
                "team", "abent", "naeste uge", "næste uge",
            ),
            "en": (
                "hello", "hi", "book", "booking", "opening hours", "opening", "hours",
                "price", "prices", "address", "phone", "tomorrow", "today", "haircut",
                "appointment", "thanks", "open", "next week", "who works", "team",
                "staff", "salon",
            ),
            "fr": (
                "bonjour", "salut", "rendez-vous", "horaire", "horaires", "prix",
                "adresse", "telephone", "téléphone", "coiffure", "coupe", "demain",
                "aujourd'hui", "aujourdhui", "merci", "reserver", "réserver",
                "qui travaille", "salon", "equipe", "équipe", "semaine prochaine",
            ),
            "de": (
                "hallo", "guten tag", "termin", "offnungszeiten", "öffnungszeiten",
                "preis", "preise", "adresse", "telefon", "haarschnitt", "morgen",
                "heute", "danke", "buchen", "uhr", "wer arbeitet", "team",
                "naechste woche", "nächste woche", "salon", "im salon",
            ),
            "zh": (),
        }

    def answer(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or f"chat-{uuid.uuid4().hex[:12]}"
        state = self._sessions.setdefault(session_id, {})
        normalized = (request.message or "").strip().lower()
        language = self._resolve_language(request.language, normalized)

        if not normalized:
            return ChatResponse(
                session_id=session_id,
                reply=self._translate(
                    language,
                    {
                        "da": "Skriv gerne hvad du vil booke, dato, tidspunkt og telefonnummer.",
                        "en": "Please share what you want to book, date, time, and phone number.",
                        "fr": "Indiquez ce que vous souhaitez reserver, la date, l'heure et le numero de telephone.",
                        "de": "Bitte teilen Sie mit, was Sie buchen mochten, sowie Datum, Uhrzeit und Telefonnummer.",
                        "zh": "请告诉我您想预约的服务、日期、时间和电话号码。",
                    },
                ),
            )

        if any(k in normalized for k in ("reset", "start over", "nulstil", "forfra")):
            self._sessions[session_id] = {}
            return ChatResponse(
                session_id=session_id,
                reply=self._translate(
                    language,
                    {
                        "da": "Klart, vi starter forfra. Hvilken behandling vil du booke?",
                        "en": "Sure, we can start over. Which service would you like to book?",
                        "fr": "Tres bien, nous recommencons. Quel service souhaitez-vous reserver ?",
                        "de": "Klar, wir fangen von vorne an. Welche Behandlung mochten Sie buchen?",
                        "zh": "好的，我们重新开始。您想预约什么服务？",
                    },
                ),
            )

        self._extract_slots(normalized, state, language)

        if self._is_opening_hours_query(normalized):
            return ChatResponse(
                session_id=session_id,
                reply=self._opening_hours_reply(
                    language=language, normalized=normalized),
            )

        if self._is_team_query(normalized):
            return ChatResponse(session_id=session_id, reply=self._team_text(language))

        if any(k in normalized for k in ("pris", "price", "koster", "cost")):
            return ChatResponse(
                session_id=session_id,
                reply=self._adapter.get_price_overview(language=language),
            )

        if any(k in normalized for k in ("service", "behandling", "klip", "services")) and "book" not in normalized and "bestil" not in normalized:
            services = self._adapter.list_services(language=language)
            lines = "; ".join(f"{s.name} ({s.price_label})" for s in services)
            return ChatResponse(
                session_id=session_id,
                reply=self._translate(
                    language,
                    {
                        "da": f"Her er vores behandlinger: {lines}.",
                        "en": f"Here are our services: {lines}.",
                        "fr": f"Voici nos services : {lines}.",
                        "de": f"Hier sind unsere Behandlungen: {lines}.",
                        "zh": f"以下是我们的服务：{lines}。",
                    },
                ),
            )

        booking_intent = any(k in normalized for k in (
            "book", "booking", "bestil", "tid", "appointment", "reserve"))
        has_all = all(state.get(k) for k in (
            "service_id", "service_date", "service_time", "customer_phone"))
        booking_context_started = all(state.get(k) for k in (
            "service_id", "service_date", "service_time"))

        if has_all and (booking_intent or booking_context_started):
            return self._finalize_booking(session_id=session_id, state=state, language=language)

        if any(k in normalized for k in ("address", "adresse", "where", "telefon", "phone", "instagram", "location")):
            return ChatResponse(
                session_id=session_id,
                reply=self._translate(
                    language,
                    {
                        "da": "Salon Anova ligger pa Amagerbrogade 219, 2300 Kobenhavn S. Telefon: +45 41 42 33 33. Booking-side: https://salonanova.setmore.com",
                        "en": "Salon Anova is at Amagerbrogade 219, 2300 Kobenhavn S. Phone: +45 41 42 33 33. Booking page: https://salonanova.setmore.com",
                        "fr": "Salon Anova se trouve a Amagerbrogade 219, 2300 Kobenhavn S. Telephone : +45 41 42 33 33. Page de reservation : https://salonanova.setmore.com",
                        "de": "Salon Anova befindet sich in der Amagerbrogade 219, 2300 Kobenhavn S. Telefon: +45 41 42 33 33. Buchungsseite: https://salonanova.setmore.com",
                        "zh": "Salon Anova 位于 Amagerbrogade 219, 2300 Kobenhavn S。电话：+45 41 42 33 33。预约页面：https://salonanova.setmore.com",
                    },
                ),
            )

        if booking_intent or any(state.get(k) for k in ("service_id", "service_date", "service_time", "customer_phone")):
            return ChatResponse(
                session_id=session_id,
                reply=self._booking_prompt(state=state, language=language),
            )

        return ChatResponse(
            session_id=session_id,
            reply=self._translate(
                language,
                {
                    "da": "Jeg kan hjaelpe med booking, priser, abningstider og kontaktinfo. Skriv fx: 'Bestil dame klip fredag klokken 10, mit nummer er +45 ...'",
                    "en": "I can help with bookings, prices, opening hours, and contact info. For example: 'Book ladies haircut Friday at 10, my number is +45 ...'",
                    "fr": "Je peux aider pour les reservations, les prix, les horaires d'ouverture et les coordonnees. Par exemple : 'Reserve une coupe femme vendredi a 10 h, mon numero est +45 ...'",
                    "de": "Ich kann bei Buchungen, Preisen, Offnungszeiten und Kontaktinformationen helfen. Zum Beispiel: 'Buche Damenhaarschnitt Freitag um 10 Uhr, meine Nummer ist +45 ...'",
                    "zh": "我可以帮助您处理预约、价格、营业时间和联系方式。例如：'预约女士剪发，周五10点，我的号码是 +45 ...'",
                },
            ),
        )

    def _finalize_booking(self, session_id: str, state: dict[str, str], language: str) -> ChatResponse:
        service_id = state["service_id"]
        service_date = state["service_date"]
        service_time = state["service_time"]
        requested_start = f"{service_date}T{service_time}:00+02:00"

        availability = self._adapter.get_availability(
            service_id=service_id, date=service_date)
        available_times = {
            slot.start_time[11:16]
            for slot in availability.slots
            if len(slot.start_time) >= 16
        }
        if service_time not in available_times:
            alternatives = ", ".join(sorted(available_times)) or self._translate(
                language,
                {
                    "da": "ingen",
                    "en": "none",
                    "fr": "aucun",
                    "de": "keine",
                    "zh": "没有",
                },
            )
            return ChatResponse(
                session_id=session_id,
                reply=self._translate(
                    language,
                    {
                        "da": f"Det tidspunkt er ikke ledigt. Ledige tider den dag er: {alternatives}.",
                        "en": f"That time is not available. Available times that day are: {alternatives}.",
                        "fr": f"Cet horaire n'est pas disponible. Les horaires disponibles ce jour-la sont : {alternatives}.",
                        "de": f"Diese Uhrzeit ist nicht verfugbar. Verfugbare Zeiten an diesem Tag sind: {alternatives}.",
                        "zh": f"该时间不可用。当天可预约时间为：{alternatives}。",
                    },
                ),
            )

        booking = self._adapter.create_booking(
            BookingRequest(
                customer_phone=state["customer_phone"],
                service_id=service_id,
                start_time=requested_start,
                language=language,
                idempotency_key=f"chat-{session_id}-{uuid.uuid4().hex[:6]}",
            )
        )
        state["booking_id"] = booking.booking_id
        return ChatResponse(
            session_id=session_id,
            booking=booking,
            reply=self._translate(
                language,
                {
                    "da": f"Perfekt. Din booking er oprettet: {booking.service_name} {service_date} kl. {service_time}. Booking-id: {booking.booking_id}.",
                    "en": f"Great. Your booking is confirmed: {booking.service_name} on {service_date} at {service_time}. Booking id: {booking.booking_id}.",
                    "fr": f"Parfait. Votre reservation est confirmee : {booking.service_name} le {service_date} a {service_time}. Identifiant de reservation : {booking.booking_id}.",
                    "de": f"Perfekt. Ihre Buchung ist bestatigt: {booking.service_name} am {service_date} um {service_time}. Buchungs-ID: {booking.booking_id}.",
                    "zh": f"很好。您的预约已确认：{booking.service_name}，日期 {service_date}，时间 {service_time}。预约编号：{booking.booking_id}。",
                },
            ),
        )

    def _extract_slots(self, normalized: str, state: dict[str, str], language: str) -> None:
        services = self._adapter.list_services(language=language)
        matched_service = False
        for service in services:
            name = service.name.lower()
            compact = name.replace(" ", "")
            if name in normalized or compact in normalized.replace(" ", ""):
                state["service_id"] = service.service_id
                state["service_name"] = service.name
                matched_service = True
                break

        if not matched_service and not state.get("service_id"):
            if any(k in normalized for k in ("book", "booking", "bestil", "tid", "appointment", "service", "klip")):
                fallback = services[0] if services else None
                for service in services:
                    if service.service_id == "haircut_ladies":
                        fallback = service
                        break
                if fallback is not None:
                    state["service_id"] = fallback.service_id
                    state["service_name"] = fallback.name

        # Accept local 8-digit numbers (e.g. Danish) and international formats.
        phone_match = re.search(r"(\+?\d[\d\s]{6,}\d)", normalized)
        if phone_match:
            state["customer_phone"] = phone_match.group(1).replace(" ", "")

        today = datetime.now(timezone.utc).date()
        target_date, _ = self._extract_date_reference(normalized, today)
        if target_date is not None:
            state["service_date"] = target_date.isoformat()

        time_match = re.search(
            r"\b(?:kl(?:okken)?\s*)?([0-2]?\d)(?:[:.]([0-5]\d))?\s*([ap]\.?m\.?)?\b", normalized)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or "00")
            meridiem = (time_match.group(3) or "").replace(".", "").lower()

            if meridiem and 1 <= hour <= 12:
                if meridiem == "am":
                    hour = 0 if hour == 12 else hour
                if meridiem == "pm":
                    hour = 12 if hour == 12 else hour + 12

            if 0 <= hour <= 23:
                state["service_time"] = f"{hour:02d}:{minute:02d}"
            return

        word_time = self._extract_word_time(normalized)
        if word_time:
            state["service_time"] = word_time

    def _extract_word_time(self, normalized: str) -> str | None:
        en_words = "|".join(self._hour_words_en.keys())
        da_words = "|".join(self._hour_words_da.keys())

        en_oclock = re.search(
            rf"\b(?:at\s+)?({en_words})\s*(am|pm)?\s*o'?clock\b",
            normalized,
        )
        if en_oclock:
            return self._build_time_from_word(
                hour_word=en_oclock.group(1),
                meridiem=en_oclock.group(2),
                language="en",
            )

        en_at = re.search(
            rf"\b(?:at\s+)({en_words})\s*(am|pm)\b",
            normalized,
        )
        if en_at:
            return self._build_time_from_word(
                hour_word=en_at.group(1),
                meridiem=en_at.group(2),
                language="en",
            )

        da_time = re.search(
            rf"\bkl(?:okken)?\s+({da_words})\b",
            normalized,
        )
        if da_time:
            return self._build_time_from_word(
                hour_word=da_time.group(1),
                meridiem=None,
                language="da",
            )

        return None

    def _build_time_from_word(self, hour_word: str, meridiem: str | None, language: str) -> str | None:
        if language == "en":
            hour = self._hour_words_en.get(hour_word)
        else:
            hour = self._hour_words_da.get(hour_word)

        if hour is None:
            return None

        normalized_meridiem = (meridiem or "").lower()
        if normalized_meridiem == "am":
            hour = 0 if hour == 12 else hour
        elif normalized_meridiem == "pm":
            hour = 12 if hour == 12 else hour + 12

        return f"{hour:02d}:00"

    def _extract_weekday(self, normalized: str) -> int | None:
        for word, weekday in self._weekday_da.items():
            if word in normalized:
                return weekday
        for word, weekday in self._weekday_en.items():
            if word in normalized:
                return weekday
        for word, weekday in self._weekday_fr.items():
            if word in normalized:
                return weekday
        for word, weekday in self._weekday_de.items():
            if word in normalized:
                return weekday
        for word, weekday in self._weekday_zh.items():
            if word in normalized:
                return weekday
        return None

    def _next_weekday(self, from_date: date, weekday: int) -> date:
        days_ahead = (weekday - from_date.weekday()) % 7
        days_ahead = 7 if days_ahead == 0 else days_ahead
        return from_date + timedelta(days=days_ahead)

    def _date_in_next_week(self, from_date: date, weekday: int) -> date:
        days_until_next_monday = 7 - from_date.weekday()
        if days_until_next_monday <= 0:
            days_until_next_monday += 7
        next_week_start = from_date + timedelta(days=days_until_next_monday)
        return next_week_start + timedelta(days=weekday)

    def _booking_prompt(self, state: dict[str, str], language: str) -> str:
        missing: list[str] = []
        if not state.get("service_id"):
            missing.append(self._missing_field_label(language, "service"))
        if not state.get("service_date"):
            missing.append(self._missing_field_label(language, "date"))
        if not state.get("service_time"):
            missing.append(self._missing_field_label(language, "time"))
        if not state.get("customer_phone"):
            missing.append(self._missing_field_label(language, "phone"))

        if not missing:
            return self._translate(
                language,
                {
                    "da": "Jeg har det hele. Skriv 'bekraeft booking' for at fortsaette.",
                    "en": "I have everything. Type 'confirm booking' to continue.",
                    "fr": "J'ai toutes les informations. Ecrivez 'confirmer la reservation' pour continuer.",
                    "de": "Ich habe alle Angaben. Schreiben Sie 'Buchung bestatigen', um fortzufahren.",
                    "zh": "我已经有全部信息。请输入“确认预约”以继续。",
                },
            )

        readable = ", ".join(missing)
        return self._translate(
            language,
            {
                "da": f"Jeg mangler: {readable}.",
                "en": f"I still need: {readable}.",
                "fr": f"Il me manque encore : {readable}.",
                "de": f"Ich brauche noch: {readable}.",
                "zh": f"我还需要：{readable}。",
            },
        )

    def _opening_hours_text(self, language: str) -> str:
        return self._translate(
            language,
            {
                "da": "Abningstider: Man-Fre 09:30-18:00, Lor 09:30-16:00, Son lukket. Adresse: Amagerbrogade 219, 2300 Kobenhavn S.",
                "en": "Opening hours: Mon-Fri 09:30-18:00, Sat 09:30-16:00, Sun closed. Address: Amagerbrogade 219, 2300 Kobenhavn S.",
                "fr": "Horaires d'ouverture : lun-ven 09:30-18:00, sam 09:30-16:00, dim ferme. Adresse : Amagerbrogade 219, 2300 Kobenhavn S.",
                "de": "Offnungszeiten: Mo-Fr 09:30-18:00, Sa 09:30-16:00, So geschlossen. Adresse: Amagerbrogade 219, 2300 Kobenhavn S.",
                "zh": "营业时间：周一至周五 09:30-18:00，周六 09:30-16:00，周日休息。地址：Amagerbrogade 219, 2300 Kobenhavn S。",
            },
        )

    def _opening_hours_reply(self, language: str, normalized: str) -> str:
        today = datetime.now(timezone.utc).date()
        target_date, reference_kind = self._extract_date_reference(
            normalized, today)

        if reference_kind == "next_week":
            return self._translate(
                language,
                {
                    "da": "Naeste uge folger vi de normale abningstider: Man-Fre 09:30-18:00, Lor 09:30-16:00, Son lukket.",
                    "en": "Next week we follow the regular opening hours: Mon-Fri 09:30-18:00, Sat 09:30-16:00, Sun closed.",
                    "fr": "La semaine prochaine, nous suivons les horaires habituels : lun-ven 09:30-18:00, sam 09:30-16:00, dim ferme.",
                    "de": "Nächste Woche gelten unsere normalen Offnungszeiten: Mo-Fr 09:30-18:00, Sa 09:30-16:00, So geschlossen.",
                    "zh": "下周我们按照正常营业时间营业：周一至周五 09:30-18:00，周六 09:30-16:00，周日休息。",
                },
            )

        if target_date is None:
            return self._opening_hours_text(language)

        schedule = self._schedule_for_date(target_date)
        if schedule is None:
            return self._translate(
                language,
                {
                    "da": f"Den {target_date.isoformat()} har vi lukket.",
                    "en": f"We are closed on {target_date.isoformat()}.",
                    "fr": f"Nous sommes fermes le {target_date.isoformat()}.",
                    "de": f"Am {target_date.isoformat()} haben wir geschlossen.",
                    "zh": f"我们在 {target_date.isoformat()} 不营业。",
                },
            )

        return self._translate(
            language,
            {
                "da": f"Den {target_date.isoformat()} har vi abent {schedule}.",
                "en": f"We are open on {target_date.isoformat()} from {schedule}.",
                "fr": f"Nous sommes ouverts le {target_date.isoformat()} de {schedule}.",
                "de": f"Am {target_date.isoformat()} haben wir von {schedule} geoffnet.",
                "zh": f"我们在 {target_date.isoformat()} 的营业时间为 {schedule}。",
            },
        )

    def _team_text(self, language: str) -> str:
        return self._translate(
            language,
            {
                "da": "Hjemmesiden beskriver, at salonen har erfarne stylister, som arbejder med produkter af hoj kvalitet i afslappede omgivelser. Der star ikke navne pa individuelle teammedlemmer pa websitet.",
                "en": "The website says the salon has experienced stylists who use high quality products in a relaxed atmosphere. It does not list individual team member names.",
                "fr": "Le site indique que le salon compte des stylistes experimentes utilisant des produits de haute qualite dans une atmosphere detendue. Les noms des membres de l'equipe ne sont pas indiques sur le site.",
                "de": "Laut Website arbeitet der Salon mit erfahrenen Stylisten und hochwertigen Produkten in entspannter Atmosphare. Einzelne Teammitglieder werden auf der Website nicht namentlich aufgefuhrt.",
                "zh": "网站说明沙龙拥有经验丰富的造型师，使用高品质产品，并提供轻松的环境。网站上没有列出具体团队成员姓名。",
            },
        )

    def _missing_field_label(self, language: str, field: str) -> str:
        labels = {
            "service": {
                "da": "behandling",
                "en": "service",
                "fr": "service",
                "de": "Behandlung",
                "zh": "服务",
            },
            "date": {
                "da": "dato",
                "en": "date",
                "fr": "date",
                "de": "Datum",
                "zh": "日期",
            },
            "time": {
                "da": "tidspunkt",
                "en": "time",
                "fr": "heure",
                "de": "Uhrzeit",
                "zh": "时间",
            },
            "phone": {
                "da": "telefonnummer",
                "en": "phone number",
                "fr": "numero de telephone",
                "de": "Telefonnummer",
                "zh": "电话号码",
            },
        }
        return labels.get(field, {}).get(language, labels.get(field, {}).get("en", field))

    def _normalize_language(self, language: str | None) -> str | None:
        if not language:
            return None
        normalized = language.lower().strip()
        if normalized in LANG_MAP:
            return normalized
        prefix = normalized.split("-", 1)[0]
        if prefix in LANG_MAP:
            return prefix
        return None

    def _resolve_language(self, requested_language: str | None, normalized_message: str) -> str:
        detected_language = self._detect_language(normalized_message)
        if detected_language:
            return detected_language
        requested = self._normalize_language(requested_language)
        if requested:
            return requested
        return "da"

    def _detect_language(self, normalized_message: str) -> str | None:
        if re.search(r"[\u4e00-\u9fff]", normalized_message):
            return "zh"

        scores = {language: 0 for language in self._supported_languages}
        for language, cues in self._language_cues.items():
            for cue in cues:
                if cue in normalized_message:
                    scores[language] += 1

        best_language = max(scores, key=scores.get)
        if scores[best_language] == 0:
            return None
        return best_language

    def _extract_date_reference(self, normalized: str, today: date) -> tuple[date | None, str | None]:
        date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", normalized)
        if date_match:
            return date.fromisoformat(date_match.group(1)), "absolute"

        weekday = self._extract_weekday(normalized)
        if self._contains_phrase(normalized, self._next_week_phrases):
            if weekday is not None:
                return self._date_in_next_week(today, weekday), "next_week_weekday"
            return today + timedelta(days=7), "next_week"

        if self._contains_phrase(normalized, self._tomorrow_phrases):
            return today + timedelta(days=1), "tomorrow"

        if self._contains_phrase(normalized, self._today_phrases):
            return today, "today"

        if weekday is not None:
            return self._next_weekday(today, weekday), "weekday"

        return None, None

    def _schedule_for_date(self, target_date: date) -> str | None:
        weekday = target_date.weekday()
        if 0 <= weekday <= 4:
            return "09:30-18:00"
        if weekday == 5:
            return "09:30-16:00"
        return None

    def _is_opening_hours_query(self, normalized: str) -> bool:
        return self._contains_phrase(normalized, self._opening_hours_keywords)

    def _is_team_query(self, normalized: str) -> bool:
        return self._contains_phrase(normalized, self._team_keywords)

    def _contains_phrase(self, normalized: str, phrases: tuple[str, ...]) -> bool:
        return any(phrase in normalized for phrase in phrases)

    def _translate(self, language: str, translations: dict[str, str]) -> str:
        normalized_language = self._normalize_language(language) or "da"
        return (
            translations.get(normalized_language)
            or translations.get("en")
            or translations.get("da")
            or next(iter(translations.values()))
        )
