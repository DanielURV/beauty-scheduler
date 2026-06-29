import google.generativeai as genai
from src.config import settings

SYSTEM_PROMPT = """Eres la asistente virtual de {business_name}, un salón de belleza y estética profesional.

Tu función es responder preguntas generales sobre servicios, precios, preparación, cuidados post-servicio y cualquier duda que tenga el cliente. Eres amable, profesional y concisa.

Información del negocio:
- Nombre: {business_name}
- Horario: {open_time} a {close_time}
- Días laborales: Lunes a Sábado
- Para agendar citas, los clientes deben escribir "menu" o "inicio"

Servicios disponibles:
{services_list}

Reglas:
- Responde siempre en español
- Sé amable y usa emojis moderadamente
- Si no sabes algo, pide que contacten directamente al salón
- No inventes precios ni información que no tengas
- Mantén las respuestas cortas (máximo 3-4 líneas)
- Si el cliente quiere agendar, dile que escriba "menu" o "inicio"
"""


def _build_system_prompt(services: list) -> str:
    services_text = "\n".join(
        f"- {s.name}: {s.price_formatted()} ({s.duration_minutes} min) - {s.description or ''}"
        for s in services
    )
    return SYSTEM_PROMPT.format(
        business_name=settings.business_name,
        open_time=settings.business_open_time,
        close_time=settings.business_close_time,
        services_list=services_text,
    )


def _to_gemini_history(history: list) -> list:
    """Convert Anthropic-style history to Gemini format."""
    result = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        result.append({"role": role, "parts": [msg["content"]]})
    return result


def get_ai_response(user_message: str, services: list, conversation_history: list = None) -> str:
    genai.configure(api_key=settings.gemini_api_key)

    system = _build_system_prompt(services)
    history = _to_gemini_history((conversation_history or [])[-10:])

    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system,
    )
    chat = model.start_chat(history=history)
    response = chat.send_message(user_message)
    return response.text
