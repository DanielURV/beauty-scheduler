import json
import os

_MESSAGES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "messages.json")

_DEFAULTS = {
    "blocked": (
        "Hola 👋 Debido a incidencias recientes con tus citas, la reserva online no está disponible para ti en este momento.\n\n"
        "Para gestionar tu próxima cita te pedimos que te pases por el salón o nos llames directamente. Estaremos encantados de atenderte en persona. 😊"
    ),
    "ask_name": "¿Cuál es tu nombre? 😊",
    "welcome_menu": (
        "¿En qué te puedo ayudar?\n\n"
        "1️⃣ Agendar una cita\n"
        "2️⃣ Ver mis citas\n"
        "3️⃣ Cancelar una cita\n"
        "4️⃣ Preguntas / Información\n\n"
        "Responde con el número de tu opción 👇"
    ),
    "appointment_confirmed_note": "📍 Recuerda llegar 5 minutos antes.\nTe enviaremos un recordatorio 24 horas antes.",
    "appointment_cancelled": "✅ Tu cita de *{servicio}* ha sido cancelada.\n\nSi deseas agendar otra, escribe *menu*.",
    "appointment_not_cancelled": "De acuerdo, tu cita sigue confirmada. 😊 Escribe *menu* para volver al inicio.",
    "appointment_cancel_rejected": "Cita cancelada. Escribe *menu* para volver al inicio.",
    "appointment_cancel_error": "No se pudo cancelar la cita. Escribe *menu* para volver.",
    "no_slots": (
        "😔 Lo siento, no hay horarios disponibles para esa fecha.\n\n"
        "¿Deseas buscar en otra fecha? Escribe *1* para sí o *menu* para volver al inicio."
    ),
    "no_appointments": "📋 No tienes citas programadas próximamente.\n\nEscribe *menu* para volver al inicio.",
    "no_appointments_cancel": "📋 No tienes citas para cancelar.\n\nEscribe *menu* para volver al inicio.",
    "invalid_option": "❓ No entendí tu respuesta. Por favor escribe el número de la opción deseada o *menu* para volver al inicio.",
    "error_generic": "⚠️ Ocurrió un error. Por favor intenta de nuevo o escribe *menu*.",
    "ask_name_invalid": "Por favor escribe tu nombre completo.",
    "no_dates": "😔 No hay fechas disponibles próximamente. Contáctanos directamente.",
    "ai_chat_intro": "💬 ¡Claro! Puedes preguntarme lo que quieras sobre nuestros servicios.\nEscribe *menu* cuando quieras volver al inicio.",
    "slot_taken": "😔 Lo sentimos, ese horario acaba de ser reservado por otra persona.\n\nEscribe *1* para buscar otra fecha o *menu* para volver al inicio.",
    "confirm_cancel_prompt": "¿Confirmas que deseas cancelar tu cita de *{servicio}* el *{dia}* a las *{hora}*?\n\nEscribe *SÍ* para cancelar o *NO* para conservarla.",
    "reminder": "🔔 Recordatorio: mañana tienes cita de *{servicio}* a las *{hora}*. ¡Te esperamos en {negocio}!",
}


def load() -> dict:
    try:
        with open(_MESSAGES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except Exception:
        return dict(_DEFAULTS)


def get(key: str, **kwargs) -> str:
    """Get a message by key, interpolating {variables}."""
    text = load().get(key, _DEFAULTS.get(key, ""))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except KeyError:
            pass
    return text


def save(messages: dict):
    os.makedirs(os.path.dirname(_MESSAGES_FILE), exist_ok=True)
    current = load()
    current.update({k: v for k, v in messages.items() if k in _DEFAULTS})
    with open(_MESSAGES_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)


def all_keys() -> dict:
    """Returns all message keys with their default values for the API."""
    return dict(_DEFAULTS)
