import os
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from models import TriggerResponse

router = APIRouter()

SCENARIO_DESCRIPTIONS = {
    "A": "High vibration on M-204. HIGH priority order PO-1042 active. Alternate machine M-207 available.",
    "B": "High vibration on M-204. HIGH priority order PO-1042 active. No alternate machine available.",
    "C": "High vibration on M-204. LOW priority order PO-1042 active. Alternate machine M-207 available.",
}


@router.post("/trigger/{scenario_id}", response_model=TriggerResponse)
def trigger_scenario(scenario_id: str):
    """
    Manually trigger a scenario for the demo dashboard.
    Creates an anomaly event for the decision claw to process.
    """
    # Normalise to uppercase
    scenario_id = scenario_id.upper()

    if scenario_id not in SCENARIO_DESCRIPTIONS:
        raise HTTPException(
            status_code=422,
            detail="scenario_id must be A, B, or C"
        )

    with get_db() as conn:
        # STEP 1: Acknowledge any existing pending events for M-204
        conn.execute(
            """UPDATE events
               SET status = 'acknowledged', acknowledged_at = datetime('now')
               WHERE machine_id = 'M-204' AND status = 'pending'"""
        )

        # STEP 2: Reset M-204 telemetry to anomaly state
        conn.execute(
            """UPDATE machines SET
               vibration_percentile = 87,
               bearing_wear = 'high',
               failure_probability = 0.72,
               status = 'running',
               last_updated = datetime('now')
               WHERE id = 'M-204'"""
        )

        # STEP 3: Set alternate machine state based on scenario
        m207_status = "available" if scenario_id in ("A", "C") else "running"
        conn.execute(
            "UPDATE machines SET status = ? WHERE id = 'M-207'",
            (m207_status,)
        )

        # STEP 4: Set order priority based on scenario
        po1042_priority = "HIGH" if scenario_id in ("A", "B") else "LOW"
        conn.execute(
            """UPDATE orders SET
               priority = ?, status = 'active', assigned_machine_id = 'M-204'
               WHERE id = 'PO-1042'""",
            (po1042_priority,)
        )
        conn.execute(
            "UPDATE orders SET status = 'active' WHERE id = 'PO-1089'"
        )

        # STEP 5: Insert a pending event
        cursor = conn.execute(
            """INSERT INTO events
               (machine_id, event_type, severity, vibration_percentile, scenario_id, status)
               VALUES ('M-204', 'vibration_anomaly', 'critical', 87, ?, 'pending')""",
            (scenario_id,)
        )
        event_id = cursor.lastrowid

        conn.commit()

        # STEP 6: Fetch updated M-204 machine record
        machine = conn.execute(
            "SELECT * FROM machines WHERE id = 'M-204'"
        ).fetchone()

        machine_state = {
            "id": machine["id"],
            "name": machine["name"],
            "vibration_percentile": machine["vibration_percentile"],
            "bearing_wear": machine["bearing_wear"],
            "failure_probability": machine["failure_probability"],
            "status": machine["status"],
            "anomaly_detected": machine["vibration_percentile"] > 80,
        }

    return TriggerResponse(
        status="event_created",
        scenario_id=scenario_id,
        event_id=event_id,
        description=SCENARIO_DESCRIPTIONS[scenario_id],
        machine_state=machine_state,
        next_step="Run the decision claw in NemoClaw to process this event.",
        timestamp=datetime.now().isoformat()
    )


# curl examples
# POST /api/v1/trigger/A (ENV=development)
#   curl -s -X POST http://localhost:8080/api/v1/trigger/A
#
# POST /api/v1/trigger/B
#   curl -s -X POST http://localhost:8080/api/v1/trigger/B
#
# POST /api/v1/trigger/C
#   curl -s -X POST http://localhost:8080/api/v1/trigger/C
