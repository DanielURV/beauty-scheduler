import logging
import uvicorn
from fastapi import FastAPI
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

from src.config import settings
from src.models.database import init_db, SessionLocal
from src.models.appointment import Appointment, AppointmentStatus
from src.api.webhook import router as webhook_router
from src.api.admin import router as admin_router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def send_reminders():
    """Send WhatsApp reminders for appointments in the next 24 hours."""
    import httpx

    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start = now + timedelta(hours=settings.reminder_hours_before - 1)
        window_end = now + timedelta(hours=settings.reminder_hours_before + 1)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == AppointmentStatus.CONFIRMED,
                Appointment.reminder_sent == "false",
                Appointment.scheduled_at >= window_start,
                Appointment.scheduled_at <= window_end,
            )
            .all()
        )

        if not appointments:
            return

        tz = settings.timezone

        from src.bot.templates import reminder_message

        async with httpx.AsyncClient(timeout=10) as http:
            for appt in appointments:
                dt = tz.localize(appt.scheduled_at)
                msg = reminder_message(
                    service_name=appt.service.name,
                    time_str=dt.strftime("%H:%M"),
                )
                try:
                    await http.post(
                        f"{settings.bridge_url}/send",
                        json={"to": appt.client.phone, "message": msg},
                    )
                    appt.reminder_sent = "true"
                    db.commit()
                    logger.info(f"Reminder sent to {appt.client.phone} for appointment #{appt.id}")
                except Exception as e:
                    logger.error(f"Failed to send reminder to {appt.client.phone}: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.business_name} Bot...")
    init_db()

    from src.scheduling.appointment_service import seed_services
    db = SessionLocal()
    try:
        seed_services(db)
    finally:
        db.close()

    scheduler.add_job(send_reminders, IntervalTrigger(hours=1), id="reminders")
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown()


app = FastAPI(
    title=f"{settings.business_name} - WhatsApp Bot",
    description="Bot de agendación de citas por WhatsApp",
    version="1.0.0",
    lifespan=lifespan,
)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_STATIC_DIR = os.path.join(_BASE_DIR, "static")
_ADMIN_HTML = os.path.join(_STATIC_DIR, "admin.html")

app.include_router(webhook_router, tags=["WhatsApp"])
app.include_router(admin_router, tags=["Admin"])
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


@app.get("/admin", include_in_schema=False)
def admin_page():
    with open(_ADMIN_HTML, encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.app_host,
        port=settings.app_port,
    )
