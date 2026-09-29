"""
AuditGuard AI - ETL: Clean, validate, and prepare transaction data.
"""

import pandas as pd
import numpy as np
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUTPUT_DIR = DATA_DIR

REQUIRED_TX_COLS = [
    "transaction_id", "employee_id", "department", "amount", "timestamp",
    "location", "transaction_type", "approval_status", "approver_id",
    "user_role", "access_level", "device_id"
]

def load_raw():
    tx = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"), parse_dates=["timestamp"])
    emp = pd.read_csv(os.path.join(DATA_DIR, "employees.csv"))
    return tx, emp

def clean_transactions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Standardize
    df["transaction_id"] = df["transaction_id"].astype(str).str.strip()
    df["employee_id"] = df["employee_id"].astype(str).str.strip()
    df["approver_id"] = df["approver_id"].astype(str).str.strip().replace({"nan": None, "None": None})
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # Drop pure nulls in critical fields
    before = len(df)
    df = df.dropna(subset=["transaction_id", "employee_id", "amount", "timestamp"])
    dropped = before - len(df)
    if dropped:
        print(f"  Dropped {dropped} rows with null critical fields")

    # Flag negative/zero amounts
    df["amount_flag"] = df["amount"] <= 0
    df.loc[df["amount"] <= 0, "amount"] = np.nan  # will be handled later or kept for investigation

    # Hour and day features for anomaly detection
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6])
    df["is_after_hours"] = (df["hour"] < 7) | (df["hour"] >= 20)

    # Amount buckets
    df["amount_bucket"] = pd.cut(
        df["amount"].fillna(0),
        bins=[0, 1000, 5000, 15000, 50000, np.inf],
        labels=["Low", "Medium", "High", "Very High", "Critical"]
    )

    return df

def validate(df: pd.DataFrame) -> dict:
    report = {
        "total_rows": len(df),
        "null_amounts": int(df["amount"].isna().sum()),
        "duplicate_tx_ids": int(df["transaction_id"].duplicated().sum()),
        "negative_or_zero_amount": int((df["amount"].fillna(0) <= 0).sum()),
        "future_timestamps": int((df["timestamp"] > datetime.now()).sum()),
        "unique_employees": df["employee_id"].nunique(),
        "date_range": (str(df["timestamp"].min()), str(df["timestamp"].max())),
    }
    return report

def main():
    print("Loading raw data...")
    tx, emp = load_raw()
    print(f"  Raw transactions: {len(tx):,}")

    print("Cleaning...")
    tx_clean = clean_transactions(tx)

    print("Validating...")
    report = validate(tx_clean)
    for k, v in report.items():
        print(f"  {k}: {v}")

    # Persist cleaned
    out_path = os.path.join(OUTPUT_DIR, "transactions_clean.csv")
    tx_clean.to_csv(out_path, index=False)
    print(f"\nCleaned data saved -> {out_path}")

    # Also save validation report
    report_path = os.path.join(OUTPUT_DIR, "validation_report.txt")
    with open(report_path, "w") as f:
        f.write("AuditGuard AI - Data Validation Report\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n\n")
        for k, v in report.items():
            f.write(f"{k}: {v}\n")
    print(f"Validation report -> {report_path}")

    return tx_clean, emp

if __name__ == "__main__":
    main()
