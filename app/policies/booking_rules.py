from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings


def validate_slot(value: str, now: datetime | None = None) -> datetime:
    settings = get_settings()
    zone = ZoneInfo(settings.business_timezone)
    try:
        proposed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Please provide a valid date and time with a timezone.") from exc
    if proposed.tzinfo is None:
        raise ValueError("A timezone is required for booking.")
    local = proposed.astimezone(zone)
    current = (now or datetime.now(timezone.utc)).astimezone(zone)
    if local <= current + timedelta(minutes=settings.minimum_notice_minutes):
        raise ValueError("That time does not meet the minimum booking notice.")
    if local.date() > current.date() + timedelta(days=settings.max_booking_days):
        raise ValueError("That time is beyond the booking window.")
    if local.strftime("%a").upper()[:3] not in settings.configured_business_days:
        raise ValueError("That day is outside business hours.")
    opening = time.fromisoformat(settings.business_open_time)
    closing = time.fromisoformat(settings.business_close_time)
    local_clock = local.time().replace(tzinfo=None)
    slot_end = (datetime.combine(local.date(), local_clock) + timedelta(minutes=settings.slot_length_minutes)).time()
    if local_clock < opening or slot_end > closing:
        raise ValueError("That time is outside business hours.")
    if ((local_clock.hour * 60 + local_clock.minute) - (opening.hour * 60 + opening.minute)) % settings.slot_length_minutes or local.second or local.microsecond:
        raise ValueError("That time does not match an available appointment slot.")
    return local
