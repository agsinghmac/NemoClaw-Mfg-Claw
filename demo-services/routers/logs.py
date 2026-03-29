import json
from typing import Optional

from fastapi import APIRouter, Query

from database import get_db
from models import (
    DecisionLogRequest,
    DecisionLogResponse,
    DecisionLogListResponse,
)

router = APIRouter()


@router.post("/log")
def create_log(request: DecisionLogRequest):
    with get_db() as conn:
        cursor = conn.execute(
            """INSERT INTO decision_logs
               (scenario_id, trigger_type, context_snapshot, options_evaluated,
                selected_option, reasoning, policy_trace, execution_log)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.scenario_id,
                request.trigger_type,
                json.dumps(request.context_snapshot) if request.context_snapshot else None,
                json.dumps(request.options_evaluated) if request.options_evaluated else None,
                request.selected_option,
                json.dumps(request.reasoning) if request.reasoning else None,
                json.dumps(request.policy_trace) if request.policy_trace else None,
                json.dumps(request.execution_log) if request.execution_log else None,
            ),
        )
        conn.commit()

        row = conn.execute(
            "SELECT id, created_at FROM decision_logs WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()

    return {
        "id": row["id"],
        "scenario_id": request.scenario_id,
        "created_at": row["created_at"],
    }


@router.get("/log", response_model=DecisionLogListResponse)
def get_logs(limit: int = Query(10, ge=1, le=50)):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM decision_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()

        total = conn.execute("SELECT COUNT(*) FROM decision_logs").fetchone()[0]

        decisions = []
        for row in rows:
            decisions.append({
                "id": row["id"],
                "scenario_id": row["scenario_id"],
                "trigger_type": row["trigger_type"],
                "context_snapshot": json.loads(row["context_snapshot"]) if row["context_snapshot"] else None,
                "options_evaluated": json.loads(row["options_evaluated"]) if row["options_evaluated"] else None,
                "selected_option": row["selected_option"],
                "reasoning": json.loads(row["reasoning"]) if row["reasoning"] else None,
                "policy_trace": json.loads(row["policy_trace"]) if row["policy_trace"] else None,
                "execution_log": json.loads(row["execution_log"]) if row["execution_log"] else None,
                "created_at": row["created_at"],
            })

    return {
        "decisions": decisions,
        "total": total,
    }


# curl examples
# POST /api/v1/log
#   curl -s -X POST http://localhost:8080/api/v1/log \
#     -H "Content-Type: application/json" \
#     -d '{"scenario_id": "A", "trigger_type": "manual", "context_snapshot": {"machine": "M-204"}, "selected_option": "SHIFT_PRODUCTION"}'
#
# GET /api/v1/log?limit=5
#   curl -s "http://localhost:8080/api/v1/log?limit=5"