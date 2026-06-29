from fastapi import APIRouter, Form, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from src.models.database import get_db
from src.bot.conversation import handle_message
from src.config import settings
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(
    From: str = Form(...),
    Body: str = Form(...),
    db: Session = Depends(get_db),
):
    # From comes as "+521234567890" from the bridge
    phone = From.replace("whatsapp:", "").strip()
    logger.info(f"Message from {phone}: {Body[:50]}")

    try:
        reply_text = handle_message(db, phone, Body)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        reply_text = "⚠️ Ocurrió un error. Por favor intenta de nuevo."

    return JSONResponse({"reply": reply_text})


@router.get("/health")
async def health():
    return {"status": "ok", "business": settings.business_name}
