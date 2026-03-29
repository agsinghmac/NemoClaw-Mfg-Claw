from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import get_db

router = APIRouter()


@router.get("/events/pending")
def get_pending_events():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM events WHERE status = 'pending' ORDER BY created_at ASC"
        ).fetchall()

        events = []
        for row in rows:
            events.append({
                "id": row["id"],
                "machine_id": row["machine_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "vibration_percentile": row["vibration_percentile"],
                "scenario_id": row["scenario_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "acknowledged_at": row["acknowledged_at"],
            })

        return {"events": events, "count": len(events)}


@router.get("/events")
def get_all_events(
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100)
):
    with get_db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM events WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        events = []
        for row in rows:
            events.append({
                "id": row["id"],
                "machine_id": row["machine_id"],
                "event_type": row["event_type"],
                "severity": row["severity"],
                "vibration_percentile": row["vibration_percentile"],
                "scenario_id": row["scenario_id"],
                "status": row["status"],
                "created_at": row["created_at"],
                "acknowledged_at": row["acknowledged_at"],
            })

        return {"events": events, "count": len(events)}


@router.post("/events/{event_id}/acknowledge")
def acknowledge_event(event_id: int):
    with get_db() as conn:
        # Validate event exists
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        if row["status"] == "acknowledged":
            raise HTTPException(status_code=400, detail=f"Event {event_id} already acknowledged")

        acknowledged_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn.execute(
            "UPDATE events SET status = 'acknowledged', acknowledged_at = ? WHERE id = ?",
            (acknowledged_at, event_id),
        )
        conn.commit()

        return {
            "status": "acknowledged",
            "event_id": event_id,
            "acknowledged_at": acknowledged_at,
        }


# curl examples
# GET /api/v1/events/pending
#   curl http://localhost:8080/api/v1/events/pending
#
# POST /api/v1/events/1/acknowledge
#   curl -s -X POST http://localhost:8080/api/v1/events/1/acknowledge \
#     -H "Content-Type: application/json" \
#     -d '{"log_id": null}'
#
# GET /api/v1/events
#   curl http://localhost:8080/api/v1/events