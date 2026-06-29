from src.config import settings
from src.bot import messages as msg

DIAS_SEMANA = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}


def welcome(name: str = None) -> str:
    greeting = f"¡Hola {name}! 👋" if name else "¡Hola! 👋"
    menu = msg.get("welcome_menu")
    return f"{greeting} Bienvenido/a a *{settings.business_name}*.\n\n{menu}"


def ask_name() -> str:
    return msg.get("ask_name")


def services_menu(services: list) -> str:
    lines = ["✨ *Nuestros servicios:*\n"]
    for i, s in enumerate(services, 1):
        lines.append(f"{i}. {s.name} - {s.price_formatted()} ({s.duration_minutes} min)")
    lines.append("\nEscribe el número del servicio que deseas 👇")
    return "\n".join(lines)


def dates_menu(dates: list) -> str:
    lines = ["📅 *Fechas disponibles:*\n"]
    for i, d in enumerate(dates, 1):
        day_name = DIAS_SEMANA[d.weekday()]
        lines.append(f"{i}. {day_name} {d.day}/{d.month}/{d.year}")
    lines.append("\nEscribe el número de la fecha 👇")
    return "\n".join(lines)


def times_menu(slots: list, tz) -> str:
    lines = ["🕐 *Horarios disponibles:*\n"]
    morning, afternoon = [], []
    for slot in slots:
        local = slot if slot.tzinfo else tz.localize(slot)
        (morning if local.hour < 14 else afternoon).append(local)

    i = 1
    if morning:
        lines.append("🌅 *Mañana*")
        for s in morning:
            lines.append(f"  {i}. {s.strftime('%H:%M')}")
            i += 1
    if afternoon:
        if morning:
            lines.append("")
        lines.append("☀️ *Tarde*")
        for s in afternoon:
            lines.append(f"  {i}. {s.strftime('%H:%M')}")
            i += 1

    lines.append("\nEscribe el número del horario 👇")
    return "\n".join(lines)


def confirm_appointment(service_name: str, date_str: str, time_str: str, price: str) -> str:
    return (
        f"📋 *Confirma tu cita:*\n\n"
        f"💅 Servicio: {service_name}\n"
        f"📅 Fecha: {date_str}\n"
        f"🕐 Hora: {time_str}\n"
        f"💰 Precio: {price}\n\n"
        "¿Confirmas? Escribe *SÍ* para confirmar o *NO* para cancelar."
    )


def appointment_confirmed(service_name: str, date_str: str, time_str: str) -> str:
    note = msg.get("appointment_confirmed_note")
    return (
        f"✅ *¡Cita confirmada!*\n\n"
        f"Te esperamos el *{date_str}* a las *{time_str}* para tu servicio de *{service_name}*.\n\n"
        f"{note}\n\n"
        "Escribe *menu* en cualquier momento para volver al menú principal."
    )


def no_slots_available() -> str:
    return msg.get("no_slots")


def your_appointments(appointments: list, tz) -> str:
    if not appointments:
        return msg.get("no_appointments")
    lines = ["📋 *Tus próximas citas:*\n"]
    for i, a in enumerate(appointments, 1):
        dt = tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at
        day_name = DIAS_SEMANA[dt.weekday()]
        lines.append(
            f"{i}. {a.service.name}\n"
            f"   📅 {day_name} {dt.day}/{dt.month} a las {dt.strftime('%H:%M')}\n"
            f"   ID: #{a.id}"
        )
    lines.append("\nEscribe *menu* para volver al inicio.")
    return "\n".join(lines)


def cancel_which_appointment(appointments: list, tz) -> str:
    if not appointments:
        return msg.get("no_appointments_cancel")
    lines = ["¿Qué cita deseas cancelar?\n"]
    for i, a in enumerate(appointments, 1):
        dt = tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at
        day_name = DIAS_SEMANA[dt.weekday()]
        lines.append(f"{i}. {a.service.name} - {day_name} {dt.day}/{dt.month} {dt.strftime('%H:%M')}")
    lines.append("\nEscribe el número o *menu* para volver.")
    return "\n".join(lines)


def appointment_cancelled(service_name: str) -> str:
    return msg.get("appointment_cancelled", servicio=service_name)


def invalid_option() -> str:
    return msg.get("invalid_option")


def error_message() -> str:
    return msg.get("error_generic")


def reminder_message(service_name: str, time_str: str) -> str:
    return msg.get("reminder", servicio=service_name, hora=time_str, negocio=settings.business_name)
