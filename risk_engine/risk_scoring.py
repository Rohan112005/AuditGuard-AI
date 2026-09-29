"""
AuditGuard AI - Explainable Risk Scoring Engine
Project-defined scoring model (not industry standard):
  Control failure      +30
  Anomaly (rule/IF)    +25
  Missing approval     +25
  Unusual location     +10
  High-value tx        +10
  Self-approval / SoD  +15 (extra weight)
  Inactive user        +20
  Privilege violation  +15

Final score clipped 0-100.
Thresholds: Low <30, Medium 30-54, High 55-74, Critical >=75
"""

import sqlite3
import pandas as pd
import numpy as np
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"
ANOMALY_PATH = os.path.join(BASE, "anomaly_detection", "anomaly_scores.csv")
OUTPUT_DIR = os.path.join(BASE, "risk_engine")

WEIGHTS = {
    "control_failure": 30,
    "anomaly": 25,
    "missing_approval": 25,
    "unusual_location": 10,
    "high_value": 10,
    "sod_self": 15,
    "inactive_user": 20,
    "privilege": 15,
}

def load_data(conn):
    tx = pd.read_sql_query("""
        SELECT transaction_id, employee_id, department, amount, location,
               approval_status, approver_id, user_role, access_level,
               is_after_hours, timestamp
        FROM transactions
    """, conn)

    controls = pd.read_sql_query("""
        SELECT transaction_id, control_id, control_name
        FROM control_results
        WHERE is_violation = 1
    """, conn)

    anomalies = pd.read_csv(ANOMALY_PATH) if os.path.exists(ANOMALY_PATH) else None
    return tx, controls, anomalies

def score_transactions(tx, controls, anomalies):
    # Aggregate controls per transaction
    ctrl_agg = controls.groupby("transaction_id").agg(
        control_count=("control_id", "count"),
        controls_list=("control_name", lambda x: "; ".join(sorted(set(x))))
    ).reset_index()

    df = tx.merge(ctrl_agg, on="transaction_id", how="left")
    df["control_count"] = df["control_count"].fillna(0).astype(int)
    df["controls_list"] = df["controls_list"].fillna("")

    if anomalies is not None:
        df = df.merge(anomalies, on="transaction_id", how="left")
        for c in ["is_rule_anomaly", "is_if_anomaly", "is_any_anomaly", "rule_score", "if_anomaly_score"]:
            if c in df.columns:
                df[c] = df[c].fillna(0)
    else:
        df["is_any_anomaly"] = 0
        df["if_anomaly_score"] = 0
        df["rule_score"] = 0

    # Build score components (explainable)
    df["pts_control"] = np.where(df["control_count"] > 0, WEIGHTS["control_failure"], 0)
    # Extra points for specific severe controls
    df["pts_missing"] = np.where(
        df["controls_list"].str.contains("Missing Approval", na=False), WEIGHTS["missing_approval"], 0
    )
    df["pts_sod"] = np.where(
        df["controls_list"].str.contains("Self Approval|SoD", na=False, regex=True), WEIGHTS["sod_self"], 0
    )
    df["pts_inactive"] = np.where(
        df["controls_list"].str.contains("Inactive User", na=False), WEIGHTS["inactive_user"], 0
    )
    df["pts_privilege"] = np.where(
        df["controls_list"].str.contains("Privilege", na=False), WEIGHTS["privilege"], 0
    )
    df["pts_anomaly"] = np.where(df["is_any_anomaly"] == 1, WEIGHTS["anomaly"], 0)
    df["pts_location"] = np.where(
        df["location"].isin(["Unknown", "Offshore", "Sanctioned Zone"]), WEIGHTS["unusual_location"], 0
    )
    df["pts_high_value"] = np.where(df["amount"] >= 50000, WEIGHTS["high_value"], 0)

    # Total (may exceed 100 before clip)
    component_cols = [
        "pts_control", "pts_missing", "pts_sod", "pts_inactive",
        "pts_privilege", "pts_anomaly", "pts_location", "pts_high_value"
    ]
    df["risk_score_raw"] = df[component_cols].sum(axis=1)
    df["risk_score"] = df["risk_score_raw"].clip(0, 100)

    def level(s):
        if s >= 75:
            return "Critical"
        if s >= 55:
            return "High"
        if s >= 30:
            return "Medium"
        return "Low"

    df["risk_level"] = df["risk_score"].apply(level)

    # Only keep rows that have some signal (score > 0) for findings table, but we can keep all
    return df

def write_findings(conn, scored: pd.DataFrame):
    cur = conn.cursor()
    cur.execute("DELETE FROM findings")
    now = datetime.now().isoformat()

    # Insert findings with risk_score > 0 or any control/anomaly
    findings = scored[
        (scored["risk_score"] > 0) | (scored["control_count"] > 0) | (scored["is_any_anomaly"] == 1)
    ].copy()

    rows = []
    for _, r in findings.iterrows():
        issue = r["controls_list"] if r["controls_list"] else (
            "Anomaly detected" if r.get("is_any_anomaly", 0) == 1 else "Elevated risk"
        )
        rows.append((
            r["transaction_id"],
            r["employee_id"],
            float(r["amount"]) if pd.notna(r["amount"]) else None,
            issue[:500],
            r["controls_list"][:300] if r["controls_list"] else None,
            float(r.get("if_anomaly_score", 0) or 0),
            float(r["risk_score"]),
            r["risk_level"],
            "Open",
            now
        ))

    cur.executemany("""
        INSERT INTO findings (
            transaction_id, employee_id, amount, issue_summary,
            control_violated, anomaly_score, risk_score, risk_level,
            investigation_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    print(f"  Written {len(rows):,} findings to database")
    return len(rows)

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Database missing. Run prior steps.")
    if not os.path.exists(ANOMALY_PATH):
        print("WARNING: anomaly_scores.csv not found – run anomaly_engine first. Continuing with control-only scoring.")

    conn = sqlite3.connect(DB_PATH)
    print("Loading data for risk scoring...")
    tx, controls, anomalies = load_data(conn)
    print(f"  Transactions: {len(tx):,} | Control violation rows: {len(controls):,}")

    print("Computing explainable risk scores...")
    scored = score_transactions(tx, controls, anomalies)

    # Persist full scored set
    out_csv = os.path.join(OUTPUT_DIR, "scored_transactions.csv")
    keep_cols = [
        "transaction_id", "employee_id", "department", "amount", "location",
        "control_count", "controls_list", "is_any_anomaly", "if_anomaly_score",
        "risk_score", "risk_level",
        "pts_control", "pts_missing", "pts_sod", "pts_inactive",
        "pts_privilege", "pts_anomaly", "pts_location", "pts_high_value"
    ]
    scored[[c for c in keep_cols if c in scored.columns]].to_csv(out_csv, index=False)
    print(f"  Scored data -> {out_csv}")

    print("Writing findings table...")
    n = write_findings(conn, scored)

    # Distribution
    print("\nRisk level distribution (all scored):")
    print(scored["risk_level"].value_counts().to_string())
    print("\nRisk level distribution (findings only, score>0):")
    print(scored[scored["risk_score"] > 0]["risk_level"].value_counts().to_string())

    # Summary metrics for resume / report
    metrics = {
        "total_transactions": len(tx),
        "transactions_with_control_violations": int((scored["control_count"] > 0).sum()),
        "transactions_with_anomaly": int((scored["is_any_anomaly"] == 1).sum()),
        "findings_written": n,
        "critical": int((scored["risk_level"] == "Critical").sum()),
        "high": int((scored["risk_level"] == "High").sum()),
        "medium": int((scored["risk_level"] == "Medium").sum()),
        "low": int((scored["risk_level"] == "Low").sum()),
    }
    metrics_path = os.path.join(OUTPUT_DIR, "metrics.json")
    import json
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"\nMetrics -> {metrics_path}")
    print(metrics)

    conn.close()
    return scored

if __name__ == "__main__":
    main()
