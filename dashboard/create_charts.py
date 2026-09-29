"""
AuditGuard AI - Dashboard Charts
Replicates the three Power BI pages described in the project guide:
  Page 1 – Executive Risk Overview
  Page 2 – Control Testing
  Page 3 – Investigation-ready tables (exported)
Uses matplotlib + plotly for static + interactive outputs.
"""

import sqlite3
import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"
CHART_DIR = os.path.join(BASE, "dashboard", "charts")
os.makedirs(CHART_DIR, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#cbd5e0",
    "axes.labelcolor": "#2d3748",
    "xtick.color": "#4a5568",
    "ytick.color": "#4a5568",
    "font.size": 9,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
})

def load(conn):
    metrics = {}
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transactions")
    metrics["total_tx"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM findings WHERE risk_score > 0")
    metrics["findings"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM findings WHERE risk_level='Critical'")
    metrics["critical"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM control_results WHERE is_violation=1")
    metrics["control_violations"] = cur.fetchone()[0]

    risk_dist = pd.read_sql_query("""
        SELECT risk_level, COUNT(*) as cnt FROM findings
        WHERE risk_score > 0 GROUP BY risk_level
    """, conn)
    controls = pd.read_sql_query("""
        SELECT control_name, COUNT(*) as cnt FROM control_results
        WHERE is_violation=1 GROUP BY control_name ORDER BY cnt DESC
    """, conn)
    # Monthly trend
    monthly = pd.read_sql_query("""
        SELECT strftime('%Y-%m', t.timestamp) as month,
               COUNT(DISTINCT f.transaction_id) as findings
        FROM findings f
        JOIN transactions t ON f.transaction_id = t.transaction_id
        WHERE f.risk_score > 0
        GROUP BY month ORDER BY month
    """, conn)
    dept = pd.read_sql_query("""
        SELECT t.department, COUNT(*) as findings
        FROM findings f JOIN transactions t ON f.transaction_id = t.transaction_id
        WHERE f.risk_score > 0
        GROUP BY t.department ORDER BY findings DESC
    """, conn)
    inv = pd.read_sql_query("""
        SELECT f.transaction_id, f.employee_id, ROUND(f.amount,2) as amount,
               f.issue_summary, f.risk_score, f.risk_level,
               f.control_violated, f.investigation_status
        FROM findings f
        WHERE f.risk_score >= 55
        ORDER BY f.risk_score DESC LIMIT 200
    """, conn)
    return metrics, risk_dist, controls, monthly, dept, inv

def page1_executive(metrics, risk_dist, monthly, dept):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("Page 1 – Executive Risk Overview", fontsize=14, fontweight="bold", color="#1a365d")

    # KPI cards via text
    ax = axes[0, 0]
    ax.axis("off")
    kpis = [
        ("Total Transactions", f"{metrics['total_tx']:,}"),
        ("Findings", f"{metrics['findings']:,}"),
        ("Control Violations", f"{metrics['control_violations']:,}"),
        ("Critical Cases", f"{metrics['critical']:,}"),
    ]
    y = 0.85
    for label, val in kpis:
        ax.text(0.05, y, label, fontsize=10, color="#718096")
        ax.text(0.05, y - 0.12, val, fontsize=18, fontweight="bold", color="#1a365d")
        y -= 0.25
    ax.set_title("Key Metrics")

    # Risk distribution pie
    ax = axes[0, 1]
    order = ["Critical", "High", "Medium", "Low"]
    colors_map = {"Critical": "#c53030", "High": "#dd6b20", "Medium": "#d69e2e", "Low": "#38a169"}
    rd = risk_dist.set_index("risk_level").reindex(order).dropna()
    if len(rd) > 0:
        wedges, texts, autotexts = ax.pie(
            rd["cnt"], labels=rd.index, autopct="%1.1f%%",
            colors=[colors_map.get(i, "#a0aec0") for i in rd.index],
            startangle=90, textprops={"fontsize": 8}
        )
        for at in autotexts:
            at.set_fontsize(8)
    ax.set_title("Risk Distribution")

    # Monthly trend
    ax = axes[1, 0]
    if len(monthly) > 0:
        ax.plot(monthly["month"], monthly["findings"], marker="o", color="#2b6cb0", linewidth=2)
        ax.fill_between(monthly["month"], monthly["findings"], alpha=0.15, color="#2b6cb0")
        ax.set_xticks(range(0, len(monthly), max(1, len(monthly)//6)))
        ax.set_xticklabels(monthly["month"].iloc[::max(1, len(monthly)//6)], rotation=45, ha="right", fontsize=7)
    ax.set_title("Monthly Finding Trend")
    ax.set_ylabel("Findings")
    ax.grid(True, alpha=0.3)

    # Department bar
    ax = axes[1, 1]
    d = dept.head(8)
    if len(d) > 0:
        bars = ax.barh(d["department"][::-1], d["findings"][::-1], color="#2c5282")
        ax.set_xlabel("Findings")
    ax.set_title("Findings by Department")
    ax.grid(True, axis="x", alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    path = os.path.join(CHART_DIR, "page1_executive_overview.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")
    return path

def page2_control_testing(controls, dept):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.suptitle("Page 2 – Control Testing", fontsize=14, fontweight="bold", color="#1a365d")

    ax = axes[0]
    c = controls.head(9)
    if len(c) > 0:
        colors = plt.cm.Reds(np.linspace(0.35, 0.85, len(c)))[::-1]
        ax.barh(c["control_name"][::-1], c["cnt"][::-1], color=colors)
        ax.set_xlabel("Violation Count")
    ax.set_title("Control Failures by Type")
    ax.grid(True, axis="x", alpha=0.3)

    ax = axes[1]
    # Department failure rates (using findings as proxy)
    d = dept.head(8)
    if len(d) > 0:
        ax.bar(range(len(d)), d["findings"], color="#c53030", alpha=0.85)
        ax.set_xticks(range(len(d)))
        ax.set_xticklabels(d["department"], rotation=45, ha="right", fontsize=8)
        ax.set_ylabel("Findings")
    ax.set_title("Department-Level Failure Concentration")
    ax.grid(True, axis="y", alpha=0.3)

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    path = os.path.join(CHART_DIR, "page2_control_testing.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")
    return path

def page3_investigation(inv):
    # Export investigation table
    path_csv = os.path.join(CHART_DIR, "page3_investigation_table.csv")
    inv.to_csv(path_csv, index=False)
    print(f"  Saved {path_csv}")

    # Simple visual of top risk scores
    fig, ax = plt.subplots(figsize=(10, 5))
    top = inv.head(25)
    if len(top) > 0:
        colors = ["#c53030" if r == "Critical" else "#dd6b20" for r in top["risk_level"]]
        ax.barh(range(len(top)), top["risk_score"][::-1], color=colors[::-1])
        ax.set_yticks(range(len(top)))
        labels = [f"{t} ({e})" for t, e in zip(top["transaction_id"].str[:10], top["employee_id"].str[:8])]
        ax.set_yticklabels(labels[::-1], fontsize=7)
        ax.set_xlabel("Risk Score")
        ax.set_title("Page 3 – Investigation: Top High/Critical Transactions by Risk Score")
        ax.axvline(75, color="#c53030", linestyle="--", alpha=0.6, label="Critical threshold")
        ax.axvline(55, color="#dd6b20", linestyle="--", alpha=0.6, label="High threshold")
        ax.legend(fontsize=8)
        ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(CHART_DIR, "page3_investigation.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {path}")
    return path, path_csv

def main():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError("Run full pipeline first.")
    conn = sqlite3.connect(DB_PATH)
    print("Building dashboard charts (Power BI equivalent pages)...")
    metrics, risk_dist, controls, monthly, dept, inv = load(conn)
    page1_executive(metrics, risk_dist, monthly, dept)
    page2_control_testing(controls, dept)
    page3_investigation(inv)
    conn.close()
    print("Dashboard charts complete.")

if __name__ == "__main__":
    main()
