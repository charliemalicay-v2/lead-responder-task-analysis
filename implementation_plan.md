# Updated Implementation Plan: AI Lead Responder

## 1. Goal

Build an AI lead responder for a service business with:

1. A GoHighLevel (GHL) form webhook that receives new leads.
2. An immediate automated response.
3. An Ollama-hosted local AI model that asks qualification questions.
4. Deterministic Python code that controls qualification and booking rules.
5. GHL calendar integration for valid appointments.
6. Human handoff when requested or required.
7. A 30-conversation scripted test suite.
8. A Dockerized FastAPI backend that runs in the sandbox environment.

The implementation will use only the GHL sandbox sub-account and fabricated data.

---

## 2. Technology stack

- **Backend:** Python 3.12
- **Web framework:** FastAPI
- **ASGI server:** Uvicorn
- **AI runtime:** Ollama
- **AI model:** A configurable Ollama chat model, initially selected from models such as `qwen2.5:7b` or `llama3.1:8b`
- **Database:** PostgreSQL in Docker
- **ORM:** SQLAlchemy 2.x
- **Migrations:** Alembic
- **HTTP client:** httpx
- **Validation:** Pydantic v2
- **Testing:** pytest, pytest-asyncio, and respx
- **Containerization:** Docker and Docker Compose
- **External integration:** GHL API and webhooks
- **Configuration:** Environment variables through `.env`

The final Ollama model should be selected after testing response quality, speed, structured-output reliability, and sandbox resource usage.

---

## 3. Architecture

```text
                         ┌─────────────────────┐
                         │ GHL Form Submission │
                         └──────────┬──────────┘
                                    │ webhook
                                    v
                    ┌──────────────────────────────┐
                    │ FastAPI Application Container │
                    │                              │
                    │  Webhook API                  │
                    │  Conversation Service         │
                    │  Qualification Policy         │
                    │  Booking Rules Engine         │
                    │  Human Handoff Service        │
                    │  GHL API Client               │
                    └──────────────┬───────────────┘
                                   │
               ┌───────────────────┼───────────────────┐
               v                   v                   v
     ┌────────────────┐  ┌──────────────────┐  ┌───────────────┐
     │ PostgreSQL      │  │ Ollama Container │  │ GHL API       │
     │ conversation DB │  │ local AI model   │  │ calendar/SMS  │
     └────────────────┘  └──────────────────┘  └───────────────┘
```

Ollama may suggest responses and extract information, but it must never directly control GHL or create appointments.

---

## 4. Docker Compose design

### Services

#### `api`

Runs the FastAPI application and is responsible for:

- Receiving GHL webhooks.
- Storing leads and messages.
- Calling Ollama over the Docker network.
- Applying qualification policies.
- Applying booking rules.
- Calling the GHL API.
- Handling human handoff.
- Exposing health and diagnostic endpoints.

#### `ollama`

Runs the local Ollama server and configured model.

Example service configuration:

```yaml
ollama:
  image: ollama/ollama:latest
  volumes:
    - ollama_data:/root/.ollama
  ports:
    - "11434:11434"
```

The API connects to:

```env
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
```

The model should be downloaded during setup, not on every API startup:

```bash
docker compose exec ollama ollama pull qwen2.5:7b
```

#### `db`

Runs PostgreSQL for leads, conversations, messages, qualification answers, appointments, and webhook events.

#### Optional `adminer`

An optional local database viewer may be included for sandbox debugging, but it should not be required for normal use.

### Example `docker-compose.yml`

```yaml
services:
  api:
    build: .
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_started
    environment:
      DATABASE_URL: postgresql+psycopg://lead_responder:local-development-password@db:5432/lead_responder
      OLLAMA_BASE_URL: http://ollama:11434
      OLLAMA_MODEL: qwen2.5:7b
    ports:
      - "8000:8000"
    volumes:
      - .:/app

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: lead_responder
      POSTGRES_USER: lead_responder
      POSTGRES_PASSWORD: local-development-password
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lead_responder -d lead_responder"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - postgres_data:/var/lib/postgresql/data

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  postgres_data:
  ollama_data:
```

### API `Dockerfile` requirements

The API image should:

- Use a slim Python base image.
- Install dependencies from `requirements.txt` or `pyproject.toml`.
- Run database migrations before or during deployment.
- Start Uvicorn with a production-style command.

Example runtime command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## 5. FastAPI application structure

```text
ai-lead-responder/
├── README.md
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── alembic.ini
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── dependencies.py
│   ├── api/
│   │   ├── health.py
│   │   ├── ghl_webhooks.py
│   │   └── inbound_messages.py
│   ├── models/
│   │   ├── lead.py
│   │   ├── conversation.py
│   │   ├── message.py
│   │   ├── appointment.py
│   │   └── webhook_event.py
│   ├── schemas/
│   │   ├── ghl.py
│   │   ├── conversation.py
│   │   ├── ai.py
│   │   └── booking.py
│   ├── services/
│   │   ├── conversation_service.py
│   │   ├── qualification_service.py
│   │   ├── booking_service.py
│   │   ├── handoff_service.py
│   │   ├── ghl_client.py
│   │   └── ollama_client.py
│   ├── policies/
│   │   ├── booking_rules.py
│   │   ├── qualification_rules.py
│   │   ├── handoff_rules.py
│   │   └── message_rules.py
│   ├── prompts/
│   │   └── qualification_prompt.txt
│   └── workers/
│       └── message_tasks.py
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── conversations/
│   └── results/
├── scripts/
│   ├── wait_for_ollama.py
│   ├── pull_model.sh
│   ├── seed_sandbox.py
│   ├── run_conversation_tests.py
│   └── generate_test_report.py
└── docs/
    ├── architecture.md
    ├── booking-rules.md
    ├── operations.md
    └── demo-script.md
```

---

## 6. FastAPI endpoints

### Health endpoint

```text
GET /health
```

Example response:

```json
{
  "status": "ok",
  "database": "ok",
  "ollama": "ok",
  "model": "qwen2.5:7b"
}
```

### GHL form webhook

```text
POST /webhooks/ghl/form
```

Responsibilities:

- Validate the webhook.
- Check idempotency.
- Normalize the lead.
- Store the lead.
- Create a conversation.
- Trigger the immediate response.
- Return quickly to GHL.

### Inbound message webhook

```text
POST /webhooks/ghl/message
```

Responsibilities:

- Identify the lead and conversation.
- Store the incoming message.
- Invoke the conversation service.
- Call Ollama when appropriate.
- Send the next response or trigger booking/handoff.

### Optional diagnostic endpoints

These should be protected or disabled outside sandbox use:

```text
GET /debug/conversations/{conversation_id}
POST /debug/reset-sandbox
GET /debug/test-results
```

---

## 7. Ollama integration

Create an `OllamaClient` using `httpx.AsyncClient`.

The client should:

- Call the Ollama `/api/chat` endpoint.
- Send the configured model name.
- Set request timeouts.
- Support structured JSON output where supported.
- Validate the response with Pydantic.
- Record latency and model errors.
- Avoid exposing prompts or credentials in normal logs.

Example request:

```json
{
  "model": "qwen2.5:7b",
  "stream": false,
  "format": "json",
  "messages": [
    {
      "role": "system",
      "content": "You are a concise lead qualification assistant..."
    },
    {
      "role": "user",
      "content": "Conversation context and latest lead message..."
    }
  ],
  "options": {
    "temperature": 0.2
  }
}
```

The exact `format` behavior should be verified against the selected Ollama model. If strict JSON mode is unreliable, invalid output must be rejected and the system must use a safe fallback instead of executing it.

### AI response schema

```python
class AIIntent(str, Enum):
    ASK_QUESTION = "ask_question"
    ANSWER_FAQ = "answer_faq"
    PROVIDE_TIMES = "provide_times"
    SELECT_TIME = "select_time"
    CONFIRM_BOOKING = "confirm_booking"
    REQUEST_HUMAN = "request_human"
    NOT_INTERESTED = "not_interested"
    UNCLEAR = "unclear"
    URGENT = "urgent"


class AIResponse(BaseModel):
    intent: AIIntent
    message: str
    extracted_fields: dict[str, str | None] = {}
    confidence: float = Field(ge=0, le=1)
    needs_handoff: bool = False
    handoff_reason: str | None = None
```

Model output must always be treated as untrusted input.

---

## 8. AI responsibilities and restrictions

Ollama may:

- Detect the lead’s intent.
- Extract service, location, timeline, and budget.
- Select the next approved question.
- Rephrase approved questions.
- Answer configured FAQs.
- Detect requests for a human.
- Detect unclear, urgent, or sensitive messages.

Ollama may not:

- Call GHL directly.
- Select an unvalidated appointment slot.
- Decide whether a slot is available.
- Override business hours.
- Create, cancel, or modify appointments.
- Invent prices or guarantees.
- Claim that an appointment is booked before the backend confirms it.
- Continue automated qualification after an approved handoff.

All actions must go through deterministic Python services.

---

## 9. Deterministic Python booking engine

Example configuration:

```env
BUSINESS_TIMEZONE=Australia/Brisbane
BUSINESS_DAYS=MON,TUE,WED,THU,FRI
BUSINESS_OPEN_TIME=09:00
BUSINESS_CLOSE_TIME=17:00
SLOT_LENGTH_MINUTES=30
MINIMUM_NOTICE_MINUTES=120
MAX_BOOKING_DAYS=30
```

The booking engine must:

- Parse and normalize time zones.
- Reject dates in the past.
- Reject times outside business hours.
- Enforce slot length.
- Enforce minimum notice.
- Enforce the maximum booking window.
- Query GHL availability.
- Recheck availability immediately before booking.
- Use an idempotency key.
- Avoid duplicate appointment creation.
- Record the GHL appointment ID.

The AI may return:

```json
{
  "intent": "select_time",
  "extracted_fields": {
    "selected_time": "2026-11-03T10:30:00+10:00"
  }
}
```

The booking service must validate that value before making any GHL request.

---

## 10. Conversation state machine

```text
NEW
  |
  v
QUALIFYING
  |
  +--> HANDOFF_ACTIVE
  |
  +--> NOT_INTERESTED
  |
  v
QUALIFIED
  |
  v
OFFERING_TIMES
  |
  v
AWAITING_TIME
  |
  +--> HANDOFF_ACTIVE
  |
  v
BOOKED
  |
  v
CLOSED
```

Additional error states:

```text
AI_ERROR
GHL_ERROR
BOOKING_CONFLICT
```

When a human handoff occurs:

- Set status to `HANDOFF_ACTIVE`.
- Add a GHL tag.
- Add an internal note.
- Stop automatic messages.
- Preserve the transcript.
- Do not invoke Ollama for subsequent replies unless a human explicitly resumes automation.

---

## 11. Implementation phases

### Phase 1: Confirm sandbox and Docker environment

- Confirm the GHL sandbox sub-account.
- Confirm the sandbox calendar and test form.
- Confirm the messaging channel.
- Confirm sandbox credentials.
- Confirm Docker and Docker Compose availability.
- Confirm whether Ollama can run on CPU or whether GPU support is available.
- Select an initial model based on available memory and response speed.

### Phase 2: Create the FastAPI Docker skeleton

Implement:

- FastAPI application.
- `/health` endpoint.
- Dockerfile.
- Docker Compose.
- PostgreSQL connection.
- Alembic migrations.
- Environment configuration.
- Ollama connectivity check.

Acceptance test:

```bash
docker compose up -d
curl http://localhost:8000/health
```

The health endpoint should show the database and Ollama status.

### Phase 3: Implement GHL webhook intake

Implement:

- Form submission webhook.
- Inbound message webhook.
- Payload validation with Pydantic.
- Idempotency.
- Lead and conversation persistence.
- Structured logs.
- Fast webhook responses.

### Phase 4: Implement immediate response

Implement:

- GHL outbound message client.
- First-response template.
- Message delivery tracking.
- Retry handling.
- Conversation state transitions.

Acceptance test: a fake sandbox form submission receives a message within one minute.

### Phase 5: Implement Ollama qualification

Implement:

- `OllamaClient`.
- Prompt templates.
- Structured response schema.
- Model timeout handling.
- Invalid JSON fallback.
- Qualification field extraction.
- Approved question flow.
- Human handoff detection.

Acceptance test: the model can collect required fields but cannot directly book an appointment.

### Phase 6: Implement deterministic booking

Implement:

- Business-hours policy.
- Slot-length policy.
- Time-zone conversion.
- GHL availability lookup.
- Slot filtering.
- Final availability check.
- Appointment creation.
- Duplicate prevention.
- Booking confirmation.

### Phase 7: Implement handoff

Implement:

- Explicit human-request detection.
- Handoff state.
- GHL tag and internal note.
- Transcript summary.
- Automation stop behavior.

### Phase 8: Build the 30-conversation test suite

- Store conversations as JSON fixtures.
- Mock Ollama responses where deterministic tests are required.
- Add a smaller live-Ollama smoke-test subset.
- Mock GHL for unit and integration tests.
- Run the full suite against the Docker Compose stack.
- Generate a Markdown results report.

### Phase 9: Sandbox demo and recording

- Seed fabricated sandbox data.
- Demonstrate form submission.
- Demonstrate qualification.
- Demonstrate booking.
- Demonstrate rejection of an invalid time.
- Demonstrate human handoff.
- Record the screen.
- Include Docker startup and README instructions.

---

## 12. Testing strategy

### Unit tests

Test Python policy code without Ollama or GHL:

- Business-hour validation.
- Time-zone conversion.
- Slot generation.
- Minimum notice.
- Maximum booking window.
- Double-booking prevention.
- Qualification completeness.
- Human handoff rules.
- Idempotency behavior.

### Ollama client tests

Mock the Ollama HTTP API and test:

- Valid JSON output.
- Invalid JSON output.
- Missing required fields.
- Low-confidence output.
- Timeout.
- Connection failure.
- Unexpected intent.
- Prompt-injection attempt.

### GHL client tests

Mock the GHL API and test:

- Form event processing.
- Message sending.
- Availability lookup.
- Appointment creation.
- Duplicate appointment response.
- API timeout.
- API rate-limit response.

### End-to-end Docker tests

```bash
docker compose up -d
pytest
python scripts/run_conversation_tests.py
python scripts/generate_test_report.py
```

---

## 13. The 30 scripted conversations

| ID | Scenario | Expected result |
|---|---|---|
| TC-001 | Normal qualified lead | Qualifies and books |
| TC-002 | All details provided in first message | Extracts details and asks only missing questions |
| TC-003 | One answer at a time | Continues normally |
| TC-004 | Price asked immediately | Gives configured answer |
| TC-005 | Unsupported service | Does not book |
| TC-006 | Outside service area | Does not book |
| TC-007 | Vague location | Clarifies |
| TC-008 | Vague timeline | Clarifies |
| TC-009 | Relative date such as “tomorrow” | Resolves using configured time zone |
| TC-010 | Past date | Rejects |
| TC-011 | Outside business hours | Rejects and offers alternatives |
| TC-012 | Unavailable slot | Offers alternatives |
| TC-013 | Slot taken during booking | Rechecks and avoids double booking |
| TC-014 | Valid slot | Books |
| TC-015 | Time changed before booking | Revalidates |
| TC-016 | Human request | Stops automation |
| TC-017 | Angry lead | Handoff |
| TC-018 | Profanity | Remains safe and professional |
| TC-019 | Empty or unclear reply | Clarifies |
| TC-020 | Multiple unrelated questions | Handles approved FAQ |
| TC-021 | Ignore-rules request | Refuses policy bypass |
| TC-022 | Prompt injection | Does not reveal system prompt |
| TC-023 | Conflicting answers | Requests clarification |
| TC-024 | Service changed mid-conversation | Re-evaluates |
| TC-025 | Emergency or unsafe request | Handoff or safe fallback |
| TC-026 | Not interested | Closes politely |
| TC-027 | Duplicate GHL webhook | No duplicate conversation or message |
| TC-028 | GHL API failure | Retries safely |
| TC-029 | Ollama timeout or unavailable model | Uses fallback; does not book |
| TC-030 | Reply after human handoff | Does not resume AI automatically |

Each test should record:

```json
{
  "id": "TC-029",
  "expected_final_state": "AI_ERROR",
  "expected_handoff": true,
  "expected_appointment_created": false,
  "ollama_failure_mode": "timeout"
}
```

---

## 14. Test success criteria

A test passes only when the expected behavior and safety invariants are satisfied.

Target:

- At least 27 of 30 scenarios correct.
- Zero double bookings.
- Zero bookings outside business hours.
- Zero bookings made while Ollama output is invalid or unavailable.
- Zero missed explicit human handoffs.
- Zero duplicate responses caused by repeated webhooks.
- Zero unsupported claims about price, availability, or completed bookings.

Any failure involving a booking-rule violation, duplicate appointment, or missed human handoff is a release blocker.

---

## 15. README requirements for non-engineers

The README should explain Docker and Ollama without assuming Python knowledge.

### Start the system

```bash
cp .env.example .env
docker compose up -d
docker compose exec ollama ollama pull qwen2.5:7b
```

Then verify:

```bash
curl http://localhost:8000/health
```

### Stop the system

```bash
docker compose down
```

### Reset local test data

```bash
docker compose down -v
docker compose up -d
```

This deletes local Docker database and Ollama volumes, so the README must clearly warn that it removes local test data and the downloaded model.

### Run tests

```bash
docker compose exec api pytest
docker compose exec api python scripts/run_conversation_tests.py
```

### Configure GHL

The README should explain:

1. Where to find the sandbox location ID.
2. Where to place the GHL API key.
3. How to configure the webhook URL.
4. How to configure the calendar ID.
5. How to configure the sandbox test form.
6. How to verify that messages and appointments appear in GHL.

No credentials should be committed to the repository.

---

## 16. Screen recording plan

The recording should demonstrate:

1. `docker compose up` starting FastAPI, PostgreSQL, and Ollama.
2. The health endpoint showing all dependencies are ready.
3. A fake lead submitted through the GHL sandbox form.
4. The immediate response.
5. Ollama-generated qualification questions.
6. A valid appointment being offered and booked.
7. An invalid or unavailable time being rejected by Python booking rules.
8. A human request stopping automation.
9. The resulting GHL tag, note, conversation, and calendar appointment.

All names, phone numbers, addresses, and service information must be fabricated.

---

## 17. Risks and mitigations

### Ollama response quality

**Risk:** The local model may misunderstand short or ambiguous messages.

**Mitigation:**

- Use a constrained prompt.
- Use low temperature.
- Require structured output.
- Validate every response.
- Ask for clarification when confidence is low.
- Keep deterministic rules outside the model.
- Add regression tests for every discovered failure.

### Ollama startup and model loading time

**Risk:** The first request may be slow while the model loads.

**Mitigation:**

- Pull the model during setup.
- Add an Ollama readiness check.
- Warm up the model after container startup.
- Send the first response using a static template before calling the model.
- Configure request timeouts and fallback behavior.

### Resource constraints

**Risk:** A large model may not run reliably in the sandbox.

**Mitigation:**

- Start with a smaller instruct model.
- Measure latency and memory usage.
- Keep the model configurable through `OLLAMA_MODEL`.
- Do not require GPU support for the initial implementation.

### Invalid structured output

**Risk:** The model may return malformed JSON or unauthorized actions.

**Mitigation:**

- Validate with Pydantic.
- Retry once with a repair instruction if appropriate.
- Otherwise use a safe fallback.
- Never execute model output directly.

### External API failures

**Risk:** GHL may be temporarily unavailable.

**Mitigation:**

- Use bounded retries.
- Use idempotency keys.
- Avoid blind retries for appointment creation.
- Log every external operation.
- Provide a human follow-up path.

---

## 18. Definition of done

The implementation is complete when:

- The backend is written in Python using FastAPI.
- The complete backend runs through Docker Compose.
- PostgreSQL and Ollama run as Docker services.
- The selected Ollama model is configurable.
- The API health endpoint reports database and Ollama readiness.
- GHL sandbox webhooks are received and deduplicated.
- New leads receive a response within one minute.
- Qualification uses Ollama, but all business rules remain in Python.
- Booking hours, slot length, time zone, notice period, and duplicate prevention are enforced in Python.
- GHL appointments are created only after deterministic validation.
- Human handoff stops automated AI messages.
- Thirty scripted conversations are included.
- Test results report the exact number handled correctly.
- A non-engineer can start and test the system using the README.
- A screen recording demonstrates the sandbox workflow.
- The repository contains no real client data or committed secrets.
- The final documentation includes limitations and next steps.
