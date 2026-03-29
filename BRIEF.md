# Project brief — autonomous manufacturing decision demo

## What this is
A demo showing OpenClaw (running inside NemoClaw) making 
goal-driven manufacturing decisions. Two OpenClaw claws — a 
decision claw and a policy claw — call these simulated REST 
APIs as tools. The claws are configured separately; this 
codebase is only the services they call.

## Three scenarios (always available in SQLite)
- A: Machine M-204 anomaly, HIGH priority order PO-1042, 
     alternate machine M-207 available → expect SHIFT_PRODUCTION
- B: Machine M-204 anomaly, HIGH priority order PO-1042, 
     no alternate machine → expect REDUCE_SPEED  
- C: Machine M-204 anomaly, LOW priority order PO-1089, 
     alternate machine M-207 available → expect STOP_MACHINE

## Architecture
- Single FastAPI app, deployed on Google Cloud Run
- SQLite database, seeded at startup, file: data/demo.db
- All endpoints are called by OpenClaw claws as HTTP tools
- Node-RED (local PC) pushes telemetry to PUT /machine/{id}/telemetry
- Dashboard at GET / reads decision logs and telemetry live

## Build tiers
- Tier 1: All read APIs + mock execution + decision log + dashboard
- Tier 2: Add PUT /machine/{id}/telemetry, live dashboard panel
- Tier 3: Add Events API, anomaly detection in telemetry write path

## Rules
- No auth on any endpoint (demo only)
- Every endpoint returns JSON
- SQLite only — no external database
- Seed data must always be present on startup (INSERT OR IGNORE)
- Never change an existing endpoint's response shape between tiers
  — only add new endpoints
```

---

## Session 1 — Project scaffold + database
```
Read BRIEF.md first.

Create the complete project scaffold for a FastAPI application.

DIRECTORY STRUCTURE:
demo-services/
├── main.py
├── database.py
├── routers/
│   ├── __init__.py
│   ├── telemetry.py
│   ├── orders.py
│   ├── maintenance.py
│   ├── resources.py
│   ├── execution.py
│   ├── events.py
│   └── logs.py
├── models.py
├── seed.py
├── templates/
│   └── dashboard.html      ← empty placeholder for now
├── data/                   ← gitignored, created at runtime
├── .env.example
├── .gitignore
├── Dockerfile
├── requirements.txt
└── README.md

DATABASE — database.py must:
  - Use Python built-in sqlite3
  - Database file path: data/demo.db
  - Create the data/ directory if it doesn't exist
  - Expose get_db() that returns a connection with 
    row_factory = sqlite3.Row
  - Call init_db() on import which creates all tables 
    then calls seed_db()

TABLES — create all tables for all three tiers upfront:

machines:
  id            TEXT PRIMARY KEY   -- "M-204", "M-207"
  name          TEXT NOT NULL
  vibration_percentile  INTEGER    -- 0-100
  bearing_wear  TEXT               -- "low"|"medium"|"high"
  last_maintenance_days_ago INTEGER
  failure_probability   REAL       -- 0.0-1.0
  status        TEXT DEFAULT 'running'  -- "running"|"stopped"|"maintenance"
  last_updated  TEXT DEFAULT (datetime('now'))

orders:
  id            TEXT PRIMARY KEY   -- "PO-1042"
  product       TEXT NOT NULL
  priority      TEXT NOT NULL      -- "LOW"|"MEDIUM"|"HIGH"
  due_days      INTEGER
  units_remaining INTEGER
  total_units   INTEGER
  assigned_machine_id TEXT
  status        TEXT DEFAULT 'active' -- "active"|"rescheduled"|"complete"

maintenance_history:
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  machine_id    TEXT NOT NULL
  date          TEXT NOT NULL
  type          TEXT NOT NULL
  outcome       TEXT NOT NULL

decision_logs:
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  scenario_id   TEXT NOT NULL
  trigger_type  TEXT DEFAULT 'manual'  -- "manual"|"anomaly"
  context_snapshot    TEXT             -- JSON
  options_evaluated   TEXT             -- JSON array
  selected_option     TEXT
  reasoning           TEXT             -- JSON array
  policy_trace        TEXT             -- JSON array
  execution_log       TEXT             -- JSON array
  created_at    TEXT DEFAULT (datetime('now'))

events:
  id            INTEGER PRIMARY KEY AUTOINCREMENT
  machine_id    TEXT NOT NULL
  event_type    TEXT NOT NULL          -- "vibration_anomaly"
  severity      TEXT NOT NULL          -- "warning"|"critical"
  vibration_percentile INTEGER
  scenario_id   TEXT                   -- inferred from machine state
  status        TEXT DEFAULT 'pending' -- "pending"|"acknowledged"
  created_at    TEXT DEFAULT (datetime('now'))
  acknowledged_at TEXT

SEED DATA — seed.py, called from database.py init:
  Machines:
    M-204: CNC Lathe Unit 4, vibration_percentile=87, 
           bearing_wear="high", last_maintenance_days_ago=42,
           failure_probability=0.72, status="running"
    M-207: CNC Lathe Unit 7, vibration_percentile=12,
           bearing_wear="low", last_maintenance_days_ago=8,
           failure_probability=0.04, status="available"

  Orders:
    PO-1042: "Drill collar assembly", priority="HIGH", 
             due_days=3, units_remaining=18, total_units=40,
             assigned_machine_id="M-204", status="active"
    PO-1089: "Pipe coupling batch", priority="LOW",
             due_days=14, units_remaining=40, total_units=40,
             assigned_machine_id="M-204", status="active"

  Maintenance history for M-204:
    2025-02-12: "bearing replacement", outcome="resolved"
    2024-11-03: "routine inspection",  outcome="ok"

  Use INSERT OR IGNORE on all seed rows.

MODELS — models.py:
  Pydantic models for all request/response bodies.
  Every router imports its models from here.
  Use from __future__ import annotations.

REQUIREMENTS:
  fastapi
  uvicorn[standard]
  jinja2
  python-dotenv
  pydantic

DOCKERFILE:
  FROM python:3.11-slim
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  RUN mkdir -p data
  EXPOSE 8080
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

README:
  Setup instructions, how to run locally, 
  how to seed, Cloud Run deploy command.

Do not implement any router logic yet — 
leave all router files with a single placeholder route 
that returns {"status": "not implemented"}.
Only database.py, seed.py, models.py, main.py scaffold, 
Dockerfile, and requirements.txt should be fully implemented.

Verify: running `python -c "from database import init_db; 
init_db(); print('OK')"` should create data/demo.db 
with all tables and seed data without errors.
```

---

## Session 2 — Read APIs (Tier 1)
```
Read BRIEF.md first. Database and scaffold are already built.

Implement the four read API routers. These are called by the 
OpenClaw decision claw as context-gathering tools.
All return JSON. No auth. No pagination needed.

── routers/telemetry.py ──────────────────────────────────────

GET /machine/{machine_id}
  Returns full machine record from SQLite.
  Response shape:
  {
    "id": "M-204",
    "name": "CNC Lathe Unit 4",
    "vibration_percentile": 87,
    "bearing_wear": "high",
    "last_maintenance_days_ago": 42,
    "failure_probability": 0.72,
    "status": "running",
    "last_updated": "2026-03-27T11:00:00",
    "anomaly_detected": true        ← true if vibration_percentile > 80
  }
  404 if machine not found.

GET /machine/{machine_id}/history
  Returns last 5 maintenance records for this machine,
  newest first. Array of:
  { "date": "...", "type": "...", "outcome": "..." }

── routers/orders.py ─────────────────────────────────────────

GET /orders/active/{machine_id}
  Returns the active order assigned to this machine.
  Response shape:
  {
    "id": "PO-1042",
    "product": "Drill collar assembly",
    "priority": "HIGH",
    "due_days": 3,
    "units_remaining": 18,
    "total_units": 40,
    "completion_percentage": 55.0,
    "assigned_machine_id": "M-204",
    "status": "active"
  }
  404 if no active order for this machine.
  completion_percentage = ((total-remaining)/total)*100, 
  rounded to 1 decimal.

── routers/resources.py ──────────────────────────────────────

GET /machines/available
  Returns all machines with status = "available" or "running"
  that are NOT the machine_id passed as a query parameter.
  Query param: exclude_machine_id (optional)
  Example: GET /machines/available?exclude_machine_id=M-204
  Response: array of machine records, same shape as 
  GET /machine/{id} but without anomaly_detected field.
  Empty array if none available.

GET /machines/available/{machine_id}
  Returns a single machine record if it exists and is available.
  Used by claws to verify a specific alternate machine.
  404 if not found or not available.

── routers/maintenance.py ────────────────────────────────────

GET /maintenance/{machine_id}/summary
  Returns a summary for the decision claw:
  {
    "machine_id": "M-204",
    "total_services": 2,
    "last_service_date": "2025-02-12",
    "last_service_type": "bearing replacement",
    "last_service_outcome": "resolved",
    "days_since_last_service": 42,
    "bearing_replaced_recently": true   ← true if bearing replacement 
                                           in last 60 days
  }

── main.py ───────────────────────────────────────────────────

Register all four routers with prefix /api/v1.
Final URL examples:
  GET /api/v1/machine/M-204
  GET /api/v1/orders/active/M-204
  GET /api/v1/machines/available?exclude_machine_id=M-204
  GET /api/v1/maintenance/M-204/summary

Add a root health check:
  GET /health → {"status": "ok", "db": "connected"}
  Test DB by running SELECT 1.

Verify by running uvicorn locally and hitting each endpoint 
with curl. Show the expected curl commands and responses 
in a comment block at the bottom of each router file.
```

---

## Session 3 — Mock execution API (Tier 1)
```
Read BRIEF.md first.

Implement routers/execution.py — mock execution endpoints.
These are called ONLY by the OpenClaw policy claw, 
after it has approved an action. They simulate ERP/CMMS calls.

All three endpoints must:
  - Accept a JSON body
  - Write a structured log entry to decision_logs if 
    a log_id is provided in the body (optional field)
  - Return a success response with a simulated reference number
  - Never fail (always return 200 — mock system is always "up")
  - Print a human-readable line to stdout so it's visible 
    in Cloud Run logs during demo

── POST /api/v1/execute/reschedule ───────────────────────────

Request body:
{
  "order_id": "PO-1042",
  "from_machine_id": "M-204",
  "to_machine_id": "M-207",
  "setup_time_hours": 1.5,
  "reason": "bearing failure risk",
  "log_id": 1           ← optional, links to decision_logs row
}

Actions:
  1. Update orders table: assigned_machine_id = to_machine_id,
     status = "rescheduled"
  2. Update machines table: set M-207 status = "running"
  3. Return:
  {
    "status": "executed",
    "action": "RESCHEDULE_ORDER",
    "reference": "ERP-XXXX",    ← 4 random digits
    "message": "Order PO-1042 rescheduled from M-204 to M-207. 
                Resume after 1.5h setup.",
    "timestamp": "..."
  }

── POST /api/v1/execute/ticket ───────────────────────────────

Request body:
{
  "machine_id": "M-204",
  "issue_type": "bearing inspection",
  "priority": "urgent",
  "assigned_to": "maintenance team",
  "log_id": 1
}

Actions:
  1. Insert into maintenance_history with type=issue_type, 
     outcome="scheduled", date=today
  2. Update machines table: status = "maintenance"
  3. Return:
  {
    "status": "executed",
    "action": "CREATE_MAINTENANCE_TICKET",
    "reference": "MT-XXXX",
    "message": "Ticket MT-XXXX opened for M-204: 
                bearing inspection. Priority: urgent.",
    "timestamp": "..."
  }

── POST /api/v1/execute/notify ───────────────────────────────

Request body:
{
  "recipient_role": "shift floor manager",
  "subject": "Production decision — M-204",
  "message": "full message text",
  "log_id": 1
}

Actions:
  1. No DB write needed
  2. Return:
  {
    "status": "executed",
    "action": "NOTIFY_SUPERVISOR",
    "reference": "MSG-XXXX",
    "message": "Alert delivered to shift floor manager.",
    "timestamp": "..."
  }

── POST /api/v1/log ──────────────────────────────────────────

Also implement the decision log write endpoint here:

Request body:
{
  "scenario_id": "A",
  "trigger_type": "manual",
  "context_snapshot": {},       ← any JSON object
  "options_evaluated": [],      ← array
  "selected_option": "SHIFT_PRODUCTION",
  "reasoning": [],              ← array
  "policy_trace": [],           ← array
  "execution_log": []           ← array
}

Inserts into decision_logs, returns:
{ "id": 1, "created_at": "..." }

── GET /api/v1/log ───────────────────────────────────────────

Query params: limit (default 10, max 50)
Returns last N rows from decision_logs, newest first.
Deserialise all JSON fields before returning.
Response: { "decisions": [...], "total": N }
```

---

## Session 4 — Telemetry write + Events API (Tier 2 & 3)
```
Read BRIEF.md first.

Add the Tier 2 and Tier 3 endpoints. These are ADDITIVE — 
do not modify any existing endpoint.

── PUT /api/v1/machine/{machine_id}/telemetry  (Tier 2) ──────

Called by Node-RED every 10 seconds with a live sensor reading.

Request body:
{
  "vibration_percentile": 87,
  "bearing_wear": "high",          ← optional
  "failure_probability": 0.72      ← optional
}

Actions:
  1. Update machines table with provided fields + last_updated = now
  2. ANOMALY DETECTION (Tier 3 logic, implement now):
     If vibration_percentile > 80 AND no pending event exists 
     for this machine:
       - Determine scenario_id by looking at assigned order priority
         and alternate machine availability:
           HIGH priority + alternate available → "A"
           HIGH priority + no alternate        → "B"  
           LOW priority  + alternate available → "C"
       - Insert into events table:
           machine_id, event_type="vibration_anomaly",
           severity="critical" if >90 else "warning",
           vibration_percentile, scenario_id, status="pending"
  3. Return updated machine record (same shape as GET /machine/{id})

── GET /api/v1/events/pending  (Tier 3) ─────────────────────

Called by the OpenClaw decision claw as its first tool call
in autonomous mode.

Returns all events with status = "pending", newest first:
{
  "events": [
    {
      "id": 1,
      "machine_id": "M-204",
      "event_type": "vibration_anomaly",
      "severity": "critical",
      "vibration_percentile": 87,
      "scenario_id": "A",
      "status": "pending",
      "created_at": "..."
    }
  ],
  "count": 1
}

── POST /api/v1/events/{event_id}/acknowledge  (Tier 3) ──────

Called by the decision claw when it has finished processing 
an event.

Request body:
{
  "log_id": 1       ← links to the decision_logs row
}

Actions:
  1. Update events: status="acknowledged", 
     acknowledged_at=now
  2. Return: { "status": "acknowledged", "event_id": 1 }
  404 if event not found or already acknowledged.

── Also add a test data helper ───────────────────────────────

POST /api/v1/dev/reset
  Resets all machine telemetry back to seed values,
  clears all events (status != "pending" stays, 
  deletes pending ones),
  clears decision_logs.
  Returns: {"status": "reset", "message": "Seed data restored"}
  
  This is used before each demo run to get back to 
  a clean state. Only needed in dev — add a check:
  only works if ENV=development (set in .env).
```

---

## Session 5 — Dashboard (Tier 1 + 2 + 3)
```
Read BRIEF.md first.

Build templates/dashboard.html — a single self-contained HTML 
file served by FastAPI via Jinja2. No build step. No framework. 
Tailwind CSS via CDN. Vanilla JS only.

The dashboard has three visual states:

STATE 1 — Waiting (no decisions yet)
  Large centred message: "Waiting for first scenario..."
  Below it: three manual trigger buttons, one per scenario
  Each button labelled with the scenario letter and a one-line 
  description pulled from a JS constant at top of the file.

STATE 2 — Decision loaded (after trigger or on page load 
          if decisions exist)
  Three-column layout:

  LEFT COLUMN — Context
    Card: Machine state
      Machine ID and name
      Vibration percentile with a horizontal bar 
        (red if >80, amber if >60, green if <=60)
      Bearing wear badge
      Days since last service
      Failure probability as percentage
    Card: Active order
      Order ID, product name
      Priority badge (red=HIGH, amber=MEDIUM, green=LOW)
      Due in N days
      Units remaining / total as a progress bar
    Card: Resources
      Alternate machine available — green tick + machine ID
      OR "No alternate available" — red cross

  CENTRE COLUMN — Decision
    Heading: selected option name (e.g. SHIFT_PRODUCTION)
             in large text, purple
    Options table:
      Columns: Option | Risk | Cost | Delivery | Score
      Each score shown as a number + thin horizontal bar
      Selected row highlighted with purple background
    Reasoning:
      Numbered list of reasoning steps
      Each step on its own line

  RIGHT COLUMN — Policy audit + execution
    Section heading: "Policy audit trace"
    One card per action:
      Action name as monospace
      APPROVED (green) or REJECTED (red) badge
      Policies matched as small pills
      One-sentence reason
      Timestamp in small muted text
    Section heading: "Execution log"
    Monospace log lines, each prefixed with:
      [ERP], [CMMS], or [NOTIFY]
      Timestamp on the left, message on the right

STATE 3 — Live telemetry panel (Tier 2, shown when 
          telemetry data is updating)
  Narrow top bar above the three columns:
    Machine M-204: vibration gauge (number + animated bar)
    Machine M-207: status pill
    Updates every 5 seconds via fetch to 
    /api/v1/machine/M-204

BEHAVIOUR:
  On load: fetch GET /api/v1/log?limit=1
    If result exists: render STATE 2 with that decision
    If empty: render STATE 1

  Manual trigger buttons (all three states):
    POST to /api/v1/trigger/{scenario_id}
    Show spinner on button while waiting
    On response: render STATE 2

  Polling: every 5 seconds fetch /api/v1/log?limit=1
    If created_at is newer than current: re-render STATE 2
    Also fetch /api/v1/machine/M-204 and update telemetry bar

  Add a "Reset demo" button (small, top right):
    Only visible if ENV=development
    POSTs to /api/v1/dev/reset then clears STATE 2 to STATE 1

STYLE GUIDE:
  White background. Subtle gray borders. 
  Purple (#534AB7) for selected/primary. 
  Green (#1D9E75) for approved/low risk. 
  Red (#E24B4A) for rejected/high risk. 
  Amber (#BA7517) for warnings. 
  Monospace font for log lines and action names.
  Works at 1280px width minimum.
```

---

## Session 6 — Trigger endpoint + main.py wiring
```
Read BRIEF.md first.

Add one more endpoint and complete main.py wiring.

── POST /api/v1/trigger/{scenario_id} ───────────────────────

This is the endpoint the dashboard calls when a presenter 
clicks a scenario button. It is NOT called by OpenClaw — 
it exists only to let the dashboard simulate an event 
arriving so the demo can be triggered from the browser 
without needing the NemoClaw CLI.

It does NOT run the agent logic. Instead it:
  1. Validates scenario_id is "A", "B", or "C"
  2. Resets machine M-204 telemetry to seed anomaly values
     (vibration_percentile=87, bearing_wear="high", 
      failure_probability=0.72) if not already there
  3. Inserts a pending event for M-204 with the correct 
     scenario_id
  4. Returns:
  {
    "status": "event_created",
    "scenario_id": "A",
    "event_id": 1,
    "message": "Anomaly event created. 
                Run the decision claw in NemoClaw to process it.",
    "machine_state": { ...current M-204 record... }
  }

The dashboard shows a message: "Event created — run the 
decision claw in NemoClaw" after this call.

── Complete main.py ──────────────────────────────────────────

Register all routers:
  app.include_router(telemetry.router,   prefix="/api/v1")
  app.include_router(orders.router,      prefix="/api/v1")
  app.include_router(resources.router,   prefix="/api/v1")
  app.include_router(maintenance.router, prefix="/api/v1")
  app.include_router(execution.router,   prefix="/api/v1")
  app.include_router(events.router,      prefix="/api/v1")
  app.include_router(logs.router,        prefix="/api/v1")

Startup event: call database.init_db()

Serve dashboard at GET / using Jinja2Templates
  Pass to template:
    env = os.getenv("ENV", "production")

Add CORS middleware allowing all origins 
(demo only — NemoClaw claw needs to call from its sandbox).

GET /health returns:
  {
    "status": "ok",
    "env": "development"|"production",
    "db_path": "data/demo.db",
    "tables": ["machines","orders","maintenance_history",
               "decision_logs","events"]
  }
  Verify each table exists in the DB before returning.

── Final smoke test ──────────────────────────────────────────

Add a script smoke_test.py that:
  1. Calls GET /health
  2. Calls GET /api/v1/machine/M-204
  3. Calls GET /api/v1/orders/active/M-204
  4. Calls GET /api/v1/machines/available?exclude_machine_id=M-204
  5. Calls GET /api/v1/maintenance/M-204/summary
  6. Calls POST /api/v1/trigger/A
  7. Calls GET /api/v1/events/pending
  8. Calls POST /api/v1/execute/reschedule with dummy body
  9. Calls GET /api/v1/log
  Prints PASS or FAIL for each. 
  Runs against http://localhost:8080 by default, 
  accepts base URL as CLI argument.
```

---

## Session 7 — Dockerfile + deploy
```
Read BRIEF.md first.

Finalise deployment configuration.

── Dockerfile (update from Session 1) ───────────────────────

FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p data
ENV ENV=production
EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

── .env.example ─────────────────────────────────────────────

ENV=development
PORT=8080

── .gitignore ───────────────────────────────────────────────

data/
*.db
.env
__pycache__/
*.pyc
.DS_Store

── Cloud Run deploy script: deploy.sh ───────────────────────

#!/bin/bash
# Usage: ./deploy.sh YOUR_PROJECT_ID
PROJECT_ID=$1
SERVICE_NAME=demo-services
REGION=us-central1

gcloud run deploy $SERVICE_NAME \
  --source . \
  --project $PROJECT_ID \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars ENV=production \
  --min-instances 1 \
  --port 8080 \
  --memory 512Mi

echo ""
echo "Service URL:"
gcloud run services describe $SERVICE_NAME \
  --region $REGION \
  --format "value(status.url)"

── nodered/flow.json ────────────────────────────────────────

Node-RED flow with two tabs:

Tab 1 — "Telemetry simulator (Tier 2)":
  Three inject nodes (one per scenario profile) each wired 
  to a function node that builds the telemetry payload 
  (different vibration_percentile per scenario: 
   A=87, B=87, C=87 — same anomaly, different order context).
  Then an HTTP request node: PUT YOUR_CLOUD_RUN_URL/api/v1/machine/M-204/telemetry
  Then a debug node showing the response.
  Also a timer inject (every 10s) cycling through 
  a graduated ramp: 45→55→65→75→85→87 percentile values
  to simulate the anomaly building up over time.

Tab 2 — "Manual triggers (Tier 1 fallback)":
  Three inject nodes labelled "Trigger A", "Trigger B", 
  "Trigger C" wired to an HTTP request node:
  POST YOUR_CLOUD_RUN_URL/api/v1/trigger/{scenario_id}
  Then debug node.

Use YOUR_CLOUD_RUN_URL as a placeholder throughout.
Export as valid Node-RED flow JSON array.
```

---

## Claude Code session order
```
Session 1 → Scaffold + database + seed     test: python -c "from database import init_db; init_db()"
Session 2 → Read APIs                      test: uvicorn main:app --reload + curl each endpoint
Session 3 → Execution + log APIs           test: curl POST each execution endpoint
Session 4 → Telemetry write + Events API   test: curl PUT /telemetry + GET /events/pending
Session 5 → Dashboard                      test: open browser at localhost:8080
Session 6 → Trigger endpoint + wiring      test: python smoke_test.py
Session 7 → Dockerfile + deploy            test: ./deploy.sh YOUR_PROJECT_ID
                                                  python smoke_test.py https://YOUR_CLOUD_RUN_URL