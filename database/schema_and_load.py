"""
AuditGuard AI - Database schema (SQLite for portability) and data load.
PostgreSQL-compatible schema; uses SQLite here for zero-config demo.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data")
DB_PATH = "/tmp/auditguard.db"

SCHEMA_SQL = """
DROP TABLE IF EXISTS findings;
DROP TABLE IF EXISTS control_results;
DROP TABLE IF EXISTS transactions;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS controls_catalog;

CREATE TABLE employees (
    employee_id     TEXT PRIMARY KEY,
    name            TEXT,
    department      TEXT,
    user_role       TEXT,
    access_level    TEXT,
    is_active       INTEGER,
    hire_date       TEXT
);

CREATE TABLE transactions (
    transaction_id      TEXT PRIMARY KEY,
    employee_id         TEXT,
    department          TEXT,
    amount              REAL,
    timestamp           TEXT,
    location            TEXT,
    transaction_type    TEXT,
    approval_status     TEXT,
    approver_id         TEXT,
    user_role           TEXT,
    access_level        TEXT,
    device_id           TEXT,
    hour                INTEGER,
    day_of_week         INTEGER,
    is_weekend          INTEGER,
    is_after_hours      INTEGER,
    amount_bucket       TEXT,
    is_injected_issue   INTEGER,
    injected_issue_type TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

CREATE TABLE controls_catalog (
    control_id      TEXT PRIMARY KEY,
    control_name    TEXT,
    category        TEXT,
    description     TEXT,
    severity_weight REAL
);

CREATE TABLE control_results (
    result_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT,
    control_id      TEXT,
    control_name    TEXT,
    is_violation    INTEGER,
    details         TEXT,
    detected_at     TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    FOREIGN KEY (control_id) REFERENCES controls_catalog(control_id)
);

CREATE TABLE findings (
    finding_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id  TEXT,
    employee_id     TEXT,
    amount          REAL,
    issue_summary   TEXT,
    control_violated TEXT,
    anomaly_score   REAL,
    risk_score      REAL,
    risk_level      TEXT,
    investigation_status TEXT DEFAULT 'Open',
    created_at      TEXT,
    FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id)
);

CREATE INDEX idx_tx_emp ON transactions(employee_id);
CREATE INDEX idx_tx_amount ON transactions(amount);
CREATE INDEX idx_tx_ts ON transactions(timestamp);
CREATE INDEX idx_findings_risk ON findings(risk_score);
CREATE INDEX idx_cr_tx ON control_results(transaction_id);
"""

CONTROLS = [
    ("C01", "Missing Approval", "Approval", "Transaction lacks required approval", 30),
    ("C02", "Unauthorized Approval", "Approval", "Approval performed by unauthorized person", 25),
    ("C03", "Self Approval / SoD", "Segregation of Duties", "Same employee created and approved transaction", 30),
    ("C04", "Duplicate Transaction", "Transaction Integrity", "Potential duplicate payment or claim", 20),
    ("C05", "Inactive User Activity", "Access Control", "Transaction by inactive or terminated user", 25),
    ("C06", "Privilege Violation", "Privilege / Access", "Activity inconsistent with assigned role/access", 20),
    ("C07", "Unusual Amount", "Transaction Control", "Amount significantly outside normal pattern", 15),
    ("C08", "After-Hours Activity", "Transaction Control", "Transaction outside normal business hours", 10),
    ("C09", "Unusual Location", "Transaction Control", "Location inconsistent with expected pattern", 10),
]

def create_schema(conn):
    conn.executescript(SCHEMA_SQL)
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO controls_catalog VALUES (?, ?, ?, ?, ?)",
        CONTROLS
    )
    conn.commit()
    print("Schema created and controls catalog loaded.")

def load_data(conn):
    emp = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))
    emp["is_active"] = emp["is_active"].astype(int)
    emp.to_sql("employees", conn, if_exists="append", index=False)
    print(f"  Loaded {len(emp)} employees")

    # Prefer cleaned if available
    clean_path = os.path.join(DATA_DIR, "transactions_clean.csv")
    raw_path = os.path.join(DATA_DIR, "transactions.csv")
    path = clean_path if os.path.exists(clean_path) else raw_path
    tx = pd.read_csv(path, parse_dates=["timestamp"])

    # Ensure columns exist
    for col in ["hour", "day_of_week", "is_weekend", "is_after_hours", "amount_bucket"]:
        if col not in tx.columns:
            if col == "hour":
                tx["hour"] = pd.to_datetime(tx["timestamp"]).dt.hour
            elif col == "day_of_week":
                tx["day_of_week"] = pd.to_datetime(tx["timestamp"]).dt.dayofweek
            elif col == "is_weekend":
                tx["is_weekend"] = tx["day_of_week"].isin([5, 6]).astype(int)
            elif col == "is_after_hours":
                tx["is_after_hours"] = ((tx["hour"] < 7) | (tx["hour"] >= 20)).astype(int)
            elif col == "amount_bucket":
                tx["amount_bucket"] = "Medium"

    # Convert bools
    for c in ["is_weekend", "is_after_hours", "is_injected_issue"]:
        if c in tx.columns:
            tx[c] = tx[c].astype(int)

    # Stringify timestamp for SQLite
    tx["timestamp"] = pd.to_datetime(tx["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # Keep only columns that exist in table
    keep = [
        "transaction_id", "employee_id", "department", "amount", "timestamp",
        "location", "transaction_type", "approval_status", "approver_id",
        "user_role", "access_level", "device_id", "hour", "day_of_week",
        "is_weekend", "is_after_hours", "amount_bucket", "is_injected_issue",
        "injected_issue_type"
    ]
    tx = tx[[c for c in keep if c in tx.columns]]
    tx.to_sql("transactions", conn, if_exists="append", index=False)
    print(f"  Loaded {len(tx)} transactions from {os.path.basename(path)}")

def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    try:
        create_schema(conn)
        print("Loading data...")
        load_data(conn)
        # Quick counts
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM transactions")
        print(f"  DB transactions: {cur.fetchone()[0]:,}")
        cur.execute("SELECT COUNT(*) FROM employees")
        print(f"  DB employees: {cur.fetchone()[0]:,}")
        cur.execute("SELECT COUNT(*) FROM controls_catalog")
        print(f"  Controls defined: {cur.fetchone()[0]}")
        print(f"\nDatabase ready: {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
