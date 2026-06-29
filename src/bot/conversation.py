from sqlalchemy.orm import Session
from src.config import settings
from src.models.conversation import ConversationState
from src.models.client import Client
from src.scheduling import appointment_service as svc
from src.scheduling.availability import get_available_dates, get_available_slots
from src.bot import templates as t
from src.bot.messages import get as msg_get
from src.ai.assistant import get_ai_response
from datetime import datetime
import pytz

MENU_TRIGGERS = {"menu", "inicio", "hola", "hi", "hello", "start", "0", "ayuda", "help"}


def handle_message(db: Session, phone: str, text: str) -> str:
    text = text.strip()
    text_lower = text.lower()

    client = svc.get_or_create_client(db, phone)

    if client.is_blocked:
        return msg_get("blocked")

    conv = svc.get_conversation(db, client)

    if text_lower in MENU_TRIGGERS:
        svc.update_conversation(db, conv, "main_menu", {})
        return t.welcome(client.name)

    state = conv.state
    ctx = conv.context

    if state == "idle" or state == "main_menu":
        return _handle_main_menu(db, client, conv, text)

    if state == "collect_name":
        return _handle_collect_name(db, client, conv, text)

    if state == "select_service":
        return _handle_select_service(db, client, conv, text)

    if state == "select_date":
        return _handle_select_date(db, client, conv, text, ctx)

    if state == "select_time":
        return _handle_select_time(db, client, conv, text, ctx)

    if state == "confirm_appointment":
        return _handle_confirm_appointment(db, client, conv, text, ctx)

    if state == "view_appointments":
        svc.update_conversation(db, conv, "main_menu", {})
        return t.welcome(client.name)

    if state == "cancel_which":
        return _handle_cancel_which(db, client, conv, text, ctx)

    if state == "confirm_cancel":
        return _handle_confirm_cancel(db, client, conv, text, ctx)

    if state == "ai_chat":
        return _handle_ai_chat(db, client, conv, text, ctx)

    return t.welcome(client.name)


def _handle_main_menu(db: Session, client: Client, conv: ConversationState, text: str) -> str:
    if not client.name:
        svc.update_conversation(db, conv, "collect_name", {})
        return t.ask_name()

    if text == "1":
        services = svc.get_active_services(db)
        svc.update_conversation(db, conv, "select_service", {})
        return t.services_menu(services)

    if text == "2":
        appointments = svc.get_upcoming_appointments(db, client)
        svc.update_conversation(db, conv, "view_appointments", {})
        return t.your_appointments(appointments, settings.timezone)

    if text == "3":
        appointments = svc.get_upcoming_appointments(db, client)
        appt_ids = [a.id for a in appointments]
        svc.update_conversation(db, conv, "cancel_which", {"appointment_ids": appt_ids})
        return t.cancel_which_appointment(appointments, settings.timezone)

    if text == "4":
        svc.update_conversation(db, conv, "ai_chat", {"history": []})
        return msg_get("ai_chat_intro")

    svc.update_conversation(db, conv, "main_menu", {})
    return t.welcome(client.name)


def _handle_collect_name(db: Session, client: Client, conv: ConversationState, text: str) -> str:
    if len(text) < 2 or len(text) > 50:
        return msg_get("ask_name_invalid")
    client.name = text.title()
    db.commit()
    svc.update_conversation(db, conv, "main_menu", {})
    return t.welcome(client.name)


def _handle_select_service(db: Session, client: Client, conv: ConversationState, text: str) -> str:
    services = svc.get_active_services(db)
    try:
        idx = int(text) - 1
        service = services[idx]
    except (ValueError, IndexError):
        return t.invalid_option()

    dates = get_available_dates(db)
    if not dates:
        return msg_get("no_dates")

    svc.update_conversation(db, conv, "select_date", {
        "service_id": service.id,
        "dates": [d.isoformat() for d in dates],
    })
    return t.dates_menu(dates)


def _handle_select_date(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    from datetime import date
    dates = [date.fromisoformat(d) for d in ctx.get("dates", [])]
    try:
        idx = int(text) - 1
        chosen_date = dates[idx]
    except (ValueError, IndexError):
        return t.invalid_option()

    service = svc.get_service_by_id(db, ctx["service_id"])
    slots = get_available_slots(db, service, chosen_date)

    if not slots:
        return t.no_slots_available()

    svc.update_conversation(db, conv, "select_time", {
        "service_id": ctx["service_id"],
        "chosen_date": chosen_date.isoformat(),
        "slots": [s.isoformat() for s in slots],
    })
    return t.times_menu(slots, settings.timezone)


def _handle_select_time(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    slots = [datetime.fromisoformat(s) for s in ctx.get("slots", [])]
    try:
        idx = int(text) - 1
        chosen_slot = slots[idx]
    except (ValueError, IndexError):
        return t.invalid_option()

    service = svc.get_service_by_id(db, ctx["service_id"])
    tz = settings.timezone
    local_slot = tz.localize(chosen_slot) if chosen_slot.tzinfo is None else chosen_slot
    from datetime import date as dt_date
    chosen_date = dt_date.fromisoformat(ctx["chosen_date"])
    from src.bot.templates import DIAS_SEMANA
    day_name = DIAS_SEMANA[chosen_date.weekday()]
    date_str = f"{day_name} {chosen_date.day}/{chosen_date.month}/{chosen_date.year}"
    time_str = local_slot.strftime("%H:%M")

    svc.update_conversation(db, conv, "confirm_appointment", {
        "service_id": service.id,
        "slot_iso": chosen_slot.isoformat(),
        "date_str": date_str,
        "time_str": time_str,
    })
    return t.confirm_appointment(service.name, date_str, time_str, service.price_formatted())


def _handle_confirm_appointment(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    answer = text.lower().strip()
    if answer in ("sí", "si", "yes", "s", "1", "confirmar", "confirmo"):
        service = svc.get_service_by_id(db, ctx["service_id"])
        slot = datetime.fromisoformat(ctx["slot_iso"])
        try:
            appt = svc.create_appointment(db, client, service, slot)
        except ValueError:
            svc.update_conversation(db, conv, "main_menu", {})
            return msg_get("slot_taken")
        svc.update_conversation(db, conv, "main_menu", {})
        return t.appointment_confirmed(service.name, ctx["date_str"], ctx["time_str"])
    else:
        svc.update_conversation(db, conv, "main_menu", {})
        return msg_get("appointment_cancel_rejected")


def _handle_cancel_which(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    appointments = svc.get_upcoming_appointments(db, client)
    try:
        idx = int(text) - 1
        appt = appointments[idx]
    except (ValueError, IndexError):
        return t.invalid_option()

    tz = settings.timezone
    dt = tz.localize(appt.scheduled_at) if appt.scheduled_at.tzinfo is None else appt.scheduled_at
    from src.bot.templates import DIAS_SEMANA
    day_name = DIAS_SEMANA[dt.weekday()]
    svc.update_conversation(db, conv, "confirm_cancel", {"appointment_id": appt.id})
    return msg_get(
        "confirm_cancel_prompt",
        servicio=appt.service.name,
        dia=f"{day_name} {dt.day}/{dt.month}",
        hora=dt.strftime("%H:%M"),
    )


def _handle_confirm_cancel(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    answer = text.lower().strip()
    if answer in ("sí", "si", "yes", "s", "1"):
        appt = svc.cancel_appointment(db, ctx["appointment_id"], client)
        svc.update_conversation(db, conv, "main_menu", {})
        if appt:
            return t.appointment_cancelled(appt.service.name)
        return msg_get("appointment_cancel_error")
    else:
        svc.update_conversation(db, conv, "main_menu", {})
        return msg_get("appointment_not_cancelled")


def _handle_ai_chat(db: Session, client: Client, conv: ConversationState, text: str, ctx: dict) -> str:
    services = svc.get_active_services(db)
    history = ctx.get("history", [])
    reply = get_ai_response(text, services, list(history))
    history.append({"role": "user", "content": text})
    history.append({"role": "assistant", "content": reply})
    svc.update_conversation(db, conv, "ai_chat", {"history": history[-20:]})
    return reply
