import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.appointment import Appointment, AppointmentStatus
from src.models.client import Client
from src.models.service import Service
from src.models.conversation import ConversationState


def get_or_create_client(db: Session, phone: str) -> Client:
    client = db.query(Client).filter(Client.phone == phone).first()
    if not client:
        client = Client(phone=phone)
        db.add(client)
        db.flush()
        conv = ConversationState(client_id=client.id)
        db.add(conv)
        db.commit()
        db.refresh(client)
    return client


def get_conversation(db: Session, client: Client) -> ConversationState:
    conv = db.query(ConversationState).filter(ConversationState.client_id == client.id).first()
    if not conv:
        conv = ConversationState(client_id=client.id)
        db.add(conv)
        db.commit()
        db.refresh(conv)
    return conv


def update_conversation(db: Session, conv: ConversationState, state: str, context: dict):
    conv.state = state
    conv.context = context
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()


def get_active_services(db: Session) -> List[Service]:
    return db.query(Service).filter(Service.is_active == True).all()


def get_service_by_id(db: Session, service_id: int) -> Optional[Service]:
    return db.query(Service).filter(Service.id == service_id).first()


def create_appointment(db: Session, client: Client, service: Service, scheduled_at: datetime) -> Appointment:
    slot_start = scheduled_at.replace(tzinfo=None)
    slot_end = slot_start + timedelta(minutes=service.duration_minutes)

    # Verificar que el hueco sigue libre en el momento de confirmar
    conflict = db.query(Appointment).filter(
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
        Appointment.scheduled_at < slot_end,
    ).join(Appointment.service).filter(
        (Appointment.scheduled_at + timedelta(minutes=service.duration_minutes)) > slot_start
    ).first()

    if conflict:
        raise ValueError("slot_taken")

    appt = Appointment(
        client_id=client.id,
        service_id=service.id,
        scheduled_at=slot_start,
        status=AppointmentStatus.CONFIRMED,
    )
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return appt


def get_upcoming_appointments(db: Session, client: Client) -> List[Appointment]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return (
        db.query(Appointment)
        .filter(
            Appointment.client_id == client.id,
            Appointment.status == AppointmentStatus.CONFIRMED,
            Appointment.scheduled_at >= now,
        )
        .order_by(Appointment.scheduled_at)
        .limit(5)
        .all()
    )


def cancel_appointment(db: Session, appointment_id: int, client: Client) -> Optional[Appointment]:
    appt = db.query(Appointment).filter(
        Appointment.id == appointment_id,
        Appointment.client_id == client.id,
        Appointment.status == AppointmentStatus.CONFIRMED,
    ).first()
    if appt:
        appt.status = AppointmentStatus.CANCELLED
        db.commit()
        db.refresh(appt)
    return appt


def seed_services(db: Session):
    import os, json as _json
    services_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "services.json")
    if db.query(Service).count() > 0:
        return
    with open(services_path, encoding="utf-8") as f:
        services_data = _json.load(f)
    for s in services_data:
        db.add(Service(**s))
    db.commit()
