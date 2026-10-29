# AI Lead Responder (GHL Sandbox)

An automated AI lead qualification and scheduling service for local service businesses.

- **Fast First Response:** Answers new leads in seconds with a fast initial response.
- **AI Qualification:** Uses a local Ollama AI model (`qwen2.5:7b`) to extract details and ask questions.
- **Deterministic Python Rules:** Your business hours, service areas, slot lengths, and calendar rules live strictly in Python—the AI model cannot violate them or invent bookings.
- **GoHighLevel (GHL) Sync:** Queries free calendar slots, books appointments, and halts automation when a human is requested.
- **Zero Real Data / No Hardcoded Secrets:** Designed strictly for a GHL sandbox sub-account using fabricated data.

---

## 1. Quick Start (No Python Required)

You only need **Docker Desktop** installed on your computer.

### Step 1: Start Docker Stack
Open your terminal (PowerShell on Windows, or Terminal on macOS/Linux) in this project folder:

```powershell
# Copy the example environment file
Copy-Item .env.example .env

# Start PostgreSQL, Ollama, and the Lead Responder API
docker compose up -d --build
```

### Step 2: Download the Local AI Model
Run this once to download the local model into your Ollama container:

```powershell
docker compose exec ollama ollama pull qwen2.5:7b
```
*(This model download takes a few minutes depending on your internet connection).*

### Step 3: Check System Health
Verify all services are connected:

```powershell
curl http://localhost:8000/health
```
You should see:
```json
{"status":"ok","database":"ok","ollama":"ok","model":"qwen2.5:7b"}
```

---

## 2. Running the 30 Scripted Acceptance Tests

To verify that the system handles all 30 conversation scenarios (including angry leads, prompt injection, invalid dates, out-of-area leads, and human handoff):

```powershell
docker compose exec api python scripts/run_conversation_tests.py
```
This runs the test suite and outputs the pass/fail results for each scenario.

---

## 3. Connecting to your GoHighLevel (GHL) Sandbox

To link this responder to your GoHighLevel test sub-account:

1. **Open `.env` in any text editor.**
2. **Fill in your Sandbox credentials:**
   - `GHL_LOCATION_ID`: Found in your GHL sub-account under *Settings > Business Profile*.
   - `GHL_API_KEY`: An API Key or Private Integration Token generated under *Settings > Integrations / Developers* with permissions for `contacts`, `conversations/messages`, and `calendars`.
   - `GHL_CALENDAR_ID`: The ID of your test booking calendar under *Calendars*.
3. **Configure Your Business Policy (Optional):**
   - `BUSINESS_TIMEZONE`: e.g. `Australia/Brisbane` or `America/New_York`
   - `BUSINESS_OPEN_TIME` & `BUSINESS_CLOSE_TIME`: e.g. `09:00` and `17:00`
   - `SERVICE_NAME`: e.g. `Emergency Plumbing`
   - `SERVICE_AREA`: e.g. `Brisbane`
4. **Connect Webhooks:**
   - Use a secure tunnel (such as `cloudflared` or `ngrok http 8000`) so GHL can reach your machine.
   - In GHL Automations/Workflows, send form submissions to:
     `https://<your-tunnel-url>/webhooks/ghl/form`
   - Send incoming customer SMS/messages to:
     `https://<your-tunnel-url>/webhooks/ghl/message`

---

## 4. How the Lead Conversation Works

```text
1. Form Submitted  --> Instant friendly reply: "Thanks for reaching out! What service are you looking for?"
2. Lead Replies    --> Local AI extracts service, location, and timeline into PostgreSQL.
3. Missing Info    --> AI asks clarifying questions for missing details.
4. Lead Qualified  --> Python fetches live free slots from GHL calendar and offers up to 3 choices.
5. Time Selected   --> Python validates hours, notice, and slot alignment; reserves slot; books GHL calendar.
6. Human Requested --> AI stops immediately. GHL contact tagged with 'ai-human-handoff' and note added.
```

---

## 5. Stopping and Resetting

To stop the containers:
```powershell
docker compose down
```

To completely erase the local database and downloaded AI models to start fresh:
```powershell
docker compose down -v
```

---

## 6. Files & Documentation

- `app/policies/booking_rules.py`: Business hours, timezone, and slot validation rules.
- `app/services/booking.py`: Two-phase booking logic preventing double bookings.
- `app/services/conversation.py`: Core conversation state machine and human handoff routing.
- `scenarios/conversations.json`: Summary list of the 30 acceptance scenarios.
- `scenarios/conversations_detailed.json`: Full dialogue transcripts for all 30 test cases.
- `scripts/run_conversation_tests.py`: Test runner that executes and validates the 30 test cases.
