import hashlib
import hmac
import logging

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal, get_db
from app.models import Conversation, Lead, Message, WebhookEvent
from app.schemas import FormWebhook, InboundMessage
from app.services.conversation import FIRST_RESPONSE, process_inbound
from app.services.ghl import GHLClient

logging.basicConfig(level=logging.INFO)
app = FastAPI(title="AI Lead Responder", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    raw = await request.body()
    logging.error("422 Validation error on %s %s: %s | Raw body: %s",
                  request.method, request.url.path, exc.errors(), raw.decode(errors="replace"))
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


def verify_webhook(secret: str, signature: str | None, raw: bytes) -> None:
    if not secret:
        if get_settings().app_env == "production":
            raise HTTPException(503, "Webhook authentication is not configured")
        return
    expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid webhook signature")


@app.get("/health")
async def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "error"
    settings = get_settings()
    ollama = "error"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
            response.raise_for_status()
            ollama = "ok"
    except httpx.HTTPError:
        pass
    return {"status": "ok" if database == "ok" and ollama == "ok" else "degraded", "database": database,
            "ollama": ollama, "model": settings.ollama_model}


async def background_send_first_response(contact_id: str, message_type: str | None = None) -> None:
    try:
        await GHLClient().send_message(contact_id, FIRST_RESPONSE, message_type=message_type)
    except Exception as exc:
        logging.warning("Initial GHL message failed: %s", type(exc).__name__)


async def background_process_inbound(contact_id: str, body: str, external_id: str | None, message_type: str | None = None) -> None:
    with SessionLocal() as db:
        try:
            await process_inbound(db, contact_id, body, external_id, message_type=message_type)
        except Exception as exc:
            logging.warning("Background inbound processing failed: %s", type(exc).__name__)


@app.post("/webhooks/ghl/form", status_code=202)
async def form_webhook(payload: FormWebhook, request: Request, background_tasks: BackgroundTasks,
                       db: Session = Depends(get_db), x_ghl_signature: str | None = Header(default=None)):
    raw = await request.body()
    logging.info("Received form webhook payload: %s", raw.decode(errors="replace"))
    verify_webhook(get_settings().ghl_webhook_secret, x_ghl_signature, raw)
    contact_id = payload.contactId or payload.id
    if not contact_id:
        logging.error("Form webhook rejected: contactId missing from payload: %s", payload.model_dump())
        raise HTTPException(422, "contactId is required")
    key = payload.id or f"form:{contact_id}"
    if db.scalar(select(WebhookEvent).where(WebhookEvent.event_key == key)):
        return {"status": "duplicate"}
    lead = db.scalar(select(Lead).where(Lead.ghl_contact_id == contact_id))
    if lead is None:
        name = payload.name or " ".join(p for p in (payload.firstName, payload.lastName) if p) or None
        lead = Lead(ghl_contact_id=contact_id, name=name, phone=payload.phone, email=payload.email)
        db.add(lead)
        db.flush()
        conversation = Conversation(lead_id=lead.id, status="QUALIFYING")
        db.add(conversation)
        db.flush()
    else:
        conversation = lead.conversation
    db.add(WebhookEvent(event_key=key, event_type="form"))
    db.add(Message(conversation_id=conversation.id, direction="out", body=FIRST_RESPONSE))
    db.commit()
    background_tasks.add_task(background_send_first_response, contact_id, payload.message_type)
    return {"status": "accepted", "conversation_id": conversation.id}


@app.post("/webhooks/ghl/message", status_code=202)
async def inbound_webhook(payload: InboundMessage, request: Request, background_tasks: BackgroundTasks,
                          db: Session = Depends(get_db), x_ghl_signature: str | None = Header(default=None)):
    raw = await request.body()
    logging.info("Received inbound message payload: %s", raw.decode(errors="replace"))
    verify_webhook(get_settings().ghl_webhook_secret, x_ghl_signature, raw)
    if not payload.contactId:
        logging.error("Inbound message rejected: contactId missing from payload: %s", payload.model_dump())
        raise HTTPException(422, "contactId is required")
    body = payload.message or payload.body or payload.text
    if not body:
        raise HTTPException(422, "message body is required")
    lead = db.scalar(select(Lead).where(Lead.ghl_contact_id == payload.contactId))
    if lead is None or lead.conversation is None:
        raise HTTPException(404, "No conversation found for this contact")
    if payload.id and db.scalar(select(Message).where(Message.external_id == payload.id)):
        return {"status": "duplicate"}
    background_tasks.add_task(background_process_inbound, payload.contactId, body, payload.id, payload.message_type)
    return {"status": "accepted"}


@app.get("/debug/conversations/{conversation_id}")
def debug_conversation(conversation_id: int, db: Session = Depends(get_db)):
    if get_settings().app_env == "production":
        raise HTTPException(404)
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return {"id": conversation.id, "status": conversation.status,
            "messages": [{"direction": m.direction, "body": m.body, "created_at": m.created_at}
                        for m in conversation.messages]}


@app.get("/api/latest-lead")
def get_latest_lead(db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).order_by(Lead.id.desc()))
    if not lead:
        return {"contactId": None, "name": None}
    return {
        "contactId": lead.ghl_contact_id,
        "name": lead.name,
        "phone": lead.phone,
        "conversationId": lead.conversation.id if lead.conversation else None,
        "status": lead.conversation.status if lead.conversation else None,
    }


@app.get("/chat", response_class=HTMLResponse)
def get_chat_page():
    import os
    chat_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "chat_widget_test.html")
    if os.path.exists(chat_path):
        with open(chat_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>chat_widget_test.html not found</h1>", status_code=404)
