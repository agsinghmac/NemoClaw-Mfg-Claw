import json
from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import get_db
from models import TelemetryUpdateRequest

router = APIRouter()


@router.get("/machine/{machine_id}")
def get_machine_telemetry(machine_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

        anomaly_detected = (row["vibration_percentile"] or 0) > 80

        return {
            "id": row["id"],
            "name": row["name"],
            "vibration_percentile": row["vibration_percentile"],
            "bearing_wear": row["bearing_wear"],
            "last_maintenance_days_ago": row["last_maintenance_days_ago"],
            "failure_probability": row["failure_probability"],
            "status": row["status"],
            "last_updated": row["last_updated"],
            "anomaly_detected": anomaly_detected,
        }


@router.get("/machine/{machine_id}/history")
def get_machine_history(machine_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT date, type, outcome FROM maintenance_history WHERE machine_id = ? ORDER BY date DESC LIMIT 5",
            (machine_id,),
        ).fetchall()

        return {
            "machine_id": machine_id,
            "records": [
                {"date": r["date"], "type": r["type"], "outcome": r["outcome"]}
                for r in rows
            ],
        }


@router.put("/machine/{machine_id}/telemetry")
def update_machine_telemetry(machine_id: str, request: TelemetryUpdateRequest):
    timestamp = datetime.now().isoformat()
    event_created = False
    anomaly_detected = False

    # Get fields that were explicitly provided in request (not defaults)
    provided_fields = request.model_fields_set

    with get_db() as conn:
        # STEP 1: Validate machine exists
        row = conn.execute(
            "SELECT * FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not found")

        # STEP 2: Build UPDATE statement only for explicitly provided fields
        updates = ["vibration_percentile = ?", "last_updated = datetime('now')"]
        params = [request.vibration_percentile]

        # Only update bearing_wear if it was explicitly provided in request
        if "bearing_wear" in provided_fields and request.bearing_wear is not None:
            updates.append("bearing_wear = ?")
            params.append(request.bearing_wear)

        # Only update failure_probability if it was explicitly provided in request
        if "failure_probability" in provided_fields and request.failure_probability is not None:
            updates.append("failure_probability = ?")
            params.append(request.failure_probability)

        params.append(machine_id)

        conn.execute(
            f"UPDATE machines SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

        # STEP 3: Anomaly detection
        vibration = request.vibration_percentile
        anomaly_detected = vibration > 80

        if anomaly_detected:
            # Determine scenario_id
            # Get active order for this machine
            order = conn.execute(
                "SELECT priority FROM orders WHERE assigned_machine_id = ? AND status = 'active'",
                (machine_id,),
            ).fetchone()

            # Get available alternate machines
            alternate = conn.execute(
                "SELECT id FROM machines WHERE status = 'available' AND id != ?",
                (machine_id,),
            ).fetchone()

            scenario_id = None

            if order:
                if order["priority"] == "HIGH" and alternate:
                    scenario_id = "A"
                elif order["priority"] == "HIGH" and not alternate:
                    scenario_id = "B"
                elif order["priority"] != "HIGH" and alternate:
                    scenario_id = "C"

            if scenario_id:
                severity = "critical" if vibration > 90 else "warning"

                # ATOMIC INSERT: only insert if no pending event exists
                cursor = conn.execute(
                    """INSERT INTO events
                       (machine_id, event_type, severity, vibration_percentile, scenario_id, status)
                       SELECT ?, ?, ?, ?, ?, 'pending'
                       WHERE NOT EXISTS (
                           SELECT 1 FROM events
                           WHERE machine_id = ? AND status = 'pending'
                       )""",
                    (machine_id, "vibration_anomaly", severity, vibration, scenario_id, machine_id),
                )
                conn.commit()

                # Check if row was actually inserted
                event_created = cursor.rowcount > 0

    # STEP 4: Return updated machine record
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM machines WHERE id = ?", (machine_id,)
        ).fetchone()

        result = {
            "id": row["id"],
            "name": row["name"],
            "vibration_percentile": row["vibration_percentile"],
            "bearing_wear": row["bearing_wear"],
            "last_maintenance_days_ago": row["last_maintenance_days_ago"],
            "failure_probability": row["failure_probability"],
            "status": row["status"],
            "last_updated": row["last_updated"],
            "anomaly_detected": (row["vibration_percentile"] or 0) > 80,
            "event_created": event_created,
        }

    # Print stdout log line
    print(f"[TELEMETRY] {timestamp} {machine_id} vibration: "
          f"{request.vibration_percentile}th pct | "
          f"anomaly: {anomaly_detected} | event_created: {event_created}")

    return result


# curl examples
# GET /api/v1/machine/M-204
#   curl http://localhost:8080/api/v1/machine/M-204
#
# PUT /api/v1/machine/M-204/telemetry
#   curl -s -X PUT http://localhost:8080/api/v1/machine/M-204/telemetry \
#     -H "Content-Type: application/json" \
#     -d '{"vibration_percentile": 87, "bearing_wear": "high", "failure_probability": 0.72}'
#
# Expected: {"id":"M-204","name":"CNC Lathe Unit 4",...}