"""Scheduled task runners for Healthcare Analytics Starter Kit.

This module provides functions for scheduled execution of analytics pipelines.
Can be invoked via cron, Airflow, Prefect, or any scheduler.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_logger, get_settings
from src.models import get_session
from pipelines.daily_refresh import DailyRefreshPipeline

logger = get_logger(__name__)
settings = get_settings()


def run_daily_refresh(
    lookback_days: int = 1,
    session: Session | None = None,
) -> dict[str, Any]:
    """
    Execute the daily data refresh pipeline.

    Recommended schedule: Daily at 2:00 AM local time.

    Args:
        lookback_days: Number of days to look back for incremental data.
        session: Optional SQLAlchemy session.

    Returns:
        Pipeline execution statistics.

    Example crontab entry:
        0 2 * * * /path/to/venv/bin/python -m pipelines.scheduled_tasks daily_refresh
    """
    logger.info(
        "Starting scheduled daily refresh",
        lookback_days=lookback_days,
    )

    pipeline = DailyRefreshPipeline(
        session=session,
        lookback_days=lookback_days,
    )
    return pipeline.run()


def run_hourly_metrics(session: Session | None = None) -> dict[str, Any]:
    """
    Update hourly operational metrics.

    Recommended schedule: Every hour on the hour.

    Args:
        session: Optional SQLAlchemy session.

    Returns:
        Execution statistics.

    Example crontab entry:
        0 * * * * /path/to/venv/bin/python -m pipelines.scheduled_tasks hourly_metrics
    """
    if session is None:
        session = get_session()

    stats: dict[str, Any] = {
        "start_time": datetime.now(timezone.utc),
        "metrics_updated": [],
    }

    logger.info("Starting hourly metrics update")

    try:
        # Update real-time census
        session.execute(text("""
            INSERT INTO metrics.unit_census_current (
                unit_name, current_census, staffed_beds,
                pending_admissions, pending_discharges, updated_at
            )
            SELECT
                COALESCE(e.department_id, 'Unknown') as unit_name,
                COUNT(DISTINCT e.source_encounter_id) as current_census,
                50 as staffed_beds,  -- Configure per unit
                0 as pending_admissions,
                COUNT(DISTINCT CASE
                    WHEN e.discharge_datetime IS NOT NULL
                        AND e.discharge_datetime > CURRENT_TIMESTAMP
                    THEN e.source_encounter_id
                END) as pending_discharges,
                CURRENT_TIMESTAMP
            FROM staging.encounters e
            WHERE e.admit_datetime <= CURRENT_TIMESTAMP
                AND (e.discharge_datetime IS NULL OR e.discharge_datetime > CURRENT_TIMESTAMP)
                AND e.encounter_class = 'inpatient'
            GROUP BY e.department_id
            ON CONFLICT (unit_name) DO UPDATE SET
                current_census = EXCLUDED.current_census,
                pending_discharges = EXCLUDED.pending_discharges,
                updated_at = CURRENT_TIMESTAMP
        """))
        stats["metrics_updated"].append("unit_census_current")

        # Update ED current status
        session.execute(text("""
            INSERT INTO metrics.ed_current_status (
                status_timestamp, current_volume, waiting_count,
                treatment_count, boarding_count, avg_wait_minutes
            )
            SELECT
                CURRENT_TIMESTAMP,
                COUNT(*) as current_volume,
                COUNT(CASE WHEN provider_contact_datetime IS NULL THEN 1 END) as waiting_count,
                COUNT(CASE
                    WHEN provider_contact_datetime IS NOT NULL
                        AND discharge_datetime IS NULL
                    THEN 1
                END) as treatment_count,
                COUNT(CASE
                    WHEN discharge_disposition = 'admit_pending'
                    THEN 1
                END) as boarding_count,
                AVG(CASE
                    WHEN provider_contact_datetime IS NULL
                    THEN EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - admit_datetime)) / 60
                END) as avg_wait_minutes
            FROM staging.encounters
            WHERE encounter_type = 'emergency'
                AND admit_datetime >= CURRENT_DATE
                AND (discharge_datetime IS NULL OR discharge_datetime > CURRENT_TIMESTAMP)
            ON CONFLICT DO NOTHING
        """))
        stats["metrics_updated"].append("ed_current_status")

        session.commit()

        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "success"

        logger.info(
            "Hourly metrics update completed",
            metrics_updated=stats["metrics_updated"],
        )

    except Exception as e:
        session.rollback()
        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "failed"
        stats["error"] = str(e)

        logger.error("Hourly metrics update failed", error=str(e))
        raise

    return stats


def run_monthly_aggregations(session: Session | None = None) -> dict[str, Any]:
    """
    Compute monthly aggregate metrics.

    Recommended schedule: 1st of month at 4:00 AM.

    Args:
        session: Optional SQLAlchemy session.

    Returns:
        Execution statistics.
    """
    if session is None:
        session = get_session()

    stats: dict[str, Any] = {
        "start_time": datetime.now(timezone.utc),
        "metrics_updated": [],
    }

    logger.info("Starting monthly aggregations")

    try:
        # Compute readmission metrics
        session.execute(text("""
            INSERT INTO metrics.readmission_metrics_monthly (
                metric_month, total_discharges, total_readmissions,
                readmission_rate, chf_readmission_rate, copd_readmission_rate,
                pneumonia_readmission_rate
            )
            SELECT
                DATE_TRUNC('month', e1.discharge_datetime) as metric_month,
                COUNT(DISTINCT e1.source_encounter_id) as total_discharges,
                COUNT(DISTINCT e2.source_encounter_id) as total_readmissions,
                COUNT(DISTINCT e2.source_encounter_id) * 100.0
                    / NULLIF(COUNT(DISTINCT e1.source_encounter_id), 0) as readmission_rate,
                -- CHF readmissions
                COUNT(DISTINCT CASE
                    WHEN e1.primary_diagnosis_code LIKE 'I50%' AND e2.source_encounter_id IS NOT NULL
                    THEN e2.source_encounter_id
                END) * 100.0 / NULLIF(
                    COUNT(DISTINCT CASE WHEN e1.primary_diagnosis_code LIKE 'I50%' THEN e1.source_encounter_id END), 0
                ) as chf_readmission_rate,
                -- COPD readmissions
                COUNT(DISTINCT CASE
                    WHEN e1.primary_diagnosis_code LIKE 'J44%' AND e2.source_encounter_id IS NOT NULL
                    THEN e2.source_encounter_id
                END) * 100.0 / NULLIF(
                    COUNT(DISTINCT CASE WHEN e1.primary_diagnosis_code LIKE 'J44%' THEN e1.source_encounter_id END), 0
                ) as copd_readmission_rate,
                -- Pneumonia readmissions
                COUNT(DISTINCT CASE
                    WHEN e1.primary_diagnosis_code LIKE 'J18%' AND e2.source_encounter_id IS NOT NULL
                    THEN e2.source_encounter_id
                END) * 100.0 / NULLIF(
                    COUNT(DISTINCT CASE WHEN e1.primary_diagnosis_code LIKE 'J18%' THEN e1.source_encounter_id END), 0
                ) as pneumonia_readmission_rate
            FROM staging.encounters e1
            LEFT JOIN staging.encounters e2 ON
                e1.source_patient_id = e2.source_patient_id
                AND e2.admit_datetime > e1.discharge_datetime
                AND e2.admit_datetime <= e1.discharge_datetime + INTERVAL '30 days'
                AND e2.encounter_class = 'inpatient'
            WHERE e1.encounter_class = 'inpatient'
                AND e1.discharge_datetime >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                AND e1.discharge_datetime < DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY DATE_TRUNC('month', e1.discharge_datetime)
            ON CONFLICT (metric_month) DO UPDATE SET
                total_discharges = EXCLUDED.total_discharges,
                total_readmissions = EXCLUDED.total_readmissions,
                readmission_rate = EXCLUDED.readmission_rate,
                chf_readmission_rate = EXCLUDED.chf_readmission_rate,
                copd_readmission_rate = EXCLUDED.copd_readmission_rate,
                pneumonia_readmission_rate = EXCLUDED.pneumonia_readmission_rate,
                updated_at = CURRENT_TIMESTAMP
        """))
        stats["metrics_updated"].append("readmission_metrics")

        # Compute LOS analysis
        session.execute(text("""
            INSERT INTO metrics.los_analysis_monthly (
                metric_month, service_line, drg_code, drg_description,
                discharge_count, los_days, expected_los_days, los_index
            )
            SELECT
                DATE_TRUNC('month', e.discharge_datetime) as metric_month,
                COALESCE(e.service_line, 'Unknown') as service_line,
                e.drg_code,
                e.drg_description,
                COUNT(*) as discharge_count,
                AVG(EXTRACT(EPOCH FROM (e.discharge_datetime - e.admit_datetime)) / 86400) as los_days,
                4.5 as expected_los_days,  -- Would come from benchmark data
                AVG(EXTRACT(EPOCH FROM (e.discharge_datetime - e.admit_datetime)) / 86400) / 4.5 as los_index
            FROM staging.encounters e
            WHERE e.encounter_class = 'inpatient'
                AND e.discharge_datetime >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month')
                AND e.discharge_datetime < DATE_TRUNC('month', CURRENT_DATE)
            GROUP BY
                DATE_TRUNC('month', e.discharge_datetime),
                e.service_line,
                e.drg_code,
                e.drg_description
            ON CONFLICT (metric_month, service_line, drg_code) DO UPDATE SET
                discharge_count = EXCLUDED.discharge_count,
                los_days = EXCLUDED.los_days,
                los_index = EXCLUDED.los_index,
                updated_at = CURRENT_TIMESTAMP
        """))
        stats["metrics_updated"].append("los_analysis")

        session.commit()

        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "success"

        logger.info(
            "Monthly aggregations completed",
            metrics_updated=stats["metrics_updated"],
        )

    except Exception as e:
        session.rollback()
        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "failed"
        stats["error"] = str(e)

        logger.error("Monthly aggregations failed", error=str(e))
        raise

    return stats


def run_data_quality_check(session: Session | None = None) -> dict[str, Any]:
    """
    Execute data quality checks across all staging tables.

    Recommended schedule: Daily at 6:00 AM.

    Args:
        session: Optional SQLAlchemy session.

    Returns:
        Quality check results.
    """
    if session is None:
        session = get_session()

    stats: dict[str, Any] = {
        "start_time": datetime.now(timezone.utc),
        "checks_performed": [],
        "issues_found": [],
    }

    logger.info("Starting data quality checks")

    try:
        # Check for orphaned encounters (no matching patient)
        result = session.execute(text("""
            SELECT COUNT(*) as orphan_count
            FROM staging.encounters e
            LEFT JOIN staging.patients p ON e.source_patient_id = p.source_patient_id
            WHERE p.source_patient_id IS NULL
        """))
        orphan_count = result.scalar()
        stats["checks_performed"].append("orphaned_encounters")
        if orphan_count > 0:
            stats["issues_found"].append({
                "check": "orphaned_encounters",
                "count": orphan_count,
                "severity": "warning",
            })

        # Check for missing required fields in encounters
        result = session.execute(text("""
            SELECT
                COUNT(CASE WHEN admit_datetime IS NULL THEN 1 END) as missing_admit,
                COUNT(CASE WHEN encounter_type IS NULL THEN 1 END) as missing_type,
                COUNT(CASE WHEN source_patient_id IS NULL THEN 1 END) as missing_patient
            FROM staging.encounters
            WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
        """))
        row = result.fetchone()
        stats["checks_performed"].append("required_fields_encounters")
        if row and (row[0] > 0 or row[1] > 0 or row[2] > 0):
            stats["issues_found"].append({
                "check": "required_fields_encounters",
                "missing_admit": row[0],
                "missing_type": row[1],
                "missing_patient": row[2],
                "severity": "error",
            })

        # Check for duplicate MRNs
        result = session.execute(text("""
            SELECT mrn, COUNT(*) as cnt
            FROM staging.patients
            GROUP BY mrn
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()
        stats["checks_performed"].append("duplicate_mrns")
        if duplicates:
            stats["issues_found"].append({
                "check": "duplicate_mrns",
                "count": len(duplicates),
                "severity": "warning",
            })

        # Check for future dates
        result = session.execute(text("""
            SELECT COUNT(*)
            FROM staging.encounters
            WHERE admit_datetime > CURRENT_TIMESTAMP + INTERVAL '1 day'
        """))
        future_count = result.scalar()
        stats["checks_performed"].append("future_dates")
        if future_count > 0:
            stats["issues_found"].append({
                "check": "future_dates",
                "count": future_count,
                "severity": "warning",
            })

        # Check for invalid diagnosis codes
        result = session.execute(text("""
            SELECT COUNT(*)
            FROM staging.diagnoses
            WHERE diagnosis_code IS NOT NULL
                AND diagnosis_code !~ '^[A-Z][0-9]{2}(\\.[0-9A-Z]{0,4})?$'
        """))
        invalid_codes = result.scalar()
        stats["checks_performed"].append("invalid_icd_codes")
        if invalid_codes > 0:
            stats["issues_found"].append({
                "check": "invalid_icd_codes",
                "count": invalid_codes,
                "severity": "warning",
            })

        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "success"
        stats["total_issues"] = len(stats["issues_found"])

        if stats["issues_found"]:
            logger.warning(
                "Data quality issues found",
                total_issues=stats["total_issues"],
                issues=stats["issues_found"],
            )
        else:
            logger.info("Data quality checks passed", checks=len(stats["checks_performed"]))

    except Exception as e:
        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "failed"
        stats["error"] = str(e)
        logger.error("Data quality checks failed", error=str(e))
        raise

    return stats


def run_cleanup_old_data(
    retention_days: int = 90,
    session: Session | None = None,
) -> dict[str, Any]:
    """
    Clean up old staging data beyond retention period.

    Recommended schedule: Weekly on Sunday at 3:00 AM.

    Args:
        retention_days: Number of days to retain data.
        session: Optional SQLAlchemy session.

    Returns:
        Cleanup statistics.
    """
    if session is None:
        session = get_session()

    stats: dict[str, Any] = {
        "start_time": datetime.now(timezone.utc),
        "retention_days": retention_days,
        "tables_cleaned": [],
        "rows_deleted": {},
    }

    logger.info("Starting data cleanup", retention_days=retention_days)

    try:
        cutoff_date = datetime.now(timezone.utc).date()

        # Note: In production, you'd want to archive before deleting
        # This is a simplified cleanup for the starter kit

        for table in [
            "staging.lab_results",
            "staging.vitals",
            "staging.medications",
        ]:
            result = session.execute(
                text(f"""
                    DELETE FROM {table}
                    WHERE created_at < :cutoff
                    RETURNING 1
                """),
                {"cutoff": cutoff_date},
            )
            deleted = result.rowcount
            stats["tables_cleaned"].append(table)
            stats["rows_deleted"][table] = deleted

        session.commit()

        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "success"
        stats["total_deleted"] = sum(stats["rows_deleted"].values())

        logger.info(
            "Data cleanup completed",
            total_deleted=stats["total_deleted"],
            tables_cleaned=stats["tables_cleaned"],
        )

    except Exception as e:
        session.rollback()
        stats["end_time"] = datetime.now(timezone.utc)
        stats["status"] = "failed"
        stats["error"] = str(e)
        logger.error("Data cleanup failed", error=str(e))
        raise

    return stats


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Run scheduled healthcare analytics tasks"
    )
    parser.add_argument(
        "task",
        choices=[
            "daily_refresh",
            "hourly_metrics",
            "monthly_aggregations",
            "data_quality",
            "cleanup",
        ],
        help="Task to run",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=1,
        help="Days to look back (daily_refresh only)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=90,
        help="Data retention days (cleanup only)",
    )

    args = parser.parse_args()

    task_map = {
        "daily_refresh": lambda: run_daily_refresh(lookback_days=args.lookback_days),
        "hourly_metrics": run_hourly_metrics,
        "monthly_aggregations": run_monthly_aggregations,
        "data_quality": run_data_quality_check,
        "cleanup": lambda: run_cleanup_old_data(retention_days=args.retention_days),
    }

    try:
        result = task_map[args.task]()
        print(f"Task '{args.task}' completed with status: {result['status']}")
        sys.exit(0 if result["status"] == "success" else 1)
    except Exception as e:
        print(f"Task '{args.task}' failed: {e}")
        sys.exit(1)
