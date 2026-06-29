import hmac
import hashlib
import os
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from src.models.database import Base

ROLES = ("superadmin", "admin", "viewer")


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False, default="admin")  # superadmin | admin | viewer
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16).hex()
        h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
        return f"{salt}:{h}"

    def verify_password(self, password: str) -> bool:
        try:
            salt, h = self.password_hash.split(":", 1)
            expected = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
            return hmac.compare_digest(h, expected)
        except Exception:
            return False
