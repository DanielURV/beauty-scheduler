from datetime import datetime, timedelta, date
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.config import settings
from src.models.appointment import Appointment, AppointmentStatus
from src.models.service import Service


SLOT_INTERVAL_MINUTES = 30


def _get_hours_for_date(db: Session, target_date: date) -> Tuple:
    """Returns (open_time, close_time, working_days_list, break_start, break_end) for a given date."""
    from src.models.business_hours import BusinessHours

    schedule = (
        db.query(BusinessHours)
        .filter(
            BusinessHours.is_active == True,
            or_(BusinessHours.valid_from == None, BusinessHours.valid_from <= target_date),
            or_(BusinessHours.valid_to == None, BusinessHours.valid_to >= target_date),
        )
        .order_by(BusinessHours.priority.desc())
        .first()
    )

    if schedule:
        days = [int(d.strip()) for d in schedule.working_days.split(",") if d.strip()]
        return schedule.open_time, schedule.close_time, days, schedule.break_start, schedule.break_end

    return settings.business_open_time, settings.business_close_time, settings.working_days_list, None, None


def get_available_dates(db: Optional[Session] = None, days_ahead: int = 14) -> List[date]:
    tz = settings.timezone
    today = datetime.now(tz).date()
    available = []

    for i in range(1, days_ahead + 1):
        candidate = today + timedelta(days=i)
        if db is not None:
            _, _, working_days, _, _ = _get_hours_for_date(db, candidate)
        else:
            working_days = settings.working_days_list
        if candidate.weekday() in working_days:
            available.append(candidate)

    return available[:10]


def get_available_slots(db: Session, service: Service, target_date: date) -> List[datetime]:
    tz = settings.timezone
    open_time, close_time, _, break_start, break_end = _get_hours_for_date(db, target_date)

    open_h, open_m = map(int, open_time.split(":"))
    close_h, close_m = map(int, close_time.split(":"))

    day_start = tz.localize(datetime(target_date.year, target_date.month, target_date.day, open_h, open_m))
    day_end = tz.localize(datetime(target_date.year, target_date.month, target_date.day, close_h, close_m))

    existing = db.query(Appointment).filter(
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
        Appointment.scheduled_at >= day_start.replace(tzinfo=None),
        Appointment.scheduled_at < (day_end + timedelta(hours=1)).replace(tzinfo=None),
    ).all()

    booked_ranges = []
    for appt in existing:
        start = tz.localize(appt.scheduled_at) if appt.scheduled_at.tzinfo is None else appt.scheduled_at
        end = start + timedelta(minutes=appt.service.duration_minutes)
        booked_ranges.append((start, end))

    # Add manual time blocks
    from src.models.time_block import TimeBlock
    blocks = db.query(TimeBlock).filter(TimeBlock.date == target_date).all()
    for b in blocks:
        bh, bm = map(int, b.start_time.split(":"))
        eh, em = map(int, b.end_time.split(":"))
        booked_ranges.append((
            tz.localize(datetime(target_date.year, target_date.month, target_date.day, bh, bm)),
            tz.localize(datetime(target_date.year, target_date.month, target_date.day, eh, em)),
        ))

    # Add break time as a blocked range
    if break_start and break_end:
        bh, bm = map(int, break_start.split(":"))
        eh, em = map(int, break_end.split(":"))
        booked_ranges.append((
            tz.localize(datetime(target_date.year, target_date.month, target_date.day, bh, bm)),
            tz.localize(datetime(target_date.year, target_date.month, target_date.day, eh, em)),
        ))

    slots = []
    current = day_start
    while current + timedelta(minutes=service.duration_minutes) <= day_end:
        slot_end = current + timedelta(minutes=service.duration_minutes)
        is_free = all(
            slot_end <= booked_start or current >= booked_end
            for booked_start, booked_end in booked_ranges
        )
        if is_free:
            slots.append(current)
        current += timedelta(minutes=SLOT_INTERVAL_MINUTES)

    return slots
