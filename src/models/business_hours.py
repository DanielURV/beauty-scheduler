from sqlalchemy import Column, Integer, String, Boolean, Date
from src.models.database import Base


class BusinessHours(Base):
    __tablename__ = "business_hours"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    working_days = Column(String, nullable=False, default="0,1,2,3,4,5")
    open_time = Column(String, nullable=False, default="09:00")
    close_time = Column(String, nullable=False, default="19:00")
    break_start = Column(String, nullable=True)  # ej. "14:00"
    break_end = Column(String, nullable=True)    # ej. "16:00"
    valid_from = Column(Date, nullable=True)
    valid_to = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    priority = Column(Integer, default=0)
