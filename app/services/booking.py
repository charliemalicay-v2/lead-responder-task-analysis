import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Appointment, Conversation, Lead
from app.policies.booking_rules import validate_slot
from app.services.ghl import GHLClient

logger = logging.getLogger(__name__)


def _slot_is_available(slots: dict, iso_time: str) -> bool:
    candidate = validate_slot(iso_time)
    for day in slots.values():
        for slot in day.get("slots", []) if isinstance(day, dict) else []:
            try:
                if validate_slot(slot) == candidate:
                    return True
            except ValueError:
                continue
    return False


async def offer_available_times() -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    start = now.isoformat()
    end = (now + timedelta(days=min(settings.max_booking_days, 7))).isoformat()
    result = await GHLClient().availability(start, end)
    choices: list[datetime] = []
    for day in result.values():
        for slot in day.get("slots", []) if isinstance(day, dict) else []:
            try:
                choices.append(validate_slot(slot))
            except ValueError:
                continue
    choices = sorted(set(choices))[:3]
    if not choices:
        return "I don’t see an available time in the next few days. What dates generally work for you?"
    listed = "; ".join(f"{choice.strftime('%A, %B %d at %I:%M %p')}" for choice in choices)
    return f"Here are a few available times ({settings.business_timezone}): {listed}. Which works best?"


async def book_selected_time(db: Session, conversation: Conversation, lead: Lead, iso_time: str) -> str:
    settings = get_settings()
    try:
        local_start = validate_slot(iso_time)
    except ValueError as exc:
        conversation.status = "AWAITING_TIME"
        return str(exc)
    answers = json.loads(conversation.answers_json or "{}")
    missing = [key for key in settings.required_fields if not answers.get(key)]
    if missing:
        conversation.status = "QUALIFYING"
        return "Before we look at appointments, could you share your " + ", ".join(missing) + "?"
    if not all((settings.ghl_api_key, settings.ghl_location_id, settings.ghl_calendar_id, lead.ghl_contact_id)):
        conversation.status = "GHL_ERROR"
        return "I can’t confirm a booking right now. A team member will follow up shortly."

    start = local_start.isoformat()
    end = (local_start + timedelta(minutes=settings.slot_length_minutes)).isoformat()
    digest = hashlib.sha256(f"{conversation.id}:{start}".encode()).hexdigest()
    idem_key = f"conversation-{conversation.id}-{digest[:32]}"
    existing = db.scalar(select(Appointment).where(Appointment.idempotency_key == idem_key))
    if existing:
        if existing.status == "BOOKED":
            conversation.status = "BOOKED"
            return "You’re booked for the selected time."
        conversation.status = "GHL_ERROR"
        return "I can’t confirm that appointment yet. A team member will follow up shortly."
    # Persist a reservation before the external side effect. Never retry an uncertain create blindly.
    reservation = Appointment(conversation_id=conversation.id, idempotency_key=idem_key,
                              starts_at=local_start, status="PENDING")
    db.add(reservation)
    try:
        db.commit()
    except Exception:
        db.rollback()
        conversation.status = "GHL_ERROR"
        return "I can’t confirm that appointment yet. A team member will follow up shortly."
    ghl = GHLClient()
    try:
        availability = await ghl.availability(start, end)
        if not _slot_is_available(availability, start):
            reservation.status = "CONFLICT"
            conversation.status = "BOOKING_CONFLICT"
            db.commit()
            return "That time is no longer available. What other day or time works for you?"
        # The create endpoint independently validates free slots. Do not set ignoreFreeSlotValidation.
        created = await ghl.create_appointment({
            "calendarId": settings.ghl_calendar_id, "locationId": settings.ghl_location_id,
            "contactId": lead.ghl_contact_id, "startTime": start, "endTime": end,
            "title": f"{settings.service_name} consultation", "appointmentStatus": "confirmed",
            "toNotify": True, "ignoreDateRange": False, "ignoreFreeSlotValidation": False,
        })
        event_id = created.get("id") or created.get("event", {}).get("id")
        if not event_id:
            raise ValueError("GHL did not return an appointment ID")
        reservation.ghl_appointment_id = event_id
        reservation.status = "BOOKED"
        conversation.status = "BOOKED"
        db.commit()
        return f"You’re booked for {local_start.strftime('%A, %B %d at %I:%M %p')} ({settings.business_timezone})."
    except Exception as exc:
        logger.warning("Appointment create/check failed; not retrying: %s", type(exc).__name__)
        db.rollback()
        # The request may have reached GHL before a timeout. Keep a durable pending reservation to
        # prevent a duplicate retry and send this case to a person for reconciliation.
        reservation = db.scalar(select(Appointment).where(Appointment.idempotency_key == idem_key))
        if reservation:
            reservation.status = "UNKNOWN"
        conversation = db.get(Conversation, conversation.id)
        conversation.status = "GHL_ERROR"
        db.commit()
        try:
            await ghl.handoff(lead.ghl_contact_id, "appointment_result_unknown")
        except Exception:
            logger.warning("Handoff after uncertain appointment result failed")
        return "I can’t confirm the appointment status yet. A team member will check and follow up shortly."
