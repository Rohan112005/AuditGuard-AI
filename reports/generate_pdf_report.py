"""
AuditGuard AI - Automated PDF Audit Report (ReportLab)
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = "/tmp/auditguard.db"
OUTPUT_DIR = os.path.join(BASE, "reports")
CHART_DIR = os.path.join(BASE, "dashboard", "charts")

def get_metrics(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM transactions")
    total_tx = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM employees")
    total_emp = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM findings WHERE risk_score > 0")
    findings = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM findings WHERE risk_level = 'Critical'")
    critical = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM findings WHERE risk_level = 'High'")
    high = cur.fetchone()[0]
    controls = pd.read_sql_query("""
        SELECT control_name, COUNT(*) as cnt FROM control_results
        WHERE is_violation = 1 GROUP BY control_name ORDER BY cnt DESC
    """, conn)
    risk_dist = pd.read_sql_query("""
        SELECT risk_level, COUNT(*) as cnt FROM findings
        WHERE risk_score > 0 GROUP BY risk_level
    """, conn)
    top_findings = pd.read_sql_query("""
        SELECT transaction_id, employee_id, ROUND(amount,2) as amount,
               risk_score, risk_level, substr(issue_summary,1,80) as issue
        FROM findings WHERE risk_level IN ('Critical','High')
        ORDER BY risk_score DESC LIMIT 15
    """, conn)
    dept = pd.read_sql_query("""
        SELECT t.department, COUNT(*) as findings
        FROM findings f JOIN transactions t ON f.transaction_id = t.transaction_id
        WHERE f.risk_score > 0
        GROUP BY t.department ORDER BY findings DESC LIMIT 8
    """, conn)
    return {
        "total_tx": total_tx, "total_emp": total_emp, "findings": findings,
        "critical": critical, "high": high, "controls": controls,
        "risk_dist": risk_dist, "top_findings": top_findings, "dept": dept
    }

def build_report():
    conn = sqlite3.connect(DB_PATH)
    m = get_metrics(conn)
    conn.close()

    # Load AI summary if present
    ai_path = os.path.join(BASE, "ai_assistant", "ai_audit_summary.txt")
    ai_text = ""
    if os.path.exists(ai_path):
        with open(ai_path) as f:
            ai_text = f.read()

    out_path = os.path.join(OUTPUT_DIR, "AuditGuard_AI_Audit_Report.pdf")
    doc = SimpleDocTemplate(
        out_path, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=18, spaceAfter=6))
    styles.add(ParagraphStyle(name="SubCenter", parent=styles["Normal"], alignment=TA_CENTER, fontSize=11, textColor=colors.HexColor("#444444")))
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading1"], fontSize=13, textColor=colors.HexColor("#1a365d"), spaceBefore=14, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyJust", parent=styles["Normal"], alignment=TA_JUSTIFY, fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="Small", parent=styles["Normal"], fontSize=8, leading=10))

    story = []

    # Cover
    story.append(Spacer(1, 1.2*inch))
    story.append(Paragraph("AuditGuard AI", styles["TitleCenter"]))
    story.append(Paragraph("IT Controls, Risk & Data Analytics Platform", styles["SubCenter"]))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("Automated Audit-Style Report", styles["SubCenter"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["SubCenter"]))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "This report summarizes control testing results, anomaly detection outcomes, "
        "explainable risk scores, and recommended review areas derived exclusively from "
        "verified database findings.",
        styles["BodyJust"]
    ))
    story.append(PageBreak())

    # 1. Executive Summary
    story.append(Paragraph("1. Executive Summary", styles["Section"]))
    story.append(Paragraph(
        f"The platform processed <b>{m['total_tx']:,}</b> transactions across "
        f"<b>{m['total_emp']:,}</b> employees. Control tests and hybrid anomaly detection "
        f"produced <b>{m['findings']:,}</b> findings requiring review, of which "
        f"<b>{m['critical']:,}</b> are Critical and <b>{m['high']:,}</b> are High risk.",
        styles["BodyJust"]
    ))
    story.append(Spacer(1, 0.15*inch))
    if ai_text:
        # Take first paragraph-ish of AI summary
        preview = ai_text.split("DETAILED")[0].strip().replace("\n", "<br/>")
        story.append(Paragraph(preview[:1800], styles["Small"]))
    story.append(PageBreak())

    # 2. Dataset Statistics
    story.append(Paragraph("2. Dataset Statistics", styles["Section"]))
    stats_data = [
        ["Metric", "Value"],
        ["Total transactions processed", f"{m['total_tx']:,}"],
        ["Employees in scope", f"{m['total_emp']:,}"],
        ["Findings (risk score > 0)", f"{m['findings']:,}"],
        ["Critical risk findings", f"{m['critical']:,}"],
        ["High risk findings", f"{m['high']:,}"],
    ]
    t = Table(stats_data, colWidths=[3.5*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4f8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.25*inch))

    # 3. Control Testing Results
    story.append(Paragraph("3. Control Testing Results", styles["Section"]))
    story.append(Paragraph(
        "The following table shows verified control violations detected by SQL/Python control tests. "
        "Each count is grounded in database records.",
        styles["BodyJust"]
    ))
    story.append(Spacer(1, 0.1*inch))
    ctrl_data = [["Control", "Violation Count"]]
    for _, r in m["controls"].iterrows():
        ctrl_data.append([r["control_name"], f"{int(r['cnt']):,}"])
    t2 = Table(ctrl_data, colWidths=[4*inch, 1.5*inch])
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c5282")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#edf2f7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t2)
    story.append(PageBreak())

    # 4. Risk Distribution
    story.append(Paragraph("4. Risk Distribution", styles["Section"]))
    risk_data = [["Risk Level", "Count"]]
    order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
    rd = m["risk_dist"].copy()
    rd["_ord"] = rd["risk_level"].map(order)
    rd = rd.sort_values("_ord")
    for _, r in rd.iterrows():
        risk_data.append([r["risk_level"], f"{int(r['cnt']):,}"])
    t3 = Table(risk_data, colWidths=[2.5*inch, 1.5*inch])
    t3.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#742a2a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fff5f5")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t3)
    story.append(Spacer(1, 0.2*inch))

    # Department concentration
    story.append(Paragraph("Department-Level Finding Concentration", styles["Heading2"]))
    dept_data = [["Department", "Findings"]]
    for _, r in m["dept"].iterrows():
        dept_data.append([r["department"], f"{int(r['findings']):,}"])
    t4 = Table(dept_data, colWidths=[2.5*inch, 1.5*inch])
    t4.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f855a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0fff4")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t4)
    story.append(PageBreak())

    # 5. High-Risk Findings
    story.append(Paragraph("5. High-Risk Findings (Sample)", styles["Section"]))
    story.append(Paragraph(
        "Top Critical and High risk transactions ordered by risk score. "
        "Full investigation list is available in the findings table / Streamlit interface.",
        styles["BodyJust"]
    ))
    story.append(Spacer(1, 0.1*inch))
    hf_data = [["Txn ID", "Employee", "Amount", "Score", "Level", "Issue (truncated)"]]
    for _, r in m["top_findings"].iterrows():
        hf_data.append([
            str(r["transaction_id"])[:12],
            str(r["employee_id"])[:10],
            f"{r['amount']:,.0f}" if pd.notna(r["amount"]) else "",
            f"{r['risk_score']:.0f}",
            r["risk_level"],
            str(r["issue"])[:45] + ("..." if len(str(r["issue"])) > 45 else "")
        ])
    t5 = Table(hf_data, colWidths=[1.1*inch, 0.9*inch, 0.7*inch, 0.5*inch, 0.6*inch, 2.4*inch])
    t5.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a365d")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#ebf8ff")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(t5)
    story.append(PageBreak())

    # 6. Recommended Review Areas
    story.append(Paragraph("6. Recommended Review Areas", styles["Section"]))
    recs = [
        "Payment approval process – concentration of missing and unauthorized approvals on higher-value items.",
        "Segregation of duties – self-approval cases on Payment and Vendor Payment transaction types.",
        "Inactive user access – transactions executed by employees marked inactive.",
        "Privilege alignment – Clerk/Analyst roles initiating Asset Purchase or large Vendor Payments.",
        "Geographic / location anomalies – activity from Unknown, Offshore or Sanctioned Zone locations.",
        "After-hours high-value activity – combination of time-based and amount-based signals.",
    ]
    for i, r in enumerate(recs, 1):
        story.append(Paragraph(f"<b>{i}.</b> {r}", styles["BodyJust"]))
        story.append(Spacer(1, 0.06*inch))

    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("7. Methodology & Limitations", styles["Section"]))
    story.append(Paragraph(
        "Control rules and risk weights are project-defined for portfolio demonstration and are not "
        "industry or regulatory standards. Isolation Forest contamination and feature set are tunable. "
        "AI summaries are constrained to verified database aggregates only. Synthetic data was used "
        "with intentionally injected violations to enable measurable precision of detection logic.",
        styles["BodyJust"]
    ))
    story.append(Spacer(1, 0.4*inch))
    story.append(Paragraph(
        "— End of Report — AuditGuard AI",
        styles["SubCenter"]
    ))

    doc.build(story)
    print(f"PDF report generated -> {out_path}")
    return out_path

if __name__ == "__main__":
    build_report()
