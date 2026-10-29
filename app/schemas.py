from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class AIIntent(str, Enum):
    ASK_QUESTION = "ask_question"
    ANSWER_FAQ = "answer_faq"
    PROVIDE_TIMES = "provide_times"
    SELECT_TIME = "select_time"
    CONFIRM_BOOKING = "confirm_booking"
    REQUEST_HUMAN = "request_human"
    NOT_INTERESTED = "not_interested"
    UNSUPPORTED = "unsupported"
    UNCLEAR = "unclear"
    URGENT = "urgent"


class AIResponse(BaseModel):
    intent: AIIntent
    message: str = Field(min_length=1, max_length=1200)
    extracted_fields: dict[str, str | None] = Field(default_factory=dict)
    confidence: float = Field(ge=0, le=1)
    needs_handoff: bool = False
    handoff_reason: str | None = None


class FormWebhook(BaseModel):
    model_config = {"extra": "allow"}

    id: str | None = None
    contactId: str | None = None
    locationId: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    message: str | None = None
    customFields: Any = None
    message_type: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_ghl_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}

        contact_id = (
            data.get("contactId")
            or data.get("contact_id")
            or contact.get("id")
            or contact.get("contact_id")
            or data.get("id")
        )

        first_name = data.get("firstName") or data.get("first_name") or contact.get("first_name")
        last_name = data.get("lastName") or data.get("last_name") or contact.get("last_name")
        name = data.get("name") or data.get("full_name") or contact.get("name")
        if not name and (first_name or last_name):
            name = " ".join(p for p in (first_name, last_name) if p)

        phone = data.get("phone") or contact.get("phone")
        email = data.get("email") or contact.get("email")
        location_id = data.get("locationId") or data.get("location_id") or data.get("location")

        raw_type = data.get("type") or data.get("messageType") or data.get("channel")

        result = dict(data)
        if contact_id is not None:
            result["contactId"] = str(contact_id)
        if first_name is not None:
            result["firstName"] = str(first_name)
        if last_name is not None:
            result["lastName"] = str(last_name)
        if name is not None:
            result["name"] = str(name)
        if phone is not None:
            result["phone"] = str(phone)
        if email is not None:
            result["email"] = str(email)
        if location_id is not None:
            result["locationId"] = str(location_id)
        if raw_type:
            type_str = str(raw_type).lower()
            if "live" in type_str or "chat" in type_str:
                result["message_type"] = "Live_Chat"
            elif "sms" in type_str:
                result["message_type"] = "SMS"
            else:
                result["message_type"] = str(raw_type)
        return result


class InboundMessage(BaseModel):
    model_config = {"extra": "allow"}

    id: str | None = None
    contactId: str | None = None
    locationId: str | None = None
    message: str | None = None
    body: str | None = None
    text: str | None = None
    message_type: str | None = None

    @model_validator(mode="before")
    @classmethod
    def normalize_ghl_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        contact = data.get("contact") if isinstance(data.get("contact"), dict) else {}
        msg_obj = data.get("message") if isinstance(data.get("message"), dict) else {}

        contact_id = (
            data.get("contactId")
            or data.get("contact_id")
            or contact.get("id")
            or contact.get("contact_id")
        )

        body = (
            data.get("body")
            or data.get("text")
            or (data.get("message") if isinstance(data.get("message"), str) else None)
            or msg_obj.get("body")
            or msg_obj.get("text")
        )

        raw_type = (
            data.get("type")
            or data.get("messageType")
            or data.get("channel")
            or msg_obj.get("type")
            or msg_obj.get("messageType")
        )

        result = dict(data)
        if contact_id is not None:
            result["contactId"] = str(contact_id)
        if body is not None:
            result["body"] = str(body)
            result["message"] = str(body)
        if raw_type:
            type_str = str(raw_type).lower()
            if "live" in type_str or "chat" in type_str:
                result["message_type"] = "Live_Chat"
            elif "sms" in type_str:
                result["message_type"] = "SMS"
            else:
                result["message_type"] = str(raw_type)
        return result

