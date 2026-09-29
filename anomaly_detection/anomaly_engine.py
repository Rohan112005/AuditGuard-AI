"""
AuditGuard AI - Hybrid Anomaly Detection
1. Rule-based (transparent, explainable)
2. Isolation Forest (unsupervised ML)
"""

import sqlite3
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"
OUTPUT_DIR = os.path.join(BASE, "anomaly_detection")

def load_transactions(conn):
    df = pd.read_sql_query("""
        SELECT transaction_id, employee_id, department, amount, timestamp,
               location, transaction_type, approval_status, approver_id,
               user_role, access_level, hour, day_of_week, is_weekend,
               is_after_hours, amount_bucket
        FROM transactions
    """, conn)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def rule_based_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Transparent project rules."""
    flags = pd.DataFrame(index=df.index)
    flags["rule_high_value"] = (df["amount"] >= 50000).astype(int)
    flags["rule_after_hours"] = df["is_after_hours"].astype(int)
    flags["rule_missing_approval"] = (
        (df["approval_status"] != "Approved") | (df["approver_id"].isna()) | (df["approver_id"] == "")
    ).astype(int)
    flags["rule_self_approval"] = (df["employee_id"] == df["approver_id"]).astype(int)
    flags["rule_unusual_location"] = df["location"].isin(
        ["Unknown", "Offshore", "Sanctioned Zone"]
    ).astype(int)
    # Frequency proxy: will be enriched later if needed
    flags["rule_score"] = (
        flags["rule_high_value"] * 3 +
        flags["rule_after_hours"] * 1 +
        flags["rule_missing_approval"] * 2 +
        flags["rule_self_approval"] * 3 +
        flags["rule_unusual_location"] * 2
    )
    flags["is_rule_anomaly"] = (flags["rule_score"] >= 2).astype(int)
    return flags

def isolation_forest_scores(df: pd.DataFrame, contamination=0.05) -> pd.Series:
    """Isolation Forest on engineered features."""
    work = df.copy()

    # Encode categoricals
    le_loc = LabelEncoder()
    le_type = LabelEncoder()
    le_role = LabelEncoder()
    le_dept = LabelEncoder()

    work["loc_enc"] = le_loc.fit_transform(work["location"].astype(str))
    work["type_enc"] = le_type.fit_transform(work["transaction_type"].astype(str))
    work["role_enc"] = le_role.fit_transform(work["user_role"].astype(str))
    work["dept_enc"] = le_dept.fit_transform(work["department"].astype(str))

    features = [
        "amount", "hour", "day_of_week", "is_weekend", "is_after_hours",
        "loc_enc", "type_enc", "role_enc", "dept_enc"
    ]
    X = work[features].fillna(0).values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = IsolationForest(
        n_estimators=150,
        contamination=contamination,
        random_state=42,
        n_jobs=-1
    )
    preds = model.fit_predict(X_scaled)  # -1 = anomaly
    # anomaly score: lower (more negative) = more anomalous; convert to 0-1 higher = more anomalous
    raw_scores = model.decision_function(X_scaled)
    # Invert and normalize to 0-100 roughly
    anomaly_score = 1 / (1 + np.exp(raw_scores * 5))  # sigmoid of inverted
    anomaly_score = (anomaly_score - anomaly_score.min()) / (anomaly_score.max() - anomaly_score.min() + 1e-9) * 100

    is_if_anomaly = (preds == -1).astype(int)
    return pd.Series(anomaly_score, index=df.index, name="if_anomaly_score"), \
           pd.Series(is_if_anomaly, index=df.index, name="is_if_anomaly")

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Run database/schema_and_load.py first")

    conn = sqlite3.connect(DB_PATH)
    print("Loading transactions for anomaly detection...")
    df = load_transactions(conn)
    print(f"  {len(df):,} records")

    print("Running rule-based detection...")
    rules = rule_based_flags(df)

    print("Running Isolation Forest...")
    if_scores, if_flags = isolation_forest_scores(df, contamination=0.04)

    result = df[["transaction_id", "employee_id", "amount", "department"]].copy()
    result = pd.concat([result, rules, if_scores, if_flags], axis=1)
    result["is_any_anomaly"] = ((result["is_rule_anomaly"] == 1) | (result["is_if_anomaly"] == 1)).astype(int)

    out_path = os.path.join(OUTPUT_DIR, "anomaly_results.csv")
    result.to_csv(out_path, index=False)
    print(f"\nAnomaly results saved -> {out_path}")
    print(f"  Rule anomalies: {result['is_rule_anomaly'].sum():,}")
    print(f"  Isolation Forest anomalies: {result['is_if_anomaly'].sum():,}")
    print(f"  Combined (any): {result['is_any_anomaly'].sum():,}")

    # Persist key columns back? We'll join later in risk engine.
    # Save a compact table for risk engine
    compact = result[["transaction_id", "is_rule_anomaly", "rule_score",
                      "if_anomaly_score", "is_if_anomaly", "is_any_anomaly"]]
    compact.to_csv(os.path.join(OUTPUT_DIR, "anomaly_scores.csv"), index=False)

    conn.close()
    return result

if __name__ == "__main__":
    main()
