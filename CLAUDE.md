## What this project is
Simulated REST APIs for an OpenClaw manufacturing decision demo.
Two OpenClaw claws (decision + policy) running inside NemoClaw 
call these endpoints as HTTP tools. This codebase has NO agent 
logic — it is purely data services and a dashboard.

## Architecture
- Single FastAPI app deployed on Google Cloud Run
- SQLite at data/demo.db — seeded on every startup
- All endpoints under /api/v1/
- Dashboard served at GET / via direct file read (not Jinja2, to avoid cwd issues)
- No auth on any endpoint (demo only)

## Three scenarios — always in the database
- A: M-204 anomaly, HIGH priority order, alternate M-207 available
- B: M-204 anomaly, HIGH priority order, NO alternate machine  
- C: M-204 anomaly, LOW priority order, alternate M-207 available

## Project structure
demo-services/
├── main.py              # FastAPI app, router registration, startup
├── database.py          # SQLite connection, init_db(), get_db()
├── seed.py              # INSERT OR IGNORE seed data
├── models.py            # All Pydantic models — import from here
├── routers/
│   ├── telemetry.py     # GET /machine/{id}, PUT /machine/{id}/telemetry
│   ├── orders.py        # GET /orders/active/{machine_id}
│   ├── resources.py     # GET /machines/available
│   ├── maintenance.py   # GET /maintenance/{machine_id}/summary
│   ├── execution.py     # POST /execute/reschedule|ticket|notify
│   ├── events.py        # GET /events/pending, POST /events/{id}/acknowledge
│   ├── logs.py          # POST /log, GET /log
│   ├── dev.py           # POST /dev/reset (dev only)
│   └── trigger.py       # POST /trigger/{scenario_id} (dev only)
├── templates/
│   └── dashboard.html   # Single-page UI, polling JS, no framework
├── smoke_test.py        # End-to-end test — run after every deploy
├── nodered/flow.json    # Node-RED telemetry simulator
└── data/                # Gitignored — created at runtime

## Coding conventions
- Python 3.11
- All models defined in models.py — never inline in routers
- All DB access via get_db() from database.py — never raw sqlite3 
  connections in routers
- Every router file has a curl smoke test comment block at the bottom
- Seed data lives in seed.py only — never duplicated elsewhere
- Datetime fields: always ISO 8601 strings in SQLite, 
  always datetime('now') for defaults
- Error responses: {"detail": "message"} — FastAPI default shape

## Hard rules — do not violate these
- Never change the response shape of an existing endpoint
  New tiers add endpoints, never modify existing ones
- Never add authentication — this is a demo
- Never use an external database — SQLite only
- The data/ directory is gitignored — never commit .db files
- seed.py must use INSERT OR IGNORE everywhere so restarts 
  are always safe
- Port is always 8080 — Cloud Run expects this

## Environment variables
ENV=development|production   (default: production)
PORT=8080

## How to run locally
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

## How to test
python smoke_test.py                          # local
python smoke_test.py https://YOUR_CLOUD_RUN_URL  # deployed

## How to deploy
./deploy.sh YOUR_GCP_PROJECT_ID

## Build tiers — what exists at each tier
Tier 1 (core):    All read APIs + execution + log + dashboard
Tier 2 (telemetry): + PUT /machine/{id}/telemetry + live dashboard panel
Tier 3 (autonomous): + Events API + anomaly detection in telemetry write

## Build log — completed sessions

### Session 1 — Scaffold + database ✓
Created full project structure. database.py initialises 
SQLite at data/demo.db with five tables: machines, orders, 
maintenance_history, decision_logs, events. seed.py populates 
M-204, M-207, PO-1042, PO-1089, and two maintenance records 
using INSERT OR IGNORE. models.py defines all Pydantic models 
for all sessions upfront. main.py registers all routers with 
prefix /api/v1, mounts Jinja2 templates, adds CORS middleware, 
and calls init_db() on startup. Dockerfile targets port 8080 
for Cloud Run.

Verified: all five tables exist, seed data present, 
uvicorn starts cleanly, GET /health returns {"status":"ok"}.

### Session 2 — Read APIs ✓
Implemented four read routers. All registered and working.

  GET /api/v1/machine/{id}
    Returns machine record + computed anomaly_detected 
    (true if vibration_percentile > 80). 404 if not found.

  GET /api/v1/machine/{id}/history
    Returns last 5 maintenance records newest first.

  GET /api/v1/orders/active/{machine_id}
    Returns active order + computed completion_percentage.
    404 if no active order for this machine.

  GET /api/v1/machines/available
    Query param: exclude_machine_id (optional).
    Returns machines with status = "available".

  GET /api/v1/machines/available/{machine_id}
    404 if machine not found or not available.

  GET /api/v1/maintenance/{machine_id}/summary
    Returns computed summary including bearing_replaced_recently.
    Returns zero-value summary if no history — not a 404.

Verified: all endpoints return correct data against seed 
values. 404 cases confirmed. M-207 appears in available 
machines, M-204 does not.

### Session 3 — Execution + log APIs ✓
Implemented execution router and decision log router.

  POST /api/v1/execute/reschedule
    Updates order status to "rescheduled" and 
    assigned_machine_id to to_machine_id.
    Updates destination machine status to "running".
    Returns reference ERP-XXXX.

  POST /api/v1/execute/ticket
    Inserts maintenance_history record with outcome="scheduled".
    Updates machine status to "maintenance".
    Returns reference MT-XXXX.

  POST /api/v1/execute/notify
    No DB write. Returns reference MSG-XXXX.

  POST /api/v1/log
    Inserts into decision_logs serialising all JSON fields 
    with json.dumps(). Returns new row id + created_at.

  GET /api/v1/log
    Returns last N rows (default 10) with all JSON fields 
    deserialised via json.loads(). Never returns raw strings.

All execution endpoints print human-readable stdout lines 
visible in Cloud Run logs. Reference numbers are PREFIX + 
4 random digits. All endpoints always return 200.

Verified: DB state changes confirmed by follow-up GETs. 
JSON fields returned as objects not strings. Seed state 
restored after testing.

### Session 4 — Telemetry write + Events API ✓
Implemented telemetry write endpoint, events router, 
and dev reset endpoint.

  PUT /api/v1/machine/{id}/telemetry
    Updates machine fields dynamically — only updates fields 
    present in request body, never overwrites with null.
    Anomaly detection: if vibration_percentile > 80 AND no 
    pending event exists for this machine, determines 
    scenario_id from order priority + alternate availability 
    and inserts into events table.
    Returns updated machine record + event_created flag.

  GET /api/v1/events/pending
    Returns all events with status="pending" oldest first.
    Empty array if none — not a 404.

  GET /api/v1/events
    Returns all events with optional status filter and limit.

  POST /api/v1/events/{id}/acknowledge
    Sets status="acknowledged", acknowledged_at=now.
    400 if already acknowledged. 404 if not found.

  POST /api/v1/dev/reset
    Only works when ENV=development — 403 in production.
    Restores all machine and order data to seed values.
    Clears events and decision_logs tables.
    Preserves original seed maintenance history records.

Scenario inference logic:
  HIGH priority order + alternate available  → scenario "A"
  HIGH priority order + no alternate         → scenario "B"
  non-HIGH priority + alternate available    → scenario "C"
  no active order                            → no event created

Verified: duplicate event prevention confirmed — second
PUT with anomaly does not create second pending event.
Scenario B correctly detected when M-207 set to running.
Reset restores full seed state. 403 guard not tested
(would need ENV=production).

### Session 5 — Dashboard ✓
Built templates/dashboard.html — single-page UI served
by FastAPI via direct file read (not Jinja2 templates,
to avoid directory resolution issues). Tailwind CSS via CDN.
Vanilla JS only. ENV variable injected server-side into JS.

Three states:
  STATE 1: Waiting — shown when no decisions in log
  STATE 2: Decision loaded — three-column layout
  STATE 3: Anomaly banner — shown when pending events exist

Top bar:
  System title + subtitle (OpenClaw / NemoClaw / Nemotron)
  Live M-204 telemetry pill — updates every 5 seconds
  Three scenario trigger buttons (A, B, C) with tooltips
  Reset button visible only when ENV=development (JS-driven)

Left panel — context:
  Machine state card with vibration bar (red/amber/green)
  Active order card with priority badge and progress bar
  Resources card showing alternate machine or red cross

Centre panel — decision:
  Selected option in large purple text (formatted label)
  Options table with score bars colour-coded by value
  Reasoning steps as numbered list with purple circles

Right panel — policy + execution:
  Policy trace cards: action name, APPROVED/REJECTED badge,
  policy pills, reason text, timestamp
  Execution log in monospace with coloured prefix tags
  [ERP]=blue [CMMS]=amber [NOTIFY]=purple

JS polling:
  Every 5s fetches machine telemetry, pending events,
  and latest log. isUpdating flag prevents race conditions.
  Auto-renders new decision if created_at is newer.
  Aggressive 2s polling for 60s after manual trigger.
  All field access uses optional chaining (?. / ??) —
  missing context_snapshot fields show "--" not blank panels.
  Score bars capped at 100% with Math.min(round(score*100),100).

Also built: routers/trigger.py with POST /api/v1/trigger/{scenario_id}
  Clears existing events, sets M-207 status (available/running),
  updates M-204 telemetry, creates pending event.
  Only works when ENV=development.

Verified: all six verification steps passed. Dashboard
auto-updated without page refresh when decision log posted.
Reset restores seed state. All three scenarios trigger correctly.

### Session 6 — smoke_test.py + health expansion ✓
Expanded GET /health to verify all tables and connection status.
Added smoke_test.py that tests all endpoints implemented in sessions 1-6.
Verified health endpoint returns detailed DB status including table existence and row counts.
Verified smoke test passes all 26 tests covering:
  - Health + infrastructure (1 test)
  - Read APIs (9 tests)
  - Execution APIs (3 tests)
  - Decision log (2 tests)
  - Telemetry + Events (6 tests)
  - Trigger endpoint (5 tests)

## Sessions remaining

### Session 7 — Dockerfile + deploy
  Finalise Dockerfile
  deploy.sh for Cloud Run
  nodered/flow.json
  End-to-end smoke test against live URL

### Session 7 — Dockerfile + deploy
  Finalise Dockerfile
  deploy.sh for Cloud Run
  nodered/flow.json
  End-to-end smoke test against live URL

## What is NOT in this codebase
The OpenClaw claw definitions and NemoClaw network policy 
config are configured separately outside this project.
This codebase has no agent logic — it is purely data 
services and a dashboard. The two claws call these 
endpoints as HTTP tools.