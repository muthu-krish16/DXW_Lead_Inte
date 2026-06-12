import sqlite3
import json
from datetime import datetime, timezone

DB_NAME = "lead_intelligence.db"


def create_tables():
    """
    Create all required tables. Drops and recreates if schema changed.
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Drop old tables to avoid schema mismatch
    cursor.execute("DROP TABLE IF EXISTS contacts")
    cursor.execute("DROP TABLE IF EXISTS reports")

    # Main reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id                                      INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at                              TEXT,
            company_name                            TEXT,
            industry                                TEXT,
            employee_size                           TEXT,
            revenue                                 TEXT,
            location                                TEXT,
            account_tier                            TEXT,
            final_score                             REAL,
            dxw_fitment_score                       REAL,
            strategic_account_potential_score       REAL,
            data_governance_complexity_score        REAL,
            analytics_fragmentation_risk_score      REAL,
            ai_data_readiness_score                 REAL,
            enterprise_reporting_scalability_score  REAL,
            operational_visibility_risk_score       REAL,
            executive_summary                       TEXT,
            next_step_strategy                      TEXT,
            recommended_outreach_angle              TEXT,
            full_report_json                        TEXT
        )
    """)

    # Contacts table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id    INTEGER,
            company_name TEXT,
            name         TEXT,
            title        TEXT,
            email        TEXT,
            FOREIGN KEY (report_id) REFERENCES reports(id)
        )
    """)

    conn.commit()
    conn.close()


def safe_score(data, key):
    val = data.get("strategic_scoring_framework", {}).get(key, {})
    if isinstance(val, dict):
        raw = val.get("score", 0)
    else:
        raw = val
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def save_report(ai_result, final_score, company_info, contacts):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        summary_block  = ai_result.get("executive_summary", {})
        scoring_block  = ai_result.get("strategic_scoring_framework", {})
        outreach_block = ai_result.get("outreach_intelligence_strategy", {})

        company_name   = company_info.get("company_name", "Unknown")
        industry       = company_info.get("industry", "")
        employee_size  = company_info.get("employee_size", "")
        revenue        = company_info.get("revenue", "")
        location       = ", ".join(filter(None, [
            company_info.get("city", ""),
            company_info.get("state", ""),
            company_info.get("country", "")
        ]))

        cursor.execute("""
            INSERT INTO reports (
                created_at, company_name, industry, employee_size, revenue,
                location, account_tier, final_score,
                dxw_fitment_score, strategic_account_potential_score,
                data_governance_complexity_score, analytics_fragmentation_risk_score,
                ai_data_readiness_score, enterprise_reporting_scalability_score,
                operational_visibility_risk_score, executive_summary,
                next_step_strategy, recommended_outreach_angle, full_report_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            company_name,
            industry,
            employee_size,
            revenue,
            location,
            scoring_block.get("account_tier", "Unknown"),
            float(final_score),
            safe_score(ai_result, "dxw_fitment_score"),
            safe_score(ai_result, "strategic_account_potential_score"),
            safe_score(ai_result, "data_governance_complexity_score"),
            safe_score(ai_result, "analytics_fragmentation_risk_score"),
            safe_score(ai_result, "ai_data_readiness_score"),
            safe_score(ai_result, "enterprise_reporting_scalability_score"),
            safe_score(ai_result, "operational_visibility_risk_score"),
            summary_block.get("key_findings", ""),
            scoring_block.get("next_step_strategy", ""),
            outreach_block.get("recommended_angle", ""),
            json.dumps(ai_result, ensure_ascii=False)
        ))

        report_id = cursor.lastrowid

        for contact in contacts:
            cursor.execute("""
                INSERT INTO contacts (report_id, company_name, name, title, email)
                VALUES (?, ?, ?, ?, ?)
            """, (
                report_id,
                company_name,
                contact.get("name", ""),
                contact.get("title", ""),
                contact.get("email", "")
            ))

        conn.commit()
        print(f"✓ Report saved — ID: {report_id} | Company: {company_name}")
        return report_id

    except Exception as e:
        conn.rollback()
        print(f"DATABASE ERROR: {e}")
        return None

    finally:
        conn.close()


def get_all_reports():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, created_at, company_name, industry, employee_size,
               revenue, location, account_tier, final_score,
               dxw_fitment_score, strategic_account_potential_score,
               data_governance_complexity_score, analytics_fragmentation_risk_score,
               ai_data_readiness_score, executive_summary, next_step_strategy,
               recommended_outreach_angle
        FROM reports ORDER BY created_at DESC
    """)
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows


def get_report_by_id(report_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM reports WHERE id = ?", (report_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        report = dict(row)
        try:
            report["full_report_json"] = json.loads(report["full_report_json"])
        except Exception:
            pass
        return report
    return None


def get_contacts_by_report(report_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT name, title, email FROM contacts WHERE report_id = ?", (report_id,))
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows