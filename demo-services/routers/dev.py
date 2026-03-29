import os

from fastapi import APIRouter, HTTPException

from database import get_db

router = APIRouter()


@router.post("/dev/reset")
def reset_data():
    # Check ENV
    env = os.getenv("ENV", "production")
    if env != "development":
        raise HTTPException(status_code=403, detail="Reset not available in production")

    with get_db() as conn:
        # 1. DELETE FROM events
        events_deleted = conn.execute("DELETE FROM events").rowcount

        # 2. DELETE FROM decision_logs
        logs_deleted = conn.execute("DELETE FROM decision_logs").rowcount

        # 3. DELETE FROM maintenance_history where outcome = "scheduled"
        maintenance_deleted = conn.execute(
            "DELETE FROM maintenance_history WHERE outcome = 'scheduled'"
        ).rowcount

        # 4. Update M-204 to seed values
        conn.execute("""
            UPDATE machines SET
                vibration_percentile = 87,
                bearing_wear = 'high',
                last_maintenance_days_ago = 42,
                failure_probability = 0.72,
                status = 'running',
                last_updated = datetime('now')
            WHERE id = 'M-204'
        """)

        # 5. Update M-207 to seed values
        conn.execute("""
            UPDATE machines SET
                vibration_percentile = 12,
                bearing_wear = 'low',
                last_maintenance_days_ago = 8,
                failure_probability = 0.04,
                status = 'available',
                last_updated = datetime('now')
            WHERE id = 'M-207'
        """)

        # 6. Update PO-1042
        conn.execute("""
            UPDATE orders SET
                status = 'active',
                assigned_machine_id = 'M-204'
            WHERE id = 'PO-1042'
        """)

        # 7. Update PO-1089
        conn.execute("""
            UPDATE orders SET
                status = 'active',
                assigned_machine_id = 'M-204'
            WHERE id = 'PO-1089'
        """)

        conn.commit()

    return {
        "status": "reset",
        "message": "All data restored to seed state",
        "cleared": {
            "events": events_deleted,
            "decision_logs": logs_deleted,
            "maintenance_scheduled": maintenance_deleted,
        },
        "restored": {
            "machines": ["M-204", "M-207"],
            "orders": ["PO-1042", "PO-1089"],
        },
    }


# curl examples
# POST /api/v1/dev/reset (requires ENV=development)
#   curl -s -X POST http://localhost:8080/api/v1/dev/reset