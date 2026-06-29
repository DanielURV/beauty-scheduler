import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

from src.models.database import Base
from src.models.service import Service
from src.bot.conversation import handle_message


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    service = Service(name="Corte", description="Corte básico", duration_minutes=45, price=35000)
    session.add(service)
    session.commit()
    yield session
    session.close()


def test_welcome_on_hola(db):
    response = handle_message(db, "+57300000010", "hola")
    assert "Bienvenido" in response or "nombre" in response.lower()


def test_welcome_on_menu(db):
    handle_message(db, "+57300000011", "hola")
    handle_message(db, "+57300000011", "Test User")
    response = handle_message(db, "+57300000011", "menu")
    assert "Agendar" in response


def test_select_service_flow(db):
    handle_message(db, "+57300000012", "hola")
    handle_message(db, "+57300000012", "Test User")
    response = handle_message(db, "+57300000012", "1")
    assert "Corte" in response


def test_invalid_option(db):
    handle_message(db, "+57300000013", "hola")
    handle_message(db, "+57300000013", "Pepe")
    handle_message(db, "+57300000013", "1")
    response = handle_message(db, "+57300000013", "99")
    assert "No entendí" in response or "opción" in response.lower()
