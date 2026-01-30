#!/usr/bin/env python
"""
Load sample data into the healthcare analytics database.

This script loads the synthetic sample data from sql/seed/sample_data.sql
into the database for testing and demonstration purposes.

Usage:
    python -m scripts.load_sample_data
"""

from pathlib import Path

from sqlalchemy import text

from config import setup_logging, get_logger
from src.models import get_engine

setup_logging(log_level="INFO", log_format="text")
logger = get_logger(__name__)


def load_sample_data():
    """Load sample data from SQL file."""
    logger.info("Loading sample data")

    seed_file = Path(__file__).parent.parent / "sql" / "seed" / "sample_data.sql"

    if not seed_file.exists():
        logger.error(f"Sample data file not found: {seed_file}")
        return False

    engine = get_engine()

    with engine.connect() as conn:
        logger.info(f"Executing {seed_file.name}")
        sql_content = seed_file.read_text()

        # Use raw DBAPI connection to execute full script at once
        # This handles DO blocks and complex statements correctly
        raw_conn = conn.connection.dbapi_connection
        with raw_conn.cursor() as cursor:
            try:
                cursor.execute(sql_content)
                raw_conn.commit()
                logger.info(f"Successfully executed {seed_file.name}")
            except Exception as e:
                raw_conn.rollback()
                logger.error(f"Error executing {seed_file.name}: {e}")
                return False

        # Verify data was loaded by counting records
        logger.info("Verifying loaded data...")

        verification_queries = [
            ("dim.dim_date", "Date dimension records"),
            ("dim.dim_patient", "Patients"),
            ("dim.dim_location", "Locations"),
            ("dim.dim_provider", "Providers"),
            ("dim.dim_diagnosis", "Diagnoses"),
            ("dim.fact_encounter", "Encounters"),
            ("metrics.metric_patient_census", "Census records"),
            ("metrics.metric_ed_throughput", "ED throughput records"),
            ("metrics.metric_quality_indicator", "Quality indicators"),
        ]

        total_records = 0
        for table, description in verification_queries:
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                total_records += count
                logger.info(f"  {description}: {count:,}")
            except Exception as e:
                logger.warning(f"  {description}: Error querying - {e}")

        logger.info(f"Total records loaded: {total_records:,}")

    logger.info("Sample data loaded successfully")
    return True


def main():
    """Main entry point."""
    success = load_sample_data()
    if success:
        print("\nSample data loaded successfully!")
        print("You can now view the data in Grafana dashboards.")
    else:
        print("\nFailed to load sample data. Check the logs for details.")
        exit(1)


if __name__ == "__main__":
    main()
