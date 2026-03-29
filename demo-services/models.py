from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# Machine models
class MachineRecord(BaseModel):
    id: str
    name: str
    vibration_percentile: Optional[int] = None
    bearing_wear: Optional[str] = None
    last_maintenance_days_ago: Optional[int] = None
    failure_probability: Optional[float] = None
    status: str = "running"
    last_updated: Optional[str] = None


class TelemetryUpdateRequest(BaseModel):
    vibration_percentile: int
    bearing_wear: Optional[str] = None
    failure_probability: Optional[float] = None
    status: Optional[str] = None


# Order models
class OrderRecord(BaseModel):
    id: str
    product: str
    priority: str
    due_days: Optional[int] = None
    units_remaining: Optional[int] = None
    total_units: Optional[int] = None
    assigned_machine_id: Optional[str] = None
    status: str = "active"


class ActiveOrdersResponse(BaseModel):
    orders: List[OrderRecord]


# Resources models
class AvailableMachinesResponse(BaseModel):
    machines: List[MachineRecord]


# Maintenance models
class MaintenanceRecord(BaseModel):
    id: int
    machine_id: str
    date: str
    type: str
    outcome: str


class MaintenanceSummary(BaseModel):
    machine_id: str
    last_maintenance_date: Optional[str] = None
    total_maintenance_events: int = 0
    recent_events: List[MaintenanceRecord] = Field(default_factory=list)


# Execution models
class ExecuteRescheduleRequest(BaseModel):
    order_id: str
    from_machine_id: str
    to_machine_id: str
    setup_time_hours: float
    reason: Optional[str] = None
    log_id: Optional[int] = None


class ExecuteRescheduleResponse(BaseModel):
    status: str
    action: str
    reference: str
    order_id: str
    from_machine_id: str
    to_machine_id: str
    message: str
    timestamp: str


class ExecuteTicketRequest(BaseModel):
    machine_id: str
    issue_type: str
    priority: str = "MEDIUM"
    assigned_to: Optional[str] = None
    log_id: Optional[int] = None


class ExecuteTicketResponse(BaseModel):
    status: str
    action: str
    reference: str
    machine_id: str
    issue_type: str
    priority: str
    message: str
    timestamp: str


class ExecuteNotifyRequest(BaseModel):
    recipient_role: str
    subject: str
    message: str
    log_id: Optional[int] = None


class ExecuteNotifyResponse(BaseModel):
    status: str
    action: str
    reference: str
    recipient_role: str
    subject: str
    message: str
    timestamp: str


# Decision log models
class DecisionLogRequest(BaseModel):
    scenario_id: str
    trigger_type: str = "manual"
    context_snapshot: Optional[dict[str, Any]] = None
    options_evaluated: Optional[list[dict[str, Any]]] = None
    selected_option: Optional[str] = None
    reasoning: Optional[list[str]] = None
    policy_trace: Optional[list[dict[str, Any]]] = None
    execution_log: Optional[list[dict[str, Any]]] = None


class DecisionLogResponse(BaseModel):
    id: int
    scenario_id: str
    trigger_type: str
    context_snapshot: Optional[dict[str, Any]] = None
    options_evaluated: Optional[list[dict[str, Any]]] = None
    selected_option: Optional[str] = None
    reasoning: Optional[list[str]] = None
    policy_trace: Optional[list[dict[str, Any]]] = None
    execution_log: Optional[list[dict[str, Any]]] = None
    created_at: Optional[str] = None


class DecisionLogListResponse(BaseModel):
    decisions: List[DecisionLogResponse]
    total: int


# Events models
class EventRecord(BaseModel):
    id: int
    machine_id: str
    event_type: str
    severity: str
    vibration_percentile: Optional[int] = None
    scenario_id: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None
    acknowledged_at: Optional[str] = None


class EventsResponse(BaseModel):
    events: List[EventRecord]


class AcknowledgeRequest(BaseModel):
    acknowledged_by: Optional[str] = None


class AcknowledgeResponse(BaseModel):
    success: bool
    event_id: int
    acknowledged_at: str


class TriggerResponse(BaseModel):
    status: str
    message: str


# Health model
class HealthResponse(BaseModel):
    status: str = "ok"
    env: str = "production"
    db: dict = Field(default_factory=dict)
    timestamp: Optional[str] = None


class TriggerResponse(BaseModel):
    status: str
    scenario_id: str
    event_id: int
    description: str
    machine_state: dict
    next_step: str
    timestamp: str
