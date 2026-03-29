from datetime import datetime
from fastapi import APIRouter
from database import get_db

router = APIRouter()


@router.get("/maintenance/{machine_id}/summary")
def get_maintenance_summary(machine_id: str):
    with get_db() as conn:
        # Get maintenance history for this machine
        history_rows = conn.execute(
            "SELECT date, type, outcome FROM maintenance_history WHERE machine_id = ? ORDER BY date DESC",
            (machine_id,),
        ).fetchall()

        # Get machine's last_maintenance_days_ago from machines table
        machine_row = conn.execute(
            "SELECT last_maintenance_days_ago FROM machines WHERE id = ?",
            (machine_id,),
        ).fetchone()

        days_since_last_service = None
        if machine_row and machine_row["last_maintenance_days_ago"] is not None:
            days_since_last_service = machine_row["last_maintenance_days_ago"]

        total_services = len(history_rows)

        last_service_date = None
        last_service_type = None
        last_service_outcome = None
        bearing_replaced_recently = False

        if history_rows:
            most_recent = history_rows[0]
            last_service_date = most_recent["date"]
            last_service_type = most_recent["type"]
            last_service_outcome = most_recent["outcome"]

            # Check if any record in the last 60 days has type containing "bearing"
            today = datetime.now().date()
            for row in history_rows:
                record_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
                days_diff = (today - record_date).days
                if days_diff <= 60 and "bearing" in row["type"].lower():
                    bearing_replaced_recently = True
                    break

        return {
            "machine_id": machine_id,
            "total_services": total_services,
            "last_service_date": last_service_date,
            "last_service_type": last_service_type,
            "last_service_outcome": last_service_outcome,
            "days_since_last_service": days_since_last_service,
            "bearing_replaced_recently": bearing_replaced_recently,
        }


# curl examples
# GET /api/v1/maintenance/M-204/summary
#   curl http://localhost:8080/api/v1/maintenance/M-204/summary
#
# Expected: {"machine_id":"M-204","total_services":2,...}
