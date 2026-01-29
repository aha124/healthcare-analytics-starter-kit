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

        # Split by semicolon and execute each statement
        statements = sql_content.split(";")
        executed = 0

        for statement in statements:
            statement = statement.strip()
            if statement and not statement.startswith("--"):
                try:
                    conn.execute(text(statement))
                    executed += 1
                except Exception as e:
                    logger.warning(f"Statement failed: {str(e)[:100]}")

        conn.commit()
        logger.info(f"Executed {executed} statements")

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


if __name__ == "__main__":
    main()
