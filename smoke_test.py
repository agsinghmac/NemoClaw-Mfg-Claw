#!/usr/bin/env python3
"""
Smoke test for Demo Services API.
Run against local or deployed endpoint.

Usage:
  python smoke_test.py                          # localhost:8080
  python smoke_test.py https://YOUR_CLOUD_RUN_URL
"""

import sys
import os

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
IS_DEV = os.getenv("ENV", "production") == "development"

import requests

# Detect ENV from health endpoint (more reliable than env var)
try:
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    if r.status_code == 200:
        IS_DEV = r.json().get("env") == "development"
except Exception:
    pass

# ─── Helpers ───────────────────────────────────────────────

def assert_eq(actual, expected, msg=""):
    if actual != expected:
        return False, f"{msg}: expected {expected!r}, got {actual!r}"
    return True, ""


def assert_in(key, container, msg=""):
    if key not in container:
        return False, f"{msg}: key {key!r} not in container"
    return True, ""


def assert_status(resp, code, msg=""):
    return assert_eq(resp.status_code, code, msg)


# ─── GROUP 1 — Health + infrastructure ──────────────────────

def test_health():
    r = requests.get(f"{BASE_URL}/health")
    passed, msg = assert_status(r, 200, "health")
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "ok", "health status")
    if not passed:
        return False, msg
    passed, msg = assert_in("tables", data.get("db", {}), "db.tables")
    if not passed:
        return False, msg
    tables = data["db"]["tables"]
    for t in ["machines", "orders", "maintenance_history", "decision_logs", "events"]:
        if t not in tables:
            return False, f"Missing table: {t}"
    passed, msg = assert_eq(data["db"]["counts"]["machines"], 2, "machine count")
    if not passed:
        return False, msg
    return True, ""


# ─── GROUP 2 — Read APIs ───────────────────────────────────

def test_get_machine_m204():
    r = requests.get(f"{BASE_URL}/api/v1/machine/M-204")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("id"), "M-204", "machine id")
    if not passed:
        return False, msg
    passed, msg = assert_in("vibration_percentile", data, "vibration_percentile")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(data["vibration_percentile"], int), True, "vibration is int")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(data.get("anomaly_detected"), bool), True, "anomaly_detected is bool")
    return passed, msg


def test_get_machine_not_found():
    r = requests.get(f"{BASE_URL}/api/v1/machine/INVALID")
    passed, msg = assert_status(r, 404)
    return passed, msg


def test_get_machine_history():
    r = requests.get(f"{BASE_URL}/api/v1/machine/M-204/history")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_in("records", data, "records field")
    if not passed:
        return False, msg
    passed, msg = assert_eq(len(data["records"]) >= 2, True, "at least 2 history records")
    return passed, msg


def test_get_active_order():
    r = requests.get(f"{BASE_URL}/api/v1/orders/active/M-204")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    # Response is {"orders": [...]} - get first order
    passed, msg = assert_eq(data.get("orders", [{}])[0].get("id"), "PO-1042", "order id")
    if not passed:
        return False, msg
    order = data["orders"][0]
    passed, msg = assert_eq(isinstance(order.get("completion_percentage"), float), True, "completion_percentage is float")
    if not passed:
        return False, msg
    pct = order["completion_percentage"]
    passed, msg = assert_eq(0 <= pct <= 100, True, f"completion_percentage {pct} in range")
    return passed, msg


def test_get_order_not_found():
    r = requests.get(f"{BASE_URL}/api/v1/orders/active/M-207")
    passed, msg = assert_status(r, 404)
    return passed, msg


def test_get_available_machines():
    r = requests.get(f"{BASE_URL}/api/v1/machines/available")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_in("machines", data, "machines field")
    if not passed:
        return False, msg
    machine_ids = [m["id"] for m in data["machines"]]
    passed, msg = assert_eq("M-207" in machine_ids, True, "M-207 in available machines")
    return passed, msg


def test_get_available_machines_exclude():
    r = requests.get(f"{BASE_URL}/api/v1/machines/available?exclude_machine_id=M-207")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    machine_ids = [m["id"] for m in data.get("machines", [])]
    passed, msg = assert_eq("M-207" in machine_ids, False, "M-207 NOT in excluded results")
    return passed, msg


def test_get_available_machine_by_id():
    r = requests.get(f"{BASE_URL}/api/v1/machines/available/M-207")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("id"), "M-207", "machine id")
    return passed, msg


def test_get_unavailable_machine():
    r = requests.get(f"{BASE_URL}/api/v1/machines/available/M-204")
    passed, msg = assert_status(r, 404)
    return passed, msg


def test_get_maintenance_summary():
    r = requests.get(f"{BASE_URL}/api/v1/maintenance/M-204/summary")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("machine_id"), "M-204", "machine_id")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("total_services", 0) >= 2, True, "at least 2 maintenance events")
    return passed, msg


# ─── GROUP 3 — Execution APIs ──────────────────────────────

def test_execute_reschedule():
    r = requests.post(
        f"{BASE_URL}/api/v1/execute/reschedule",
        json={
            "order_id": "PO-1042",
            "from_machine_id": "M-204",
            "to_machine_id": "M-207",
            "setup_time_hours": 1.5,
            "reason": "test"
        }
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "executed", "status")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("reference", "").startswith("ERP-"), True, "reference starts with ERP-")
    if not passed:
        return False, msg
    passed, msg = assert_eq(len(data.get("reference", "")), 8, "reference length 8")
    return passed, msg


def test_execute_ticket():
    r = requests.post(
        f"{BASE_URL}/api/v1/execute/ticket",
        json={
            "machine_id": "M-204",
            "issue_type": "bearing inspection",
            "priority": "urgent",
            "assigned_to": "maintenance team"
        }
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "executed", "status")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("reference", "").startswith("MT-"), True, "reference starts with MT-")
    return passed, msg


def test_execute_notify():
    r = requests.post(
        f"{BASE_URL}/api/v1/execute/notify",
        json={
            "recipient_role": "shift floor manager",
            "subject": "Test",
            "message": "Test message"
        }
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "executed", "status")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("reference", "").startswith("MSG-"), True, "reference starts with MSG-")
    return passed, msg


# ─── GROUP 4 — Decision log ─────────────────────────────────

def test_write_decision_log():
    r = requests.post(
        f"{BASE_URL}/api/v1/log",
        json={
            "scenario_id": "A",
            "trigger_type": "manual",
            "options_evaluated": [
                {"name": "SHIFT_PRODUCTION", "risk_score": 0.18, "cost_score": 0.45, "delivery_score": 0.08, "final_score": 0.21}
            ],
            "reasoning": ["Test reasoning step"]
        }
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(isinstance(data.get("id"), int), True, "id is int")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(data.get("created_at"), str), True, "created_at is string")
    return passed, msg


def test_read_decision_log():
    r = requests.get(f"{BASE_URL}/api/v1/log?limit=5")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_in("decisions", data, "decisions field")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(data["decisions"], list), True, "decisions is list")
    if not passed:
        return False, msg
    if len(data["decisions"]) == 0:
        return False, "No decision logs found"
    latest = data["decisions"][0]
    passed, msg = assert_eq(isinstance(latest.get("options_evaluated"), list), True, "options_evaluated is list not string")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(latest.get("reasoning"), list), True, "reasoning is list not string")
    return passed, msg


# ─── GROUP 5 — Telemetry + Events ───────────────────────────

def test_telemetry_normal():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.put(
        f"{BASE_URL}/api/v1/machine/M-204/telemetry",
        json={"vibration_percentile": 45}
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("vibration_percentile"), 45, "vibration_percentile")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("event_created"), False, "event_created false")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("anomaly_detected"), False, "anomaly_detected false")
    return passed, msg


def test_telemetry_anomaly():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.put(
        f"{BASE_URL}/api/v1/machine/M-204/telemetry",
        json={"vibration_percentile": 87, "bearing_wear": "high"}
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("event_created"), True, "event_created true")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("anomaly_detected"), True, "anomaly_detected true")
    return passed, msg


def test_no_duplicate_events():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.put(
        f"{BASE_URL}/api/v1/machine/M-204/telemetry",
        json={"vibration_percentile": 87}
    )
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("event_created"), False, "event_created false (no duplicate)")
    return passed, msg


def test_get_pending_events():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.get(f"{BASE_URL}/api/v1/events/pending")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("count", 0) >= 1, True, "at least 1 pending event")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data["events"][0].get("machine_id"), "M-204", "machine_id M-204")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data["events"][0].get("scenario_id") in ["A", "B", "C"], True, "valid scenario_id")
    return passed, msg


def test_acknowledge_event():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    # Get a pending event first
    r = requests.get(f"{BASE_URL}/api/v1/events/pending")
    data = r.json()
    if data.get("count", 0) == 0:
        return False, "No pending events to acknowledge"
    event_id = data["events"][0]["id"]
    r = requests.post(f"{BASE_URL}/api/v1/events/{event_id}/acknowledge")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "acknowledged", "acknowledge status")
    return passed, msg


def test_double_acknowledge():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    # Get a pending event first
    r = requests.get(f"{BASE_URL}/api/v1/events/pending")
    data = r.json()
    if data["count"] == 0:
        # No pending events - create one first
        requests.put(
            f"{BASE_URL}/api/v1/machine/M-204/telemetry",
            json={"vibration_percentile": 87}
        )
        r = requests.get(f"{BASE_URL}/api/v1/events/pending")
        data = r.json()
    event_id = data["events"][0]["id"]
    # Acknowledge
    requests.post(f"{BASE_URL}/api/v1/events/{event_id}/acknowledge")
    # Try again
    r = requests.post(f"{BASE_URL}/api/v1/events/{event_id}/acknowledge")
    passed, msg = assert_status(r, 400)
    return passed, msg


# ─── GROUP 6 — Trigger endpoint ─────────────────────────────

def test_trigger_scenario_a():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.post(f"{BASE_URL}/api/v1/trigger/A")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("status"), "event_created", "status")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("scenario_id"), "A", "scenario_id")
    if not passed:
        return False, msg
    passed, msg = assert_eq(isinstance(data.get("event_id"), int), True, "event_id is int")
    if not passed:
        return False, msg
    passed, msg = assert_eq(data.get("machine_state", {}).get("anomaly_detected"), True, "anomaly_detected")
    return passed, msg


def test_trigger_scenario_b():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    # Reset first
    requests.post(f"{BASE_URL}/api/v1/dev/reset")
    r = requests.post(f"{BASE_URL}/api/v1/trigger/B")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("scenario_id"), "B", "scenario_id")
    if not passed:
        return False, msg
    # M-207 should be running (no alternate available)
    r = requests.get(f"{BASE_URL}/api/v1/machines/available?exclude_machine_id=M-204")
    r_data = r.json()
    passed, msg = assert_eq(len(r_data.get("machines", [])), 0, "no available machines (M-207 running)")
    return passed, msg


def test_trigger_scenario_c():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    # Reset first
    requests.post(f"{BASE_URL}/api/v1/dev/reset")
    r = requests.post(f"{BASE_URL}/api/v1/trigger/C")
    passed, msg = assert_status(r, 200)
    if not passed:
        return False, msg
    data = r.json()
    passed, msg = assert_eq(data.get("scenario_id"), "C", "scenario_id")
    if not passed:
        return False, msg
    # Check order priority is LOW
    r = requests.get(f"{BASE_URL}/api/v1/orders/active/M-204")
    o_data = r.json()
    # Response is {"orders": [...]} - get first order
    passed, msg = assert_eq(o_data.get("orders", [{}])[0].get("priority"), "LOW", "order priority LOW")
    return passed, msg


def test_trigger_invalid():
    if not IS_DEV:
        return None, "SKIPPED (not development)"
    r = requests.post(f"{BASE_URL}/api/v1/trigger/X")
    passed, msg = assert_status(r, 422)
    return passed, msg


# ─── Test runner ────────────────────────────────────────────

TESTS = [
    ("GROUP 1 — Health + infrastructure", [
        ("test_health", test_health),
    ]),
    ("GROUP 2 — Read APIs", [
        ("test_get_machine_m204", test_get_machine_m204),
        ("test_get_machine_not_found", test_get_machine_not_found),
        ("test_get_machine_history", test_get_machine_history),
        ("test_get_active_order", test_get_active_order),
        ("test_get_order_not_found", test_get_order_not_found),
        ("test_get_available_machines", test_get_available_machines),
        ("test_get_available_machines_exclude", test_get_available_machines_exclude),
        ("test_get_available_machine_by_id", test_get_available_machine_by_id),
        ("test_get_unavailable_machine", test_get_unavailable_machine),
        ("test_get_maintenance_summary", test_get_maintenance_summary),
    ]),
    ("GROUP 3 — Execution APIs", [
        ("test_execute_reschedule", test_execute_reschedule),
        ("test_execute_ticket", test_execute_ticket),
        ("test_execute_notify", test_execute_notify),
    ]),
    ("GROUP 4 — Decision log", [
        ("test_write_decision_log", test_write_decision_log),
        ("test_read_decision_log", test_read_decision_log),
    ]),
    ("GROUP 5 — Telemetry + Events", [
        ("test_telemetry_normal", test_telemetry_normal),
        ("test_telemetry_anomaly", test_telemetry_anomaly),
        ("test_no_duplicate_events", test_no_duplicate_events),
        ("test_get_pending_events", test_get_pending_events),
        ("test_acknowledge_event", test_acknowledge_event),
        ("test_double_acknowledge", test_double_acknowledge),
    ]),
    ("GROUP 6 — Trigger endpoint", [
        ("test_trigger_scenario_a", test_trigger_scenario_a),
        ("test_trigger_scenario_b", test_trigger_scenario_b),
        ("test_trigger_scenario_c", test_trigger_scenario_c),
        ("test_trigger_invalid", test_trigger_invalid),
    ]),
]


def reset_if_dev():
    if IS_DEV:
        try:
            requests.post(f"{BASE_URL}/api/v1/dev/reset", timeout=5)
        except Exception:
            pass


def main():
    print(f"Smoke test against: {BASE_URL}")
    print(f"ENV: {'development' if IS_DEV else 'production'}")
    print()

    total = 0
    passed = 0
    failed = []

    for i, (group_name, tests) in enumerate(TESTS):
        print(group_name)
        for test_name, test_fn in tests:
            total += 1
            try:
                result, msg = test_fn()
            except Exception as e:
                result, msg = False, f"Exception: {e}"

            if result is None:
                # SKIPPED
                print(f"  --  {test_name} (skipped)")
                print(f"       {msg}")
            elif result:
                passed += 1
                print(f"  PASS  {test_name}")
            else:
                failed.append((test_name, msg))
                print(f"  FAIL  {test_name}")
                print(f"       {msg}")
        print()

        # Reset between groups (except after last group)
        if IS_DEV and i < len(TESTS) - 1:
            reset_if_dev()

    # Final reset
    if IS_DEV:
        reset_if_dev()
        print("Demo state restored to seed values")

    print()
    print(f"{'✓' if len(failed) == 0 else '✗'}  {passed}/{total} tests passed")

    if failed:
        print()
        print("Failed tests:")
        for name, msg in failed:
            print(f"  {name}: {msg}")
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
