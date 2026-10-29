import json
import logging

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Conversation, Lead, Message
from app.services.ghl import GHLClient
from app.services.ollama import OllamaClient
from app.services.booking import book_selected_time, offer_available_times

logger = logging.getLogger(__name__)
STOP_STATES = {"HANDOFF_ACTIVE", "NOT_INTERESTED", "CLOSED", "BOOKED"}
FIRST_RESPONSE = "Thanks for reaching out! I can help with a few details. What service are you looking for?"


async def process_inbound(db: Session, contact_id: str, body: str, external_id: str | None = None, message_type: str | None = None) -> str:
    lead = db.scalar(select(Lead).where(Lead.ghl_contact_id == contact_id))
    if lead is None or lead.conversation is None:
        raise LookupError("No conversation found for this contact")
    conversation = lead.conversation
    if conversation.status in STOP_STATES:
        return "Automation is stopped for this conversation."
    if external_id and db.scalar(select(Message).where(Message.external_id == external_id)):
        return "Duplicate message ignored."
    existing_msgs = sorted(
        conversation.messages,
        key=lambda m: m.created_at or datetime.min.replace(tzinfo=timezone.utc),
    )
    transcript = [{"role": "user" if m.direction == "in" else "assistant", "content": m.body} for m in existing_msgs]
    transcript.append({"role": "user", "content": body})
    incoming = Message(conversation_id=conversation.id, direction="in", body=body, external_id=external_id)
    db.add(incoming)
    result = await OllamaClient().respond(transcript, get_settings().required_fields)
    answers = json.loads(conversation.answers_json or "{}")
    answers.update({key: value for key, value in result.extracted_fields.items() if value})
    conversation.answers_json = json.dumps(answers)
    if result.needs_handoff or result.intent.value in {"request_human", "urgent"} or result.confidence < 0.35:
        conversation.status = "HANDOFF_ACTIVE"
        try:
            await GHLClient().handoff(contact_id, result.handoff_reason or result.intent.value)
        except Exception as exc:
            logger.warning("GHL handoff update failed: %s", type(exc).__name__)
            result.message = "I’m connecting you with a team member. We’ll follow up shortly."
    elif result.intent.value == "not_interested":
        conversation.status = "NOT_INTERESTED"
    elif result.intent.value == "unsupported" or result.extracted_fields.get("service_supported") == "false" or result.extracted_fields.get("in_service_area") == "false":
        conversation.status = "CLOSED"
    elif result.intent.value == "select_time":
        selected_time = result.extracted_fields.get("selected_time")
        if not selected_time:
            conversation.status = "AWAITING_TIME"
            result.message = "What date and time would you prefer? Please include your timezone."
        else:
            result.message = await book_selected_time(db, conversation, lead, selected_time)
    elif result.intent.value == "provide_times":
        missing = [key for key in get_settings().required_fields if not answers.get(key)]
        if missing:
            conversation.status = "QUALIFYING"
            result.message = "Before we look at appointments, could you share your " + ", ".join(missing) + "?"
        else:
            try:
                result.message = await offer_available_times()
                conversation.status = "AWAITING_TIME"
            except Exception as exc:
                logger.warning("GHL availability lookup failed: %s", type(exc).__name__)
                conversation.status = "GHL_ERROR"
                result.message = "I can’t check appointment times right now. A team member will follow up shortly."
    elif result.intent.value == "confirm_booking":
        # Only the booking service may confirm, after GHL returns a created appointment ID.
        conversation.status = "HANDOFF_ACTIVE"
        result.message = "I can’t confirm an appointment until the calendar verifies it. A team member will follow up."
        try:
            await GHLClient().handoff(contact_id, "unverified_booking_claim")
        except Exception:
            logger.warning("Could not apply handoff for unverified booking claim")
    else:
        missing = [key for key in get_settings().required_fields if not answers.get(key)]
        conversation.status = "QUALIFYING" if missing else "QUALIFIED"
    db.add(Message(conversation_id=conversation.id, direction="out", body=result.message))
    db.commit()
    try:
        await GHLClient().send_message(contact_id, result.message, message_type=message_type)
    except Exception as exc:
        logger.warning("GHL message send failed: %s", type(exc).__name__)
    return result.message
