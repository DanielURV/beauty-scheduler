import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.service import Service
from src.models.client import Client
from src.models.appointment import Appointment, AppointmentStatus
from src.models.conversation import ConversationState
from src.scheduling.appointment_service import (
    get_or_create_client, get_active_services, create_appointment, get_upcoming_appointments
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_service(db):
    service = Service(name="Corte", description="Corte de cabello", duration_minutes=45, price=35000)
    db.add(service)
    db.commit()
    return service


def test_create_client(db):
    client = get_or_create_client(db, "+57300000001")
    assert client.phone == "+57300000001"
    assert client.id is not None


def test_get_or_create_client_idempotent(db):
    c1 = get_or_create_client(db, "+57300000002")
    c2 = get_or_create_client(db, "+57300000002")
    assert c1.id == c2.id


def test_get_active_services(db, sample_service):
    services = get_active_services(db)
    assert len(services) == 1
    assert services[0].name == "Corte"


def test_create_appointment(db, sample_service):
    from datetime import datetime, timezone
    client = get_or_create_client(db, "+57300000003")
    scheduled = datetime(2030, 6, 10, 10, 0, tzinfo=timezone.utc)
    appt = create_appointment(db, client, sample_service, scheduled)
    assert appt.id is not None
    assert appt.status == AppointmentStatus.CONFIRMED


def test_get_upcoming_appointments(db, sample_service):
    from datetime import datetime, timezone
    client = get_or_create_client(db, "+57300000004")
    future = datetime(2030, 6, 15, 14, 0, tzinfo=timezone.utc)
    create_appointment(db, client, sample_service, future)
    appointments = get_upcoming_appointments(db, client)
    assert len(appointments) == 1
