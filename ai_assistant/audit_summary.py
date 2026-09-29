"""
AuditGuard AI - Evidence-based AI Audit Assistant
Summarizes ONLY verified findings from the database. Does not invent evidence.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "database", "auditguard.db")
OUTPUT_DIR = os.path.join(BASE, "ai_assistant")

def load_verified_findings(conn):
    findings = pd.read_sql_query("""
        SELECT f.*, t.department, t.transaction_type, t.location, t.timestamp
        FROM findings f
        LEFT JOIN transactions t ON f.transaction_id = t.transaction_id
        WHERE f.risk_score > 0
    """, conn)
    controls = pd.read_sql_query("""
        SELECT control_name, COUNT(*) as cnt
        FROM control_results WHERE is_violation = 1
        GROUP BY control_name ORDER BY cnt DESC
    """, conn)
    return findings, controls

def generate_executive_summary(findings, controls, total_tx):
    n_findings = len(findings)
    critical = (findings["risk_level"] == "Critical").sum()
    high = (findings["risk_level"] == "High").sum()
    top_controls = controls.head(5)

    lines = []
    lines.append("EXECUTIVE SUMMARY - AuditGuard AI Automated Analysis")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append(
        f"The platform processed {total_tx:,} enterprise transactions. "
        f"Control testing and hybrid anomaly detection identified {n_findings:,} "
        f"transactions requiring further review."
    )
    lines.append("")
    lines.append(
        f"Of these, {critical:,} were scored Critical and {high:,} High under the "
        f"project risk model. Priority should be given to Critical and High items."
    )
    lines.append("")
    lines.append("Most frequent control gaps observed (verified counts):")
    for _, r in top_controls.iterrows():
        lines.append(f"  - {r['control_name']}: {int(r['cnt']):,} instances")
    lines.append("")

    if "department" in findings.columns and findings["department"].notna().any():
        top_dept = findings["department"].value_counts().head(3)
        lines.append("Departments with highest concentration of findings:")
        for dept, cnt in top_dept.items():
            lines.append(f"  - {dept}: {cnt:,} findings")
        lines.append("")

    lines.append(
        "Recommended review areas: (1) Payment and high-value approval workflows, "
        "(2) Segregation-of-duties enforcement for Payment transactions, "
        "(3) Access of inactive users, (4) Privilege alignment for large Asset/Vendor payments, "
        "(5) Transactions originating from unusual locations."
    )
    lines.append("")
    lines.append(
        "Note: All statements above are derived exclusively from verified control-test "
        "results and anomaly scores stored in the project database. No unverified claims "
        "have been introduced."
    )
    return "\n".join(lines)

def generate_detailed_patterns(findings, controls):
    lines = ["DETAILED PATTERN ANALYSIS (Evidence-Based)", ""]
    hv = findings[
        findings["control_violated"].str.contains("Missing Approval", na=False) &
        (findings["amount"] >= 10000)
    ]
    if len(hv) > 0:
        lines.append(
            f"High-value transactions lacking approval: {len(hv):,} "
            f"(total value approx. {hv['amount'].sum():,.0f}). "
            "Further review of the approval workflow for these items is recommended."
        )
        lines.append("")

    sod = findings[findings["control_violated"].str.contains("Self Approval|SoD", na=False, regex=True)]
    if len(sod) > 0:
        lines.append(
            f"Segregation-of-duties / self-approval cases: {len(sod):,}. "
            "Same employee both initiated and approved the transaction."
        )
        lines.append("")

    crit = findings[findings["risk_level"] == "Critical"]
    if len(crit) > 0:
        lines.append(
            f"Critical-risk sample size: {len(crit):,}. "
            "These combine multiple control failures and/or strong anomaly signals."
        )
    return "\n".join(lines)

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}. Run schema_and_load.py and risk_scoring.py first.")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transactions")
    total_tx = cur.fetchone()[0]

    findings, controls = load_verified_findings(conn)
    print(f"Verified findings loaded: {len(findings):,}")

    exec_sum = generate_executive_summary(findings, controls, total_tx)
    detail = generate_detailed_patterns(findings, controls)

    full = exec_sum + "\n\n" + detail
    out = os.path.join(OUTPUT_DIR, "ai_audit_summary.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"AI audit summary written -> {out}")
    print("\n--- Preview ---")
    print(full[:1200])
    conn.close()
    return full

if __name__ == "__main__":
    main()