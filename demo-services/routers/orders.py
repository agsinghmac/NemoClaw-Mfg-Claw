from fastapi import APIRouter, HTTPException

from database import get_db

router = APIRouter()


@router.get("/orders/active/{machine_id}")
def get_active_orders(machine_id: str):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE status = 'active' AND assigned_machine_id = ?",
            (machine_id,),
        ).fetchall()

        if not rows:
            raise HTTPException(status_code=404, detail=f"No active order for {machine_id}")

        orders = []
        for row in rows:
            total = row["total_units"] or 1
            remaining = row["units_remaining"] or 0
            completion = round(((total - remaining) / total) * 100, 1)

            orders.append({
                "id": row["id"],
                "product": row["product"],
                "priority": row["priority"],
                "due_days": row["due_days"],
                "units_remaining": row["units_remaining"],
                "total_units": row["total_units"],
                "completion_percentage": completion,
                "assigned_machine_id": row["assigned_machine_id"],
                "status": row["status"],
            })

        return {"orders": orders}


# curl examples
# GET /api/v1/orders/active/M-204
#   curl http://localhost:8080/api/v1/orders/active/M-204
#
# Expected: {"orders":[{"id":"PO-1042","product":"Drill collar assembly",...}]}
