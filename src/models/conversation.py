import json
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from src.models.database import Base


class ConversationState(Base):
    __tablename__ = "conversation_states"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), unique=True, nullable=False)
    state = Column(String, default="idle")
    context_json = Column(Text, default="{}")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    client = relationship("Client", back_populates="conversation")

    @property
    def context(self) -> dict:
        return json.loads(self.context_json or "{}")

    @context.setter
    def context(self, value: dict):
        self.context_json = json.dumps(value, ensure_ascii=False)
