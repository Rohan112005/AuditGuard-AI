"""
AuditGuard AI - Full Pipeline Runner
Executes steps 1-11 in recommended build order.
"""

import subprocess
import sys
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

STEPS = [
    ("1. ETL clean & validate", "etl/clean_and_validate.py"),
    ("2. Database schema & load", "database/schema_and_load.py"),
    ("3. Control tests", "controls/control_tests.py"),
    ("4. Anomaly detection", "anomaly_detection/anomaly_engine.py"),
    ("5. Risk scoring", "risk_engine/risk_scoring.py"),
    ("6. AI audit summary", "ai_assistant/audit_summary.py"),
    ("7. Dashboard charts (Power BI pages)", "dashboard/create_charts.py"),
    ("8. PDF audit report", "reports/generate_pdf_report.py"),
]

def run(label, script):
    path = os.path.join(BASE, script)
    print("\n" + "=" * 60)
    print(f"▶ {label}")
    print("=" * 60)
    t0 = time.time()
    result = subprocess.run([PY, path], cwd=BASE)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"✗ FAILED ({elapsed:.1f}s) – aborting")
        sys.exit(result.returncode)
    print(f"✓ Completed in {elapsed:.1f}s")
    return elapsed

def main():
    print("AuditGuard AI – End-to-End Pipeline")
    print(f"Working directory: {BASE}")
    # Ensure data exists
    data_path = os.path.join(BASE, "data", "transactions.csv")
    if not os.path.exists(data_path):
        print("Synthetic data missing – generating...")
        run("0. Generate synthetic data", "data/generate_synthetic_data.py")

    times = {}
    for label, script in STEPS:
        times[label] = run(label, script)

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    for k, v in times.items():
        print(f"  {k}: {v:.1f}s")
    print(f"\nDatabase: {os.path.join(BASE, 'database', 'auditguard.db')}")
    print(f"PDF Report: {os.path.join(BASE, 'reports', 'AuditGuard_AI_Audit_Report.pdf')}")
    print(f"Charts: {os.path.join(BASE, 'dashboard', 'charts')}")
    print("\nTo launch investigation UI:")
    print(f"  streamlit run {os.path.join(BASE, 'dashboard', 'streamlit_app.py')}")

if __name__ == "__main__":
    main()
