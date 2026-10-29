import logging

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class GHLClient:
    def _headers(self) -> dict[str, str]:
        settings = get_settings()
        if not settings.ghl_api_key:
            raise RuntimeError("GHL_API_KEY is not configured")
        return {"Authorization": f"Bearer {settings.ghl_api_key}", "Version": settings.ghl_api_version,
                "Content-Type": "application/json"}

    async def send_message(self, contact_id: str, body: str, message_type: str | None = None) -> None:
        settings = get_settings()
        type_to_use = message_type or "SMS"
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {"type": type_to_use, "contactId": contact_id, "message": body}
            response = await client.post(
                f"{settings.ghl_api_base_url}/conversations/messages",
                headers=self._headers(),
                json=payload,
            )
            # If a non-SMS type fails, fallback gracefully to SMS
            if response.status_code >= 400 and type_to_use != "SMS":
                logger.info("Message send with type %s failed (%s), falling back to SMS", type_to_use, response.status_code)
                payload["type"] = "SMS"
                response = await client.post(
                    f"{settings.ghl_api_base_url}/conversations/messages",
                    headers=self._headers(),
                    json=payload,
                )
            response.raise_for_status()

    async def handoff(self, contact_id: str, reason: str) -> None:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            resp_tag = await client.post(
                f"{settings.ghl_api_base_url}/contacts/{contact_id}/tags",
                headers=self._headers(),
                json={"tags": ["ai-human-handoff"]},
            )
            resp_tag.raise_for_status()
            resp_note = await client.post(
                f"{settings.ghl_api_base_url}/contacts/{contact_id}/notes",
                headers=self._headers(),
                json={"body": f"AI handoff requested/required: {reason}"},
            )
            resp_note.raise_for_status()

    async def availability(self, start: str, end: str) -> dict:
        settings = get_settings()
        from datetime import datetime

        start_ms = int(datetime.fromisoformat(start).timestamp() * 1000)
        end_ms = int(datetime.fromisoformat(end).timestamp() * 1000)
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                f"{settings.ghl_api_base_url}/calendars/{settings.ghl_calendar_id}/free-slots",
                headers={**self._headers(), "Version": "v3"},
                params={"startDate": start_ms, "endDate": end_ms,
                        "timezone": settings.business_timezone, "duration": settings.slot_length_minutes})
            response.raise_for_status()
            return response.json()

    async def create_appointment(self, payload: dict) -> dict:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(f"{settings.ghl_api_base_url}/calendars/events/appointments",
                                         headers=self._headers(), json=payload)
            response.raise_for_status()
            return response.json()
