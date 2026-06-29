import hmac
import hashlib
import base64
import json
import os
from datetime import datetime, date, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.models.database import get_db
from src.models.service import Service
from src.models.appointment import Appointment, AppointmentStatus
from src.models.client import Client
from src.models.business_hours import BusinessHours
from src.models.admin_user import AdminUser, ROLES
from src.config import settings

router = APIRouter()
security = HTTPBearer()

# ── Token helpers ─────────────────────────────────────────────────────────────

def _make_token(user_id: int, username: str, role: str) -> str:
    payload = json.dumps({"id": user_id, "u": username, "r": role}, separators=(",", ":"))
    payload_b64 = base64.urlsafe_b64encode(payload.encode()).decode()
    sig = hmac.new(settings.admin_secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"


def _decode_token(token: str) -> dict:
    try:
        payload_b64, sig = token.rsplit(".", 1)
        expected = hmac.new(settings.admin_secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError
        return json.loads(base64.urlsafe_b64decode(payload_b64).decode())
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")


def require_auth(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return _decode_token(credentials.credentials)


def require_superadmin(info: dict = Depends(require_auth)) -> dict:
    if info.get("r") != "superadmin":
        raise HTTPException(status_code=403, detail="Requiere rol superadmin")
    return info


def _ensure_default_superadmin(db: Session):
    """Create default superadmin from settings if no admin users exist."""
    if db.query(AdminUser).count() == 0:
        u = AdminUser(
            username="admin",
            password_hash=AdminUser.hash_password(settings.admin_password),
            role="superadmin",
        )
        db.add(u)
        db.commit()


# ── Login ─────────────────────────────────────────────────────────────────────

class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/admin/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    _ensure_default_superadmin(db)
    user = db.query(AdminUser).filter(
        AdminUser.username == body.username,
        AdminUser.is_active == True,
    ).first()
    if not user or not user.verify_password(body.password):
        raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")
    return {
        "token": _make_token(user.id, user.username, user.role),
        "username": user.username,
        "role": user.role,
    }


# ── Info ──────────────────────────────────────────────────────────────────────

@router.get("/admin/api/info")
def get_info(info: dict = Depends(require_auth)):
    from src.bot.business_config import load as load_biz
    biz = load_biz()
    return {
        "business_name": settings.business_name,
        "business_phone": settings.business_phone,
        "calendar_key": settings.calendar_key,
        "timezone": settings.business_timezone,
        "username": info["u"],
        "role": info["r"],
        "business_emoji": biz.get("emoji", "✂️"),
    }


class BizConfigIn(BaseModel):
    emoji: Optional[str] = None

@router.put("/admin/api/biz-config")
def set_biz_config(body: BizConfigIn, info: dict = Depends(require_superadmin)):
    from src.bot.business_config import save as save_biz
    save_biz({k: v for k, v in body.dict().items() if v is not None})
    return {"ok": True}


@router.get("/admin/api/hours-for-date")
def hours_for_date(date: str = Query(...), db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    from src.scheduling.availability import _get_hours_for_date
    from datetime import date as dt_date
    d = dt_date.fromisoformat(date)
    open_time, close_time, _, break_start, break_end = _get_hours_for_date(db, d)
    return {"open_time": open_time, "close_time": close_time, "break_start": break_start, "break_end": break_end}


# ── Admin Users ───────────────────────────────────────────────────────────────

class AdminUserIn(BaseModel):
    username: str
    password: str
    role: str = "admin"


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/admin/api/users")
def list_users(db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    users = db.query(AdminUser).order_by(AdminUser.username).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.date().isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.post("/admin/api/users", status_code=201)
def create_user(body: AdminUserIn, db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    if body.role not in ROLES:
        raise HTTPException(400, f"Rol inválido. Opciones: {', '.join(ROLES)}")
    if db.query(AdminUser).filter(AdminUser.username == body.username).first():
        raise HTTPException(409, "Ya existe un usuario con ese nombre")
    u = AdminUser(
        username=body.username.strip().lower(),
        password_hash=AdminUser.hash_password(body.password),
        role=body.role,
    )
    db.add(u)
    db.commit()
    return {"id": u.id}


@router.put("/admin/api/users/{uid}")
def update_user(uid: int, body: AdminUserUpdate, db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    u = db.get(AdminUser, uid)
    if not u:
        raise HTTPException(404)
    if uid == info["id"] and body.is_active is False:
        raise HTTPException(400, "No puedes desactivar tu propia cuenta")
    if body.role is not None:
        if body.role not in ROLES:
            raise HTTPException(400, "Rol inválido")
        u.role = body.role
    if body.password:
        u.password_hash = AdminUser.hash_password(body.password)
    if body.is_active is not None:
        u.is_active = body.is_active
    db.commit()
    return {"ok": True}


@router.delete("/admin/api/users/{uid}")
def delete_user(uid: int, db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    u = db.get(AdminUser, uid)
    if not u:
        raise HTTPException(404)
    if uid == info["id"]:
        raise HTTPException(400, "No puedes eliminar tu propia cuenta")
    db.delete(u)
    db.commit()
    return {"ok": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/admin/api/stats")
def get_stats(db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    tz = settings.timezone
    now_local = datetime.now(tz)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    today_end = today_start + timedelta(days=1)
    week_end = today_start + timedelta(days=7)
    month_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)

    today_count = db.query(Appointment).filter(
        Appointment.scheduled_at >= today_start, Appointment.scheduled_at < today_end,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
    ).count()

    week_count = db.query(Appointment).filter(
        Appointment.scheduled_at >= today_start, Appointment.scheduled_at < week_end,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
    ).count()

    month_appts = db.query(Appointment).filter(
        Appointment.scheduled_at >= month_start,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED]),
    ).all()

    return {
        "today": today_count,
        "week": week_count,
        "total_clients": db.query(Client).count(),
        "blocked_clients": db.query(Client).filter(Client.is_blocked == True).count(),
        "total_confirmed": db.query(Appointment).filter(Appointment.status == AppointmentStatus.CONFIRMED).count(),
        "month_revenue": sum(a.service.price for a in month_appts),
    }


# ── Today appointments ────────────────────────────────────────────────────────

@router.get("/admin/api/appointments/today")
def today_appointments(db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    tz = settings.timezone
    now_local = datetime.now(tz)
    start = now_local.replace(hour=0, minute=0, second=0, microsecond=0).replace(tzinfo=None)
    end = start + timedelta(days=1)

    appts = (
        db.query(Appointment)
        .filter(
            Appointment.scheduled_at >= start, Appointment.scheduled_at < end,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
        )
        .order_by(Appointment.scheduled_at)
        .all()
    )
    return [
        {
            "id": a.id,
            "time": tz.localize(a.scheduled_at).strftime("%H:%M"),
            "client_name": a.client.name or "Sin nombre",
            "client_phone": a.client.phone,
            "service_name": a.service.name,
            "duration": a.service.duration_minutes,
            "status": a.status,
        }
        for a in appts
    ]


# ── Calendar events ───────────────────────────────────────────────────────────

_PALETTE = ["#6f42c1","#e91e63","#2196f3","#4caf50","#ff9800","#00bcd4","#9c27b0","#795548","#607d8b","#f44336"]
_STATUS_COLORS = {
    AppointmentStatus.PENDING: "#fd7e14",
    AppointmentStatus.COMPLETED: "#6c757d",
    AppointmentStatus.CANCELLED: "#dc3545",
    AppointmentStatus.NO_SHOW: "#343a40",
}


@router.get("/admin/api/calendar-events")
def calendar_events(
    date_from: str = Query(...), date_to: str = Query(...),
    db: Session = Depends(get_db), info: dict = Depends(require_auth),
):
    from src.models.business_hours import BusinessHours
    from datetime import date as dt_date
    from sqlalchemy import or_

    range_start = datetime.fromisoformat(date_from)
    range_end = datetime.fromisoformat(date_to) + timedelta(days=1)
    appts = db.query(Appointment).filter(
        Appointment.scheduled_at >= range_start, Appointment.scheduled_at < range_end,
        Appointment.status != AppointmentStatus.CANCELLED,
    ).all()

    tz = settings.timezone
    services = db.query(Service).order_by(Service.id).all()
    color_map = {s.id: _PALETTE[i % len(_PALETTE)] for i, s in enumerate(services)}

    events = [
        {
            "id": f"appt-{a.id}",
            "title": f"{a.service.name} · {a.client.name or a.client.phone}",
            "start": (tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at).isoformat(),
            "end": ((tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at) + timedelta(minutes=a.service.duration_minutes)).isoformat(),
            "backgroundColor": _STATUS_COLORS.get(a.status) or color_map.get(a.service_id, "#6f42c1"),
            "borderColor": _STATUS_COLORS.get(a.status) or color_map.get(a.service_id, "#6f42c1"),
            "extendedProps": {
                "appointment_id": a.id, "status": a.status,
                "client_name": a.client.name or "Sin nombre", "client_phone": a.client.phone,
                "service_name": a.service.name, "service_id": a.service_id,
                "duration": a.service.duration_minutes, "price": a.service.price,
                "notes": a.notes or "", "scheduled_at": a.scheduled_at.isoformat(),
            },
        }
        for a in appts
    ]

    # Add manual time blocks as background events
    blocks = db.query(TimeBlock).filter(
        TimeBlock.date >= range_start.date(),
        TimeBlock.date <= range_end.date(),
    ).all()
    for b in blocks:
        bs_h, bs_m = map(int, b.start_time.split(":"))
        be_h, be_m = map(int, b.end_time.split(":"))
        events.append({
            "id": f"block-{b.id}",
            "title": f"🚫 {b.reason or 'Bloqueado'}",
            "start": tz.localize(datetime(b.date.year, b.date.month, b.date.day, bs_h, bs_m)).isoformat(),
            "end": tz.localize(datetime(b.date.year, b.date.month, b.date.day, be_h, be_m)).isoformat(),
            "display": "block",
            "backgroundColor": "#dc354533",
            "borderColor": "#dc3545",
            "textColor": "#dc3545",
            "extendedProps": {"is_block": True, "block_id": b.id},
        })

    # Add break times as background events for each day in range
    schedules = db.query(BusinessHours).filter(
        BusinessHours.is_active == True,
        BusinessHours.break_start != None,
        BusinessHours.break_end != None,
    ).all()

    current = range_start.date()
    while current < range_end.date():
        for sched in schedules:
            valid_from = sched.valid_from or dt_date.min
            valid_to = sched.valid_to or dt_date.max
            if not (valid_from <= current <= valid_to):
                continue
            working_days = [int(d.strip()) for d in sched.working_days.split(",") if d.strip()]
            if current.weekday() not in working_days:
                continue
            bs_h, bs_m = map(int, sched.break_start.split(":"))
            be_h, be_m = map(int, sched.break_end.split(":"))
            events.append({
                "id": f"break-{sched.id}-{current.isoformat()}",
                "title": "🍽 Descanso",
                "start": tz.localize(datetime(current.year, current.month, current.day, bs_h, bs_m)).isoformat(),
                "end": tz.localize(datetime(current.year, current.month, current.day, be_h, be_m)).isoformat(),
                "display": "background",
                "backgroundColor": "#e9ecef",
                "extendedProps": {"is_break": True},
            })
            break  # highest-priority schedule wins per day
        current += timedelta(days=1)

    return events


# ── Services ──────────────────────────────────────────────────────────────────

class ServiceIn(BaseModel):
    name: str
    description: str = ""
    duration_minutes: int = 60
    price: float = 0.0
    is_active: bool = True


@router.get("/admin/api/services")
def list_services(db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    return [
        {"id": s.id, "name": s.name, "description": s.description or "",
         "duration_minutes": s.duration_minutes, "price": s.price, "is_active": s.is_active}
        for s in db.query(Service).order_by(Service.name).all()
    ]


@router.post("/admin/api/services", status_code=201)
def create_service(body: ServiceIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer":
        raise HTTPException(403, "Sin permisos")
    s = Service(**body.dict())
    db.add(s); db.commit(); db.refresh(s)
    return {"id": s.id}


@router.put("/admin/api/services/{sid}")
def update_service(sid: int, body: ServiceIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer":
        raise HTTPException(403, "Sin permisos")
    s = db.get(Service, sid)
    if not s: raise HTTPException(404)
    for k, v in body.dict().items(): setattr(s, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/admin/api/services/{sid}")
def delete_service(sid: int, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer":
        raise HTTPException(403, "Sin permisos")
    s = db.get(Service, sid)
    if not s: raise HTTPException(404)
    s.is_active = False; db.commit()
    return {"ok": True}


# ── Business Hours ────────────────────────────────────────────────────────────

class HoursIn(BaseModel):
    name: str
    working_days: str
    open_time: str
    close_time: str
    break_start: Optional[str] = None
    break_end: Optional[str] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None
    is_active: bool = True
    priority: int = 0


@router.get("/admin/api/hours")
def list_hours(db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    return [
        {"id": h.id, "name": h.name, "working_days": h.working_days,
         "break_start": h.break_start, "break_end": h.break_end,
         "open_time": h.open_time, "close_time": h.close_time,
         "valid_from": h.valid_from.isoformat() if h.valid_from else None,
         "valid_to": h.valid_to.isoformat() if h.valid_to else None,
         "is_active": h.is_active, "priority": h.priority}
        for h in db.query(BusinessHours).order_by(BusinessHours.priority.desc(), BusinessHours.name).all()
    ]


@router.post("/admin/api/hours", status_code=201)
def create_hours(body: HoursIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    h = BusinessHours(**body.dict()); db.add(h); db.commit(); db.refresh(h)
    return {"id": h.id}


@router.put("/admin/api/hours/{hid}")
def update_hours(hid: int, body: HoursIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    h = db.get(BusinessHours, hid)
    if not h: raise HTTPException(404)
    for k, v in body.dict().items(): setattr(h, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/admin/api/hours/{hid}")
def delete_hours(hid: int, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    h = db.get(BusinessHours, hid)
    if not h: raise HTTPException(404)
    db.delete(h); db.commit()
    return {"ok": True}


# ── Appointments ──────────────────────────────────────────────────────────────

class AppointmentIn(BaseModel):
    client_phone: str
    client_name: Optional[str] = None
    service_id: int
    scheduled_at: str
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    status: str
    notes: Optional[str] = None


@router.get("/admin/api/appointments")
def list_appointments(
    date_from: Optional[str] = Query(None), date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None), q: Optional[str] = Query(None),
    db: Session = Depends(get_db), info: dict = Depends(require_auth),
):
    query = db.query(Appointment)
    if date_from: query = query.filter(Appointment.scheduled_at >= datetime.fromisoformat(date_from))
    if date_to: query = query.filter(Appointment.scheduled_at < datetime.fromisoformat(date_to) + timedelta(days=1))
    if status: query = query.filter(Appointment.status == status)
    appts = query.order_by(Appointment.scheduled_at.desc()).limit(300).all()
    tz = settings.timezone

    if q:
        q_lower = q.lower()
        appts = [a for a in appts if q_lower in (a.client.name or "").lower() or q_lower in a.client.phone]

    return [
        {
            "id": a.id,
            "client_name": a.client.name or "Sin nombre", "client_phone": a.client.phone,
            "service_name": a.service.name, "service_id": a.service_id,
            "duration": a.service.duration_minutes, "price": a.service.price,
            "scheduled_at": (tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at).isoformat(),
            "status": a.status, "notes": a.notes or "",
            "reminder_sent": a.reminder_sent == "true",
        }
        for a in appts
    ]


@router.post("/admin/api/appointments", status_code=201)
def create_appointment(body: AppointmentIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    from src.scheduling.appointment_service import get_or_create_client
    client = get_or_create_client(db, body.client_phone)
    if body.client_name and not client.name:
        client.name = body.client_name.strip().title(); db.commit()
    service = db.get(Service, body.service_id)
    if not service: raise HTTPException(404, "Servicio no encontrado")
    appt = Appointment(
        client_id=client.id, service_id=service.id,
        scheduled_at=datetime.fromisoformat(body.scheduled_at).replace(tzinfo=None),
        status=AppointmentStatus.CONFIRMED, notes=body.notes,
    )
    db.add(appt); db.commit(); db.refresh(appt)
    return {"id": appt.id}


@router.put("/admin/api/appointments/{aid}")
def update_appointment(aid: int, body: AppointmentUpdate, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    a = db.get(Appointment, aid)
    if not a: raise HTTPException(404)
    try: a.status = AppointmentStatus(body.status)
    except ValueError: raise HTTPException(400, "Estado inválido")
    if body.notes is not None: a.notes = body.notes
    db.commit()
    return {"ok": True}


# ── Clients ───────────────────────────────────────────────────────────────────

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None


@router.get("/admin/api/clients")
def list_clients(q: Optional[str] = Query(None), db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    clients = db.query(Client).order_by(Client.name).all()
    if q:
        q_lower = q.lower()
        clients = [c for c in clients if q_lower in (c.name or "").lower() or q_lower in c.phone]
    return [
        {
            "id": c.id, "name": c.name or "Sin nombre", "phone": c.phone,
            "email": c.email or "", "notes": c.notes or "",
            "is_blocked": c.is_blocked,
            "created_at": c.created_at.date().isoformat() if c.created_at else None,
            "total_appointments": len(c.appointments),
            "confirmed": sum(1 for a in c.appointments if a.status == AppointmentStatus.CONFIRMED),
        }
        for c in clients
    ]


@router.put("/admin/api/clients/{cid}")
def update_client(cid: int, body: ClientUpdate, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    c = db.get(Client, cid)
    if not c: raise HTTPException(404)
    if body.name is not None: c.name = body.name.strip().title() if body.name.strip() else None
    if body.email is not None: c.email = body.email.strip() or None
    if body.notes is not None: c.notes = body.notes.strip() or None
    db.commit()
    return {"ok": True}


@router.post("/admin/api/clients/{cid}/block")
def toggle_block(cid: int, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    c = db.get(Client, cid)
    if not c: raise HTTPException(404)
    c.is_blocked = not c.is_blocked
    db.commit()
    return {"is_blocked": c.is_blocked}


@router.delete("/admin/api/clients/{cid}")
def delete_client(cid: int, db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    from src.models.conversation import ConversationState
    c = db.get(Client, cid)
    if not c: raise HTTPException(404)
    for a in c.appointments:
        db.delete(a)
    conv = db.query(ConversationState).filter(ConversationState.client_id == cid).first()
    if conv:
        db.delete(conv)
    db.delete(c)
    db.commit()
    return {"ok": True}


# ── Messages ─────────────────────────────────────────────────────────────────

from src.bot import messages as bot_messages

_MSG_LABELS = {
    "blocked":                   ("Cliente vetado", "Mensaje que recibe un cliente vetado al escribir al bot."),
    "ask_name":                  ("Pedir nombre", "Se envía cuando un cliente nuevo escribe por primera vez."),
    "welcome_menu":              ("Menú principal", "Opciones del menú de inicio. Mantén los números 1️⃣-4️⃣."),
    "appointment_confirmed_note":("Nota en cita confirmada", "Texto extra que aparece al confirmar una cita (instrucciones, aviso recordatorio...)."),
    "appointment_cancelled":     ("Cita cancelada", "Usa {servicio} para insertar el nombre del servicio."),
    "no_slots":                  ("Sin horarios disponibles", "Mensaje cuando no hay hueco en la fecha elegida."),
    "invalid_option":            ("Opción inválida", "Respuesta cuando el cliente escribe algo que el bot no entiende."),
    "reminder":                  ("Recordatorio 24h", "Usa {servicio}, {hora} y {negocio} como variables."),
}


@router.get("/admin/api/messages")
def get_messages(info: dict = Depends(require_auth)):
    current = bot_messages.load()
    return [
        {
            "key": k,
            "label": _MSG_LABELS.get(k, (k, ""))[0],
            "hint": _MSG_LABELS.get(k, (k, ""))[1],
            "value": current.get(k, ""),
        }
        for k in bot_messages.all_keys()
    ]


class MessagesIn(BaseModel):
    messages: dict


@router.put("/admin/api/messages")
def set_messages(body: MessagesIn, info: dict = Depends(require_auth)):
    if info["r"] == "viewer":
        raise HTTPException(403, "Sin permisos")
    bot_messages.save(body.messages)
    return {"ok": True}


# ── Role Visibility ───────────────────────────────────────────────────────────

_VISIBILITY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "role_visibility.json")
_ALL_SECTIONS = ["agenda", "dashboard", "appointments", "clients", "services", "hours", "integrations"]
_DEFAULT_VISIBILITY = {"admin": list(_ALL_SECTIONS), "viewer": list(_ALL_SECTIONS)}


def _load_visibility() -> dict:
    try:
        with open(_VISIBILITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return _DEFAULT_VISIBILITY.copy()


def _save_visibility(config: dict):
    os.makedirs(os.path.dirname(_VISIBILITY_FILE), exist_ok=True)
    with open(_VISIBILITY_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


@router.get("/admin/api/visibility")
def get_visibility(info: dict = Depends(require_auth)):
    return _load_visibility()


class VisibilityIn(BaseModel):
    admin: list
    viewer: list


@router.put("/admin/api/visibility")
def set_visibility(body: VisibilityIn, info: dict = Depends(require_superadmin)):
    valid = set(_ALL_SECTIONS)
    config = {
        "admin":  [s for s in body.admin  if s in valid],
        "viewer": [s for s in body.viewer if s in valid],
    }
    _save_visibility(config)
    return {"ok": True}


# ── Test reminder ─────────────────────────────────────────────────────────────

@router.post("/admin/api/test-reminder")
def test_reminder(db: Session = Depends(get_db), info: dict = Depends(require_superadmin)):
    import httpx
    from src.bot.templates import reminder_message

    text = reminder_message(service_name="Corte de cabello", time_str="10:00")
    phone = settings.business_phone
    try:
        r = httpx.post(f"{settings.bridge_url}/send", json={"to": phone, "message": text}, timeout=8)
        if r.is_success:
            return {"ok": True, "sent_to": phone}
        return {"ok": False, "error": r.text}
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Time Blocks ───────────────────────────────────────────────────────────────

from src.models.time_block import TimeBlock

class TimeBlockIn(BaseModel):
    date: date
    start_time: str
    end_time: str
    reason: Optional[str] = None

@router.get("/admin/api/blocks")
def list_blocks(db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    blocks = db.query(TimeBlock).order_by(TimeBlock.date, TimeBlock.start_time).all()
    return [{"id": b.id, "date": b.date.isoformat(), "start_time": b.start_time,
             "end_time": b.end_time, "reason": b.reason} for b in blocks]

@router.post("/admin/api/blocks", status_code=201)
def create_block(body: TimeBlockIn, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    b = TimeBlock(**body.dict())
    db.add(b); db.commit(); db.refresh(b)
    return {"id": b.id}

@router.delete("/admin/api/blocks/{bid}")
def delete_block(bid: int, db: Session = Depends(get_db), info: dict = Depends(require_auth)):
    if info["r"] == "viewer": raise HTTPException(403, "Sin permisos")
    b = db.get(TimeBlock, bid)
    if not b: raise HTTPException(404)
    db.delete(b); db.commit()
    return {"ok": True}


# ── iCal Feed ─────────────────────────────────────────────────────────────────

@router.get("/admin/calendar.ics")
def calendar_ics(key: str = Query(...), db: Session = Depends(get_db)):
    if key != settings.calendar_key:
        raise HTTPException(403, "Clave incorrecta")
    tz = settings.timezone
    appts = db.query(Appointment).filter(
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
    ).all()

    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0",
        f"PRODID:-//{settings.business_name}//Beauty Scheduler//ES",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        f"X-WR-CALNAME:{settings.business_name} - Citas",
        f"X-WR-TIMEZONE:{settings.business_timezone}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
    ]
    for a in appts:
        dt = tz.localize(a.scheduled_at) if a.scheduled_at.tzinfo is None else a.scheduled_at
        dt_end = dt + timedelta(minutes=a.service.duration_minutes)
        lines += [
            "BEGIN:VEVENT",
            f"DTSTART;TZID={settings.business_timezone}:{dt.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID={settings.business_timezone}:{dt_end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{a.service.name} - {a.client.name or a.client.phone}",
            f"DESCRIPTION:Cliente: {a.client.name or 'Sin nombre'}\\nTel: {a.client.phone}\\nServicio: {a.service.name} ({a.service.duration_minutes} min)",
            f"UID:appt-{a.id}@beauty-scheduler",
            f"STATUS:{'CONFIRMED' if a.status == AppointmentStatus.CONFIRMED else 'TENTATIVE'}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return Response(
        content="\r\n".join(lines),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="citas.ics"'},
    )
