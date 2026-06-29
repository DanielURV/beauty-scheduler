from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List
import pytz


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_from: str = "whatsapp:+14155238886"

    # Google Gemini
    gemini_api_key: str = ""

    # Base de datos
    database_url: str = "sqlite:///./beauty_scheduler.db"

    # Negocio
    business_name: str = "Mi Estética"
    business_phone: str = ""
    business_timezone: str = "America/Bogota"
    business_open_time: str = "09:00"
    business_close_time: str = "19:00"
    business_working_days: str = "0,1,2,3,4,5"

    # Bridge de WhatsApp (whatsapp-web.js)
    bridge_url: str = "http://localhost:3000"

    # Recordatorios
    reminder_hours_before: int = 24

    # Panel de administración
    admin_password: str = "admin1234"
    admin_secret: str = "beauty-scheduler-secret-change-me"
    calendar_key: str = "cal-key-change-me"

    # Servidor
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    @property
    def working_days_list(self) -> List[int]:
        return [int(d.strip()) for d in self.business_working_days.split(",")]

    @property
    def timezone(self):
        return pytz.timezone(self.business_timezone)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
