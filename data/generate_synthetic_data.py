"""
AuditGuard AI - Synthetic Enterprise Transaction Data Generator
Generates realistic transaction data with injected control violations and anomalies.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import os

np.random.seed(42)
random.seed(42)

# Config
N_TRANSACTIONS = 120_000  # Target ~100k-500k; start practical for demo
N_EMPLOYEES = 800
N_DEPARTMENTS = 12
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

DEPARTMENTS = [
    "Finance", "Procurement", "IT", "HR", "Sales", "Operations",
    "Legal", "Marketing", "R&D", "Customer Support", "Logistics", "Admin"
]

TRANSACTION_TYPES = [
    "Payment", "Purchase Order", "Expense Claim", "Invoice", "Refund",
    "Transfer", "Salary", "Vendor Payment", "Travel Claim", "Asset Purchase"
]

LOCATIONS = [
    "New York", "London", "Singapore", "Mumbai", "Berlin", "Tokyo",
    "Sydney", "Toronto", "Dubai", "Sao Paulo", "Remote", "Chicago"
]

ROLES = ["Analyst", "Manager", "Senior Manager", "Director", "Clerk", "Admin", "Auditor"]
ACCESS_LEVELS = ["Standard", "Elevated", "Admin", "ReadOnly"]

def generate_employees(n=N_EMPLOYEES):
    employees = []
    for i in range(1, n + 1):
        dept = random.choice(DEPARTMENTS)
        role = random.choices(ROLES, weights=[30, 25, 15, 8, 15, 5, 2])[0]
        access = "Admin" if role in ["Director", "Admin"] else (
            "Elevated" if role in ["Manager", "Senior Manager"] else
            "ReadOnly" if role == "Auditor" else "Standard"
        )
        active = random.random() > 0.05  # 5% inactive
        employees.append({
            "employee_id": f"EMP{i:05d}",
            "name": f"Employee_{i}",
            "department": dept,
            "user_role": role,
            "access_level": access,
            "is_active": active,
            "hire_date": (datetime(2015, 1, 1) + timedelta(days=random.randint(0, 3000))).strftime("%Y-%m-%d")
        })
    return pd.DataFrame(employees)

def generate_transactions(employees_df, n=N_TRANSACTIONS):
    emp_ids = employees_df["employee_id"].tolist()
    emp_lookup = employees_df.set_index("employee_id").to_dict("index")

    start_date = datetime(2024, 1, 1)
    records = []

    # Base clean transactions
    for i in range(n):
        emp = random.choice(emp_ids)
        emp_info = emp_lookup[emp]
        amount = round(np.random.lognormal(mean=5.5, sigma=1.2), 2)
        if amount > 50000:
            amount = round(amount / 3, 2)
        ts = start_date + timedelta(
            days=random.randint(0, 450),
            hours=random.randint(8, 18),
            minutes=random.randint(0, 59)
        )
        loc = random.choice(LOCATIONS)
        ttype = random.choice(TRANSACTION_TYPES)
        # Most have approval
        has_approval = random.random() > 0.08
        approver = random.choice(emp_ids) if has_approval else None
        if approver == emp:
            approver = random.choice([e for e in emp_ids if e != emp])

        records.append({
            "transaction_id": f"TXN{i+1:07d}",
            "employee_id": emp,
            "department": emp_info["department"],
            "amount": amount,
            "timestamp": ts,
            "location": loc,
            "transaction_type": ttype,
            "approval_status": "Approved" if has_approval else "Pending",
            "approver_id": approver,
            "user_role": emp_info["user_role"],
            "access_level": emp_info["access_level"],
            "device_id": f"DEV{random.randint(1000, 9999)}",
            "is_injected_issue": False,
            "injected_issue_type": None
        })

    df = pd.DataFrame(records)

    # ---- Inject control violations & anomalies (~8-12% of data) ----
    inject_count = int(n * 0.10)
    inject_indices = np.random.choice(df.index, size=inject_count, replace=False)

    issue_types = [
        "missing_approval", "unauthorized_approval", "self_approval",
        "duplicate", "inactive_user", "privilege_violation",
        "unusual_amount", "after_hours", "unusual_location", "sod_violation"
    ]

    for idx in inject_indices:
        issue = random.choice(issue_types)
        df.at[idx, "is_injected_issue"] = True
        df.at[idx, "injected_issue_type"] = issue

        if issue == "missing_approval":
            df.at[idx, "approval_status"] = "Pending"
            df.at[idx, "approver_id"] = None
            df.at[idx, "amount"] = max(df.at[idx, "amount"], random.uniform(8000, 45000))

        elif issue == "unauthorized_approval":
            # Approver is a low-privilege employee
            low_priv = employees_df[employees_df["access_level"].isin(["Standard", "ReadOnly"])]["employee_id"].tolist()
            if low_priv:
                df.at[idx, "approver_id"] = random.choice(low_priv)
            df.at[idx, "approval_status"] = "Approved"
            df.at[idx, "amount"] = max(df.at[idx, "amount"], 5000)

        elif issue == "self_approval":
            df.at[idx, "approver_id"] = df.at[idx, "employee_id"]
            df.at[idx, "approval_status"] = "Approved"

        elif issue == "duplicate":
            # Will create actual duplicate rows later
            pass

        elif issue == "inactive_user":
            inactive = employees_df[~employees_df["is_active"]]["employee_id"].tolist()
            if inactive:
                df.at[idx, "employee_id"] = random.choice(inactive)
                info = emp_lookup.get(df.at[idx, "employee_id"], emp_info)
                df.at[idx, "department"] = info.get("department", df.at[idx, "department"])
                df.at[idx, "user_role"] = info.get("user_role", df.at[idx, "user_role"])
                df.at[idx, "access_level"] = info.get("access_level", df.at[idx, "access_level"])

        elif issue == "privilege_violation":
            # Clerk/Analyst doing high-value or admin action
            df.at[idx, "user_role"] = random.choice(["Clerk", "Analyst"])
            df.at[idx, "access_level"] = "Standard"
            df.at[idx, "amount"] = random.uniform(25000, 80000)
            df.at[idx, "transaction_type"] = "Asset Purchase"

        elif issue == "unusual_amount":
            df.at[idx, "amount"] = round(random.uniform(75000, 250000), 2)

        elif issue == "after_hours":
            base = df.at[idx, "timestamp"]
            if isinstance(base, str):
                base = pd.to_datetime(base)
            df.at[idx, "timestamp"] = base.replace(hour=random.choice([0, 1, 2, 3, 22, 23]), minute=random.randint(0, 59))

        elif issue == "unusual_location":
            df.at[idx, "location"] = random.choice(["Unknown", "Offshore", "Sanctioned Zone"])

        elif issue == "sod_violation":
            # Same person creates and approves
            df.at[idx, "approver_id"] = df.at[idx, "employee_id"]
            df.at[idx, "approval_status"] = "Approved"
            df.at[idx, "transaction_type"] = "Payment"

    # Create actual duplicate transactions
    dup_indices = df[df["injected_issue_type"] == "duplicate"].index.tolist()
    extra_dups = []
    for idx in dup_indices[:min(400, len(dup_indices))]:
        row = df.loc[idx].copy()
        row["transaction_id"] = f"TXN{len(df) + len(extra_dups) + 1:07d}"
        # Same amount, employee, close timestamp, same type
        row["timestamp"] = row["timestamp"] + timedelta(minutes=random.randint(1, 30))
        row["is_injected_issue"] = True
        row["injected_issue_type"] = "duplicate"
        extra_dups.append(row)
    if extra_dups:
        df = pd.concat([df, pd.DataFrame(extra_dups)], ignore_index=True)

    # Ensure timestamps are datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Re-number transaction_ids cleanly
    df["transaction_id"] = [f"TXN{i+1:07d}" for i in range(len(df))]

    return df

def main():
    print("Generating employees...")
    employees = generate_employees()
    employees_path = os.path.join(OUTPUT_DIR, "employees.csv")
    employees.to_csv(employees_path, index=False)
    print(f"  Saved {len(employees)} employees -> {employees_path}")

    print("Generating transactions (this may take a moment)...")
    transactions = generate_transactions(employees)
    tx_path = os.path.join(OUTPUT_DIR, "transactions.csv")
    transactions.to_csv(tx_path, index=False)
    print(f"  Saved {len(transactions)} transactions -> {tx_path}")

    # Summary of injected issues
    print("\nInjected issue distribution:")
    print(transactions["injected_issue_type"].value_counts(dropna=False).to_string())

    # Also save a smaller sample for quick tests
    sample = transactions.sample(n=min(5000, len(transactions)), random_state=42)
    sample.to_csv(os.path.join(OUTPUT_DIR, "transactions_sample.csv"), index=False)
    print(f"\nSample (5k) saved for quick testing.")

    print("\nDone. Synthetic data ready.")

if __name__ == "__main__":
    main()
