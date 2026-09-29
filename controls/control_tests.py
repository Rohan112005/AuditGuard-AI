"""
AuditGuard AI - SQL / Python Control Tests
Detects: missing approvals, unauthorized approvals, self-approval/SoD,
duplicates, inactive users, privilege violations.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def run_control_tests(conn):
    """Run all control tests and insert results into control_results."""
    cur = conn.cursor()
    # Clear previous results
    cur.execute("DELETE FROM control_results")
    now = datetime.now().isoformat()

    # C01 - Missing Approval (especially high value)
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C01', 'Missing Approval', 1,
               'Transaction amount ' || ROUND(t.amount,2) || ' has no approval (status=' || COALESCE(t.approval_status,'NULL') || ')',
               ?
        FROM transactions t
        WHERE (t.approval_status IS NULL OR t.approval_status = 'Pending' OR t.approver_id IS NULL OR t.approver_id = '')
          AND t.amount >= 1000
    """, (now,))
    c01 = cur.rowcount
    print(f"  C01 Missing Approval: {c01} violations")

    # C02 - Unauthorized Approval (approver has Standard/ReadOnly access)
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C02', 'Unauthorized Approval', 1,
               'Approver ' || t.approver_id || ' has insufficient access level',
               ?
        FROM transactions t
        JOIN employees e ON t.approver_id = e.employee_id
        WHERE t.approval_status = 'Approved'
          AND e.access_level IN ('Standard', 'ReadOnly')
          AND t.amount >= 2000
    """, (now,))
    c02 = cur.rowcount
    print(f"  C02 Unauthorized Approval: {c02} violations")

    # C03 - Self Approval / Segregation of Duties
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C03', 'Self Approval / SoD', 1,
               'Employee ' || t.employee_id || ' both created and approved the transaction',
               ?
        FROM transactions t
        WHERE t.employee_id = t.approver_id
          AND t.approval_status = 'Approved'
    """, (now,))
    c03 = cur.rowcount
    print(f"  C03 Self-Approval / SoD: {c03} violations")

    # C04 - Duplicate Transactions (same emp, amount, type within short window – simplified via amount+emp+type count)
    # We detect exact amount + employee + type with multiple rows
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C04', 'Duplicate Transaction', 1,
               'Potential duplicate: same employee, amount and type appears multiple times',
               ?
        FROM transactions t
        WHERE (t.employee_id, t.amount, t.transaction_type) IN (
            SELECT employee_id, amount, transaction_type
            FROM transactions
            GROUP BY employee_id, amount, transaction_type
            HAVING COUNT(*) > 1
        )
    """, (now,))
    c04 = cur.rowcount
    print(f"  C04 Duplicate Transaction: {c04} violations")

    # C05 - Inactive User
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C05', 'Inactive User Activity', 1,
               'Transaction performed by inactive employee ' || t.employee_id,
               ?
        FROM transactions t
        JOIN employees e ON t.employee_id = e.employee_id
        WHERE e.is_active = 0
    """, (now,))
    c05 = cur.rowcount
    print(f"  C05 Inactive User: {c05} violations")

    # C06 - Privilege Violation (Clerk/Analyst with very high amount or Admin-level action)
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C06', 'Privilege Violation', 1,
               'Role ' || t.user_role || ' / access ' || t.access_level || ' inconsistent with amount ' || ROUND(t.amount,2),
               ?
        FROM transactions t
        WHERE (t.user_role IN ('Clerk', 'Analyst') AND t.amount >= 25000)
           OR (t.access_level = 'Standard' AND t.amount >= 40000 AND t.transaction_type IN ('Asset Purchase', 'Vendor Payment'))
    """, (now,))
    c06 = cur.rowcount
    print(f"  C06 Privilege Violation: {c06} violations")

    # C07 - Unusual Amount (project threshold)
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C07', 'Unusual Amount', 1,
               'Amount ' || ROUND(t.amount,2) || ' exceeds project high-value threshold (75000)',
               ?
        FROM transactions t
        WHERE t.amount >= 75000
    """, (now,))
    c07 = cur.rowcount
    print(f"  C07 Unusual Amount: {c07} violations")

    # C08 - After Hours
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C08', 'After-Hours Activity', 1,
               'Transaction at hour ' || t.hour || ' (outside 07:00-20:00)',
               ?
        FROM transactions t
        WHERE t.is_after_hours = 1
    """, (now,))
    c08 = cur.rowcount
    print(f"  C08 After-Hours: {c08} violations")

    # C09 - Unusual Location
    cur.execute("""
        INSERT INTO control_results (transaction_id, control_id, control_name, is_violation, details, detected_at)
        SELECT t.transaction_id, 'C09', 'Unusual Location', 1,
               'Location flagged as unusual: ' || t.location,
               ?
        FROM transactions t
        WHERE t.location IN ('Unknown', 'Offshore', 'Sanctioned Zone')
    """, (now,))
    c09 = cur.rowcount
    print(f"  C09 Unusual Location: {c09} violations")

    conn.commit()
    total = c01 + c02 + c03 + c04 + c05 + c06 + c07 + c08 + c09
    print(f"\nTotal control violation records written: {total}")
    return {
        "C01": c01, "C02": c02, "C03": c03, "C04": c04, "C05": c05,
        "C06": c06, "C07": c07, "C08": c08, "C09": c09, "total": total
    }

def summary_by_control(conn):
    return pd.read_sql_query("""
        SELECT control_id, control_name, COUNT(*) as violation_count
        FROM control_results
        WHERE is_violation = 1
        GROUP BY control_id, control_name
        ORDER BY violation_count DESC
    """, conn)

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run schema_and_load.py first.")
    conn = get_conn()
    try:
        print("Running control tests...")
        counts = run_control_tests(conn)
        print("\nSummary by control:")
        print(summary_by_control(conn).to_string(index=False))
        # Save summary CSV
        out = os.path.join(BASE, "controls", "control_summary.csv")
        summary_by_control(conn).to_csv(out, index=False)
        print(f"\nSummary saved -> {out}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
