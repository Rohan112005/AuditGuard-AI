"""
AuditGuard AI - Streamlit Investigation Interface
Run: streamlit run dashboard/streamlit_app.py
"""

import streamlit as st
import sqlite3
import pandas as pd
import os
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"
CHART_DIR = os.path.join(BASE, "dashboard", "charts")

st.set_page_config(page_title="AuditGuard AI", page_icon="🛡️", layout="wide")

@st.cache_resource
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def main():
    st.title("🛡️ AuditGuard AI")
    st.caption("IT Controls, Risk & Data Analytics Platform – Investigation Interface")

    if not os.path.exists(DB_PATH):
        st.error("Database not found. Please run the full pipeline first.")
        return

    conn = get_conn()
    tabs = st.tabs(["Executive Overview", "Control Testing", "Investigation", "AI Summary"])

    # ---- Tab 1 ----
    with tabs[0]:
        c1, c2, c3, c4 = st.columns(4)
        total = pd.read_sql("SELECT COUNT(*) as n FROM transactions", conn).iloc[0, 0]
        findings = pd.read_sql("SELECT COUNT(*) as n FROM findings WHERE risk_score>0", conn).iloc[0, 0]
        critical = pd.read_sql("SELECT COUNT(*) as n FROM findings WHERE risk_level='Critical'", conn).iloc[0, 0]
        high = pd.read_sql("SELECT COUNT(*) as n FROM findings WHERE risk_level='High'", conn).iloc[0, 0]
        c1.metric("Total Transactions", f"{total:,}")
        c2.metric("Findings", f"{findings:,}")
        c3.metric("Critical", f"{critical:,}")
        c4.metric("High", f"{high:,}")

        img = os.path.join(CHART_DIR, "page1_executive_overview.png")
        if os.path.exists(img):
            st.image(img, use_container_width=True)
        else:
            st.info("Run dashboard/create_charts.py to generate overview charts.")

    # ---- Tab 2 ----
    with tabs[1]:
        st.subheader("Control Failures")
        controls = pd.read_sql("""
            SELECT control_name as Control, COUNT(*) as Violations
            FROM control_results WHERE is_violation=1
            GROUP BY control_name ORDER BY Violations DESC
        """, conn)
        st.dataframe(controls, use_container_width=True)
        img = os.path.join(CHART_DIR, "page2_control_testing.png")
        if os.path.exists(img):
            st.image(img, use_container_width=True)

    # ---- Tab 3 ----
    with tabs[2]:
        st.subheader("Investigation Workbench")
        min_score = st.slider("Minimum risk score", 0, 100, 55)
        level_filter = st.multiselect(
            "Risk levels", ["Critical", "High", "Medium", "Low"],
            default=["Critical", "High"]
        )
        q = f"""
            SELECT transaction_id, employee_id, amount, risk_score, risk_level,
                   control_violated, issue_summary, investigation_status
            FROM findings
            WHERE risk_score >= {min_score}
        """
        if level_filter:
            levels = ",".join(f"'{l}'" for l in level_filter)
            q += f" AND risk_level IN ({levels})"
        q += " ORDER BY risk_score DESC LIMIT 500"
        inv = pd.read_sql(q, conn)
        st.dataframe(inv, use_container_width=True, height=400)
        st.download_button("Download CSV", inv.to_csv(index=False), "investigation_export.csv")

        img = os.path.join(CHART_DIR, "page3_investigation.png")
        if os.path.exists(img):
            st.image(img, use_container_width=True)

    # ---- Tab 4 ----
    with tabs[3]:
        st.subheader("Evidence-Based AI Audit Summary")
        path = os.path.join(BASE, "ai_assistant", "ai_audit_summary.txt")
        if os.path.exists(path):
            with open(path) as f:
                st.text(f.read())
        else:
            st.info("Run ai_assistant/audit_summary.py first.")

if __name__ == "__main__":
    main()
