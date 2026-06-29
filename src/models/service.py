from sqlalchemy import Column, Integer, String, Float, Boolean
from sqlalchemy.orm import relationship
from src.models.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=60)
    price = Column(Float, nullable=False, default=0)
    is_active = Column(Boolean, default=True)

    appointments = relationship("Appointment", back_populates="service")

    def price_formatted(self) -> str:
        return f"{self.price:,.2f} €"
