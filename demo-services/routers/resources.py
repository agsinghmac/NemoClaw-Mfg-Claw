from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from database import get_db
from models import MachineRecord

router = APIRouter()


@router.get("/machines/available")
def get_available_machines(exclude_machine_id: Optional[str] = Query(None)):
    with get_db() as conn:
        if exclude_machine_id:
            rows = conn.execute(
                "SELECT * FROM machines WHERE status = 'available' AND id != ?",
                (exclude_machine_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM machines WHERE status = 'available'"
            ).fetchall()

        machines = [
            {
                "id": r["id"],
                "name": r["name"],
                "vibration_percentile": r["vibration_percentile"],
                "bearing_wear": r["bearing_wear"],
                "last_maintenance_days_ago": r["last_maintenance_days_ago"],
                "failure_probability": r["failure_probability"],
                "status": r["status"],
                "last_updated": r["last_updated"],
            }
            for r in rows
        ]

        return {"machines": machines, "count": len(machines)}


@router.get("/machines/available/{machine_id}")
def get_available_machine(machine_id: str):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM machines WHERE id = ? AND status = 'available'",
            (machine_id,),
        ).fetchone()

        if not row:
            raise HTTPException(status_code=404, detail=f"Machine {machine_id} not available")

        return {
            "id": row["id"],
            "name": row["name"],
            "vibration_percentile": row["vibration_percentile"],
            "bearing_wear": row["bearing_wear"],
            "last_maintenance_days_ago": row["last_maintenance_days_ago"],
            "failure_probability": row["failure_probability"],
            "status": row["status"],
            "last_updated": row["last_updated"],
        }


# curl examples
# GET /api/v1/machines/available
#   curl http://localhost:8080/api/v1/machines/available
#
# Expected: {"machines":[{"id":"M-207","name":"CNC Lathe Unit 7",...}],"count":1}
