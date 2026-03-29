import json
import random
from datetime import datetime

from fastapi import APIRouter

from database import get_db
from models import (
    ExecuteRescheduleRequest,
    ExecuteRescheduleResponse,
    ExecuteTicketRequest,
    ExecuteTicketResponse,
    ExecuteNotifyRequest,
    ExecuteNotifyResponse,
)

router = APIRouter()


def generate_reference(prefix: str) -> str:
    return f"{prefix}-{random.randint(1000, 9999)}"


@router.post("/execute/reschedule", response_model=ExecuteRescheduleResponse)
def execute_reschedule(request: ExecuteRescheduleRequest):
    reference = generate_reference("ERP")
    timestamp = datetime.now().isoformat()

    with get_db() as conn:
        # Update order
        conn.execute(
            "UPDATE orders SET assigned_machine_id = ?, status = 'rescheduled' WHERE id = ?",
            (request.to_machine_id, request.order_id),
        )
        # Update target machine to running
        conn.execute(
            "UPDATE machines SET status = 'running' WHERE id = ?",
            (request.to_machine_id,),
        )
        conn.commit()

    print(f"[ERP] {timestamp} ORDER {request.order_id} rescheduled: "
          f"{request.from_machine_id} → {request.to_machine_id}. "
          f"Setup: {request.setup_time_hours}h. Ref: {reference}")

    return ExecuteRescheduleResponse(
        status="executed",
        action="RESCHEDULE_ORDER",
        reference=reference,
        order_id=request.order_id,
        from_machine_id=request.from_machine_id,
        to_machine_id=request.to_machine_id,
        message=f"Order {request.order_id} rescheduled from {request.from_machine_id} to {request.to_machine_id}. "
                f"Resume after {request.setup_time_hours}h setup.",
        timestamp=timestamp,
    )


@router.post("/execute/ticket", response_model=ExecuteTicketResponse)
def execute_ticket(request: ExecuteTicketRequest):
    reference = generate_reference("MT")
    timestamp = datetime.now().isoformat()
    today = datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        # Insert maintenance history
        conn.execute(
            "INSERT INTO maintenance_history (machine_id, date, type, outcome) VALUES (?, ?, ?, ?)",
            (request.machine_id, today, request.issue_type, "scheduled"),
        )
        # Update machine status
        conn.execute(
            "UPDATE machines SET status = 'maintenance' WHERE id = ?",
            (request.machine_id,),
        )
        conn.commit()

    print(f"[CMMS] {timestamp} Ticket {reference} opened for "
          f"{request.machine_id}: {request.issue_type}. Priority: {request.priority}.")

    return ExecuteTicketResponse(
        status="executed",
        action="CREATE_MAINTENANCE_TICKET",
        reference=reference,
        machine_id=request.machine_id,
        issue_type=request.issue_type,
        priority=request.priority,
        message=f"Ticket {reference} opened for {request.machine_id}: "
                f"{request.issue_type}. Priority: {request.priority}.",
        timestamp=timestamp,
    )


@router.post("/execute/notify", response_model=ExecuteNotifyResponse)
def execute_notify(request: ExecuteNotifyRequest):
    reference = generate_reference("MSG")
    timestamp = datetime.now().isoformat()

    # No SQLite action needed for notifications

    print(f"[NOTIFY] {timestamp} Alert {reference} sent to "
          f"{request.recipient_role}: {request.subject}")

    return ExecuteNotifyResponse(
        status="executed",
        action="NOTIFY_SUPERVISOR",
        reference=reference,
        recipient_role=request.recipient_role,
        subject=request.subject,
        message=f"Alert {reference} delivered to {request.recipient_role}.",
        timestamp=timestamp,
    )


# curl examples
# POST /api/v1/execute/reschedule
#   curl -s -X POST http://localhost:8080/api/v1/execute/reschedule \
#     -H "Content-Type: application/json" \
#     -d '{"order_id": "PO-1042", "from_machine_id": "M-204", "to_machine_id": "M-207", "setup_time_hours": 1.5, "reason": "bearing failure risk"}'
#
# POST /api/v1/execute/ticket
#   curl -s -X POST http://localhost:8080/api/v1/execute/ticket \
#     -H "Content-Type: application/json" \
#     -d '{"machine_id": "M-204", "issue_type": "bearing inspection", "priority": "urgent", "assigned_to": "maintenance team"}'
#
# POST /api/v1/execute/notify
#   curl -s -X POST http://localhost:8080/api/v1/execute/notify \
#     -H "Content-Type: application/json" \
#     -d '{"recipient_role": "shift floor manager", "subject": "Production decision", "message": "test"}'