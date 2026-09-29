# AuditGuard AI – IT Controls, Risk & Data Analytics Platform

End-to-end platform that processes enterprise transaction data, tests IT application controls, detects anomalies (rule-based + Isolation Forest), calculates explainable risk scores, visualizes findings, and generates an audit-style PDF report.

Designed around the Deloitte Assurance – IT Data & Analytics skill set: large-dataset analysis, control gaps, anomaly detection, risk prioritization, dashboards, and evidence-based AI summaries.

## Architecture

```
Raw Enterprise Data → Python ETL → SQLite (PostgreSQL-compatible schema)
  → Control Testing → Anomaly Detection → Risk Scoring
  → Dashboard Charts / Streamlit → AI Audit Summary → PDF Report
```

## Project Structure

```
AuditGuard-AI/
├── data/                     # Synthetic generator + CSVs
├── etl/                      # Clean & validate
├── database/                 # Schema, load, auditguard.db
├── controls/                 # SQL/Python control tests
├── anomaly_detection/        # Rules + Isolation Forest
├── risk_engine/              # Explainable 0–100 scoring
├── ai_assistant/             # Evidence-based summaries only
├── dashboard/                # Charts (Power BI pages) + Streamlit app
├── reports/                  # PDF audit report
├── tests/
├── run_pipeline.py           # One-command full run
├── requirements.txt
└── README.md
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate data (already done if you ran the full pipeline once)
python data/generate_synthetic_data.py

# 3. Run everything end-to-end
python run_pipeline.py

# 4. (Optional) Investigation UI
streamlit run dashboard/streamlit_app.py
```

## Control Checks Implemented

| ID  | Control                         | Category              |
|-----|---------------------------------|-----------------------|
| C01 | Missing Approval                | Approval              |
| C02 | Unauthorized Approval           | Approval              |
| C03 | Self Approval / SoD             | Segregation of Duties |
| C04 | Duplicate Transaction           | Transaction Integrity |
| C05 | Inactive User Activity          | Access Control        |
| C06 | Privilege Violation             | Privilege / Access    |
| C07 | Unusual Amount                  | Transaction Control   |
| C08 | After-Hours Activity            | Transaction Control   |
| C09 | Unusual Location                | Transaction Control   |

## Anomaly Detection

- **Rule-based**: high-value, after-hours, missing approval, self-approval, unusual location (fully transparent).
- **Isolation Forest**: amount, hour, day-of-week, location/type/role/department encodings. Contamination ≈ 4%.

Both signals feed the risk engine so every flag remains explainable.

## Explainable Risk Score (Project Rules)

| Signal                    | Points |
|---------------------------|--------|
| Any control failure       | +30    |
| Anomaly (rule or IF)      | +25    |
| Missing approval          | +25    |
| Self-approval / SoD       | +15    |
| Inactive user             | +20    |
| Privilege violation       | +15    |
| Unusual location          | +10    |
| High-value (≥ 50k)        | +10    |

Score clipped to 0–100.  
**Thresholds**: Low < 30 · Medium 30–54 · High 55–74 · Critical ≥ 75.

> These weights are **project-defined** for demonstration, not industry or regulatory standards.

## Dashboard (Power BI Requirements Mapped)

| Guide Page | Content | Deliverable |
|------------|---------|-------------|
| Page 1 – Executive Risk Overview | Total tx, anomalies, control failures, high-risk cases, risk distribution, monthly trend | `dashboard/charts/page1_executive_overview.png` + Streamlit metrics |
| Page 2 – Control Testing | Approval / access / duplicate / SoD failures, department-level rates | `dashboard/charts/page2_control_testing.png` |
| Page 3 – Investigation | Txn ID, employee, amount, issue, risk score, control violated, status | `page3_investigation.png` + CSV + Streamlit workbench |

Charts are generated with matplotlib so the project is fully self-contained. The same data can be connected to Power BI Desktop via the SQLite DB or exported CSVs.

## AI Audit Assistant

Summaries are produced **only** from verified aggregates in the `findings` and `control_results` tables. No invented evidence.

## PDF Report Sections

1. Executive Summary  
2. Dataset Statistics  
3. Control Testing Results  
4. Risk Distribution & Department Concentration  
5. High-Risk Findings (sample)  
6. Recommended Review Areas  
7. Methodology & Limitations  

Output: `reports/AuditGuard_AI_Audit_Report.pdf`

## Technology Stack

- **Python**: Pandas, NumPy, Scikit-learn  
- **Database**: SQLite (schema is PostgreSQL-compatible; swap connection string for production)  
- **Analytics / Viz**: matplotlib, Streamlit (Power BI-ready exports)  
- **Reporting**: ReportLab  
- **Dev**: Git-ready folder layout  

## Measured Metrics (populate after your run)

Record the real numbers produced by your execution:

- Records processed  
- Control violation counts by type  
- Rule vs Isolation Forest anomaly counts  
- Findings by risk level  
- Pipeline wall-clock time  
- PDF / chart generation time  

Never put example numbers on a resume—use the values from `risk_engine/metrics.json` after a successful run.

## Interview Talk-Track

> “AuditGuard AI is a data analytics and IT controls platform. I clean enterprise transaction data with Python and load it into a relational store. I then run SQL/Python control tests for approval, access, duplicate, and segregation-of-duties issues. I combine those controls with Isolation Forest for anomaly detection. Each finding receives an explainable risk score. Dashboards visualize the results, an evidence-based AI component summarizes verified findings, and a reporting module produces the final audit PDF.”

## Important Notes

- Build and test every component before listing it.  
- Clearly document which rules are project design, which algorithms come from standard libraries, and that AI text is grounded in database findings only.  
- Synthetic data contains intentionally injected violations so detection logic can be validated.
