import os
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

load_dotenv()

from database import init_db
from models import HealthResponse
from routers import telemetry, orders, resources, maintenance, execution, events, logs, dev, trigger


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Demo Services", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

app.include_router(telemetry.router, prefix="/api/v1", tags=["telemetry"])
app.include_router(orders.router, prefix="/api/v1", tags=["orders"])
app.include_router(resources.router, prefix="/api/v1", tags=["resources"])
app.include_router(maintenance.router, prefix="/api/v1", tags=["maintenance"])
app.include_router(execution.router, prefix="/api/v1", tags=["execution"])
app.include_router(events.router, prefix="/api/v1", tags=["events"])
app.include_router(logs.router, prefix="/api/v1", tags=["logs"])
app.include_router(dev.router, prefix="/api/v1", tags=["dev"])
app.include_router(trigger.router, prefix="/api/v1", tags=["trigger"])


@app.get("/", response_class=HTMLResponse)
def serve_dashboard(request: Request):
    env = os.getenv("ENV", "production")
    template_path = os.path.join(os.path.dirname(__file__), "templates", "dashboard.html")
    with open(template_path, "r") as f:
        html_content = f.read()
    # Inject env variable into a global JS variable
    html_content = html_content.replace(
        'const ENV = "";',
        f'const ENV = "{env}";'
    )
    return html_content


@app.get("/health", response_model=HealthResponse)
def health():
    from database import DB_PATH

    env = os.getenv("ENV", "production")

    try:
        from database import get_db
        with get_db() as conn:
            # STEP 1: Verify DB connection
            conn.execute("SELECT 1").fetchone()

            # STEP 2: Verify all five tables exist
            tables = [row["name"] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            required_tables = ["machines", "orders", "maintenance_history", "decision_logs", "events"]
            for t in required_tables:
                if t not in tables:
                    raise Exception(f"Missing table: {t}")

            # STEP 3: Count rows in key tables
            machine_count = conn.execute("SELECT COUNT(*) FROM machines").fetchone()[0]
            order_count = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            pending_count = conn.execute("SELECT COUNT(*) FROM events WHERE status='pending'").fetchone()[0]
            log_count = conn.execute("SELECT COUNT(*) FROM decision_logs").fetchone()[0]

        return HealthResponse(
            status="ok",
            env=env,
            db={
                "connected": True,
                "path": str(DB_PATH),
                "tables": required_tables,
                "counts": {
                    "machines": machine_count,
                    "orders": order_count,
                    "pending_events": pending_count,
                    "decision_logs": log_count,
                }
            },
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        return HealthResponse(
            status="error",
            env=env,
            db={"connected": False, "error": str(e)},
            timestamp=datetime.now().isoformat()
        )


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
