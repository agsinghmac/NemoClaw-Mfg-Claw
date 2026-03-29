import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("data/demo.db")


def _get_conn() -> sqlite3.Connection:
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db():
    conn = _get_conn()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    conn = _get_conn()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machines (
                id                        TEXT PRIMARY KEY,
                name                      TEXT NOT NULL,
                vibration_percentile      INTEGER,
                bearing_wear              TEXT,
                last_maintenance_days_ago INTEGER,
                failure_probability       REAL,
                status                    TEXT DEFAULT 'running',
                last_updated              TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id                  TEXT PRIMARY KEY,
                product             TEXT NOT NULL,
                priority            TEXT NOT NULL,
                due_days            INTEGER,
                units_remaining     INTEGER,
                total_units         INTEGER,
                assigned_machine_id TEXT,
                status              TEXT DEFAULT 'active'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_history (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                date       TEXT NOT NULL,
                type       TEXT NOT NULL,
                outcome    TEXT NOT NULL,
                UNIQUE(machine_id, date, type)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS decision_logs (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id      TEXT NOT NULL,
                trigger_type     TEXT DEFAULT 'manual',
                context_snapshot TEXT,
                options_evaluated TEXT,
                selected_option  TEXT,
                reasoning        TEXT,
                policy_trace     TEXT,
                execution_log    TEXT,
                created_at       TEXT DEFAULT (datetime('now'))
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id           TEXT NOT NULL,
                event_type           TEXT NOT NULL,
                severity             TEXT NOT NULL,
                vibration_percentile INTEGER,
                scenario_id          TEXT,
                status               TEXT DEFAULT 'pending',
                created_at           TEXT DEFAULT (datetime('now')),
                acknowledged_at     TEXT
            )
        """)

        conn.commit()
    finally:
        conn.close()

    seed_db()


def seed_db() -> None:
    from seed import run_seed
    run_seed()


