import sqlite3
from pathlib import Path

DB_PATH = Path("data/demo.db")


def run_seed() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Machines
    cursor.execute("""
        INSERT OR IGNORE INTO machines
        (id, name, vibration_percentile, bearing_wear, last_maintenance_days_ago, failure_probability, status)
        VALUES ('M-204', 'CNC Lathe Unit 4', 87, 'high', 42, 0.72, 'running')
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO machines
        (id, name, vibration_percentile, bearing_wear, last_maintenance_days_ago, failure_probability, status)
        VALUES ('M-207', 'CNC Lathe Unit 7', 12, 'low', 8, 0.04, 'available')
    """)

    # Orders
    cursor.execute("""
        INSERT OR REPLACE INTO orders
        (id, product, priority, due_days, units_remaining, total_units, assigned_machine_id, status)
        VALUES ('PO-1042', 'Drill collar assembly', 'HIGH', 3, 18, 40, 'M-204', 'active')
    """)

    cursor.execute("""
        INSERT OR REPLACE INTO orders
        (id, product, priority, due_days, units_remaining, total_units, assigned_machine_id, status)
        VALUES ('PO-1089', 'Pipe coupling batch', 'LOW', 14, 40, 40, 'M-204', 'active')
    """)

    # Maintenance history for M-204
    cursor.execute("""
        INSERT OR IGNORE INTO maintenance_history
        (machine_id, date, type, outcome)
        VALUES ('M-204', '2025-02-12', 'bearing replacement', 'resolved')
    """)

    cursor.execute("""
        INSERT OR IGNORE INTO maintenance_history
        (machine_id, date, type, outcome)
        VALUES ('M-204', '2024-11-03', 'routine inspection', 'ok')
    """)

    conn.commit()
    conn.close()
