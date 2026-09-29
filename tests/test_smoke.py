"""Smoke tests for AuditGuard AI core modules."""
import os
import sys
import sqlite3

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

DB_CANDIDATES = [
    os.path.join(BASE, "database", "auditguard.db"),
    "/tmp/auditguard.db",
]

def test_data_files_exist():
    assert os.path.exists(os.path.join(BASE, "data", "transactions.csv"))
    assert os.path.exists(os.path.join(BASE, "data", "employees.csv"))

def test_database_has_tables():
    path = next((p for p in DB_CANDIDATES if os.path.exists(p)), None)
    assert path is not None, "Database not found"
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ["employees", "transactions", "controls_catalog", "control_results", "findings"]:
        assert t in tables, f"Missing table {t}"
    n = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
    assert n > 1000
    conn.close()

def test_findings_have_risk_levels():
    path = next((p for p in DB_CANDIDATES if os.path.exists(p)), None)
    conn = sqlite3.connect(path)
    levels = {r[0] for r in conn.execute("SELECT DISTINCT risk_level FROM findings")}
    assert "Critical" in levels or "High" in levels
    conn.close()

def test_charts_exist():
    chart_dir = os.path.join(BASE, "dashboard", "charts")
    for name in ["page1_executive_overview.png", "page2_control_testing.png", "page3_investigation.png"]:
        assert os.path.exists(os.path.join(chart_dir, name)), f"Missing chart {name}"

def test_pdf_exists():
    assert os.path.exists(os.path.join(BASE, "reports", "AuditGuard_AI_Audit_Report.pdf"))

if __name__ == "__main__":
    test_data_files_exist()
    print("✓ data files")
    test_database_has_tables()
    print("✓ database tables")
    test_findings_have_risk_levels()
    print("✓ findings risk levels")
    test_charts_exist()
    print("✓ charts")
    test_pdf_exists()
    print("✓ PDF report")
    print("\nAll smoke tests passed.")
