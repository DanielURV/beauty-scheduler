from fastapi import APIRouter, Form, Depends, Request, HTTPException
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.bot.conversation import handle_message
from src.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def validate_twilio_signature(request: Request, body: bytes) -> bool:
    if not settings.twilio_auth_token:
        return True  # Skip validation in dev
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    params = {}
    if request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        import urllib.parse
        params = dict(urllib.parse.parse_qsl(body.decode()))
    return validator.validate(url, params, signature)


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):
    raw_body = await request.body()

    if settings.twilio_auth_token and not validate_twilio_signature(request, raw_body):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    phone = From.replace("whatsapp:", "").strip()
    logger.info(f"Message from {phone}: {Body[:50]}")

    try:
        reply_text = handle_message(db, phone, Body)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        reply_text = "⚠️ Ocurrió un error. Por favor intenta de nuevo."

    twiml = MessagingResponse()
    twiml.message(reply_text)
    return Response(content=str(twiml), media_type="application/xml")


@router.get("/health")
async def health():
    return {"status": "ok", "business": settings.business_name}
