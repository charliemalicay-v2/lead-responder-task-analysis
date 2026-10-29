# Pre-Launch Setup Guide: AI Lead Responder (GHL Sandbox)

This step-by-step guide walks you through configuring your **GoHighLevel (GHL) Sandbox Sub-Account**, setting up your local environment file (`.env`), exposing a webhook tunnel, and verifying everything before starting the backend.

---

## Prerequisites Checklist

Before you begin, ensure you have:
- [x] **Docker Desktop** installed and running on your machine.
- [x] Access to your **GHL Sandbox Sub-Account**.
- [x] Your **GHL Private Integration Token** (API Key).
- [x] A free webhook tunneling utility (e.g., **ngrok** or **Cloudflare Tunnel**).

---

## Phase 1: Retrieve GHL Sandbox Details

### 1. Find Your Location ID
1. Log in to your GoHighLevel Sandbox Sub-Account.
2. In the left-hand navigation, click **Settings** (bottom left).
3. Click **Business Profile**.
4. In the **General Info** section, locate the **Location ID** (a ~20 character alphanumeric string).
5. Copy this value for `GHL_LOCATION_ID`.

---

### 2. Verify Your Private Integration Token
You already have your Private Integration Token. Ensure that it was created with at least the following permissions/scopes in your GHL sub-account (**Settings > Developers / Private Integrations**):

- `contacts.readonly` & `contacts.write` (to inspect contacts, apply tags, and add notes)
- `conversations/message.write` (to send SMS replies)
- `conversations.readonly`
- `calendars.readonly` (to look up free appointment slots)
- `calendars/events.write` (to book confirmed appointments)

Copy the token string for `GHL_API_KEY`.

---

### 3. Create or Locate a Test Calendar
The backend needs a specific calendar to check availability and create appointments.

1. In GHL, go to **Settings > Calendars**.
2. If you don't have a calendar, click **Create Calendar** $\rightarrow$ choose **Simple Calendar** or **Round Robin**.
3. Set:
   - **Slot Duration:** `30 minutes`
   - **Slot Interval:** `30 minutes`
   - **Business Hours:** e.g., Monday – Friday, 9:00 AM – 5:00 PM.
   - **Timezone:** Note the exact timezone (e.g., `Australia/Brisbane` or `America/New_York`).
4. Click the three dots `...` next to your calendar $\rightarrow$ click **Edit** or inspect the URL / calendar list to copy the **Calendar ID**.
5. Save this value for `GHL_CALENDAR_ID`.

---

### 4. Create a Simple Test Form
1. In GHL, navigate to **Sites > Forms > Builder**.
2. Click **Add Form** (or use an existing test form).
3. Ensure the form contains at least:
   - **First Name**
   - **Last Name**
   - **Phone**
   - **Email**
4. Click **Save & Integrate**.

---

## Phase 2: Configure Your Local `.env` File

1. In the root directory of this project, make a copy of `.env.example`:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` in any text editor (VS Code, Notepad, etc.) and update the following values:

```ini
APP_ENV=development
DATABASE_URL=postgresql+psycopg://lead_responder:local-development-password@db:5432/lead_responder
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT_SECONDS=30

# --- GHL Credentials (From Phase 1) ---
GHL_API_BASE_URL=https://services.leadconnectorhq.com
GHL_API_KEY=pit-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
GHL_LOCATION_ID=xxxxxxxxxxxxxxxxxxxx
GHL_CALENDAR_ID=xxxxxxxxxxxxxxxxxxxx
GHL_API_VERSION=2021-07-28

# Leave empty in development to bypass signature validation
GHL_WEBHOOK_SECRET=

# --- Business Rules & Availability ---
# IMPORTANT: Must match the timezone configured on your GHL Calendar
BUSINESS_TIMEZONE=Australia/Brisbane
BUSINESS_DAYS=MON,TUE,WED,THU,FRI
BUSINESS_OPEN_TIME=09:00
BUSINESS_CLOSE_TIME=17:00
SLOT_LENGTH_MINUTES=30
MINIMUM_NOTICE_MINUTES=120
MAX_BOOKING_DAYS=30

# --- Qualification Prompts ---
SERVICE_NAME=Emergency Plumbing
SERVICE_AREA=Brisbane
QUALIFICATION_QUESTIONS=service,location,timeline
```

> [!IMPORTANT]
> Keep `GHL_WEBHOOK_SECRET=` blank during initial local testing. When empty in `APP_ENV=development`, the webhook signature verifier automatically permits incoming test webhooks from GHL workflows without requiring custom HMAC headers.

---

## Phase 3: Set Up a Public Tunnel for Webhooks

Because GHL runs in the cloud, it cannot send webhooks directly to `http://localhost:8000`. You need a public tunnel to forward traffic to port 8000.

### Option A: Using ngrok (Recommended)
If you have `ngrok` installed:
```powershell
ngrok http 8000
```
`ngrok` will provide an HTTPS Forwarding URL, for example:
`https://a1b2-c3d4.ngrok-free.app`

### Option B: Using Cloudflare Tunnel
If you have `cloudflared` installed:
```powershell
cloudflared tunnel --url http://localhost:8000
```
Copy the generated `https://*.trycloudflare.com` URL.

---

## Phase 4: Configure GHL Webhook Automations (Workflows)

Now configure GHL to trigger your local backend when leads submit forms or reply to SMS.

### Workflow 1: New Lead Form Submission
1. In GHL, go to **Automation > Workflows > Create Workflow** $\rightarrow$ choose **Start from Scratch**.
2. **Add Trigger:**
   - Select **Form Submitted**.
   - Filter: `Form is` $\rightarrow$ choose your **Test Lead Intake Form**.
3. **Add Action:**
   - Click the `+` icon $\rightarrow$ choose **Webhook**.
   - **Method:** `POST`
   - **URL:** `https://<YOUR-TUNNEL-URL>/webhooks/ghl/form`
4. Click **Save Action**, toggle the workflow to **Publish**, and click **Save** (top right).

---

### Workflow 2: Inbound Customer Message
1. In GHL, go to **Automation > Workflows > Create Workflow** $\rightarrow$ choose **Start from Scratch**.
2. **Add Trigger:**
   - Select **Customer Replied**.
   - Filter: `Reply Channel is` $\rightarrow$ choose **SMS** (or leave unfiltered for all message types).
3. **Add Action:**
   - Click the `+` icon $\rightarrow$ choose **Webhook**.
   - **Method:** `POST`
   - **URL:** `https://<YOUR-TUNNEL-URL>/webhooks/ghl/message`
4. Click **Save Action**, toggle the workflow to **Publish**, and click **Save**.

---

## Phase 5: Launch the Backend

Now that GHL and `.env` are configured, start the system:

### 1. Build and Start Containers
```powershell
docker compose up -d --build
```
This starts PostgreSQL 16, Ollama, and applies the Alembic database migrations automatically.

### 2. Pull the Ollama AI Model (One-Time Step)
```powershell
docker compose exec ollama ollama pull qwen2.5:7b
```
*(Takes a few minutes depending on connection speed).*

### 3. Verify System Health
```powershell
curl http://localhost:8000/health
```
Expected output:
```json
{
  "status": "ok",
  "database": "ok",
  "ollama": "ok",
  "model": "qwen2.5:7b"
}
```

---

## Phase 6: Run a Quick Sandbox Smoke Test

1. **Submit the Test Form:**
   - Open your test form in GHL or preview mode.
   - Fill in fabricated data:
     - Name: `Jordan Miller`
     - Phone: A sandbox test mobile number
     - Email: `jordan.test@example.com`
   - Click **Submit**.

2. **Watch the Backend Logs:**
   ```powershell
   docker compose logs -f api
   ```
   You should see:
   ```text
   INFO: 202 Accepted POST /webhooks/ghl/form
   INFO: Initial GHL message sent to contact...
   ```

3. **Check GHL Conversations:**
   - In GHL, click **Conversations**.
   - You should see the lead contact created and the immediate outbound response:
     > *"Thanks for reaching out! I can help with a few details. What service are you looking for?"*

4. **Test AI Qualification:**
   - Send an inbound reply as the lead: *"I have a burst pipe in Brisbane."*
   - Watch the backend extract the fields and prompt for dates or offer free calendar slots.

---

## Troubleshooting & Tips

| Problem | Cause | Solution |
|---|---|---|
| **Health endpoint says `"ollama": "error"`** | The Ollama container is still initializing or port 11434 is blocked. | Wait 10 seconds and test again with `curl http://localhost:8000/health`. |
| **GHL says "Webhook delivery failed"** | Your tunnel URL changed or is closed. | Ensure your `ngrok` or `cloudflared` process is still running and the URL matches your GHL workflow. |
| **Outbound messages not sending** | `GHL_API_KEY` is missing permissions. | In GHL, verify the Private Integration has `conversations/message.write` and `contacts.write`. |
| **"That day is outside business hours"** | The requested date is on a weekend or timezone mismatch. | Ensure `BUSINESS_TIMEZONE` in `.env` matches your GHL Calendar's timezone. |
| **Reset Database** | You want to wipe all local test data and start fresh. | Run `docker compose down -v`, then `docker compose up -d --build`. |
