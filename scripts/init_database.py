#!/usr/bin/env python
"""
Initialize the healthcare analytics database.

This script creates the required schemas, tables, views, and indexes
for the Healthcare Analytics Starter Kit.

Usage:
    python -m scripts.init_database
    python -m scripts.init_database --drop-existing
"""

import argparse
from pathlib import Path

from sqlalchemy import text

from config import setup_logging, get_logger, get_settings
from src.models import get_engine, Base
from src.models.staging import *  # noqa: F401, F403 - Import all models
from src.models.dimensional import *  # noqa: F401, F403
from src.models.metrics import *  # noqa: F401, F403

setup_logging(log_level="INFO", log_format="text")
logger = get_logger(__name__)
settings = get_settings()


def init_database(drop_existing: bool = False):
    """Initialize the database schema."""
    logger.info("Initializing database")

    engine = get_engine()

    with engine.connect() as conn:
        # Create schemas
        logger.info("Creating schemas")
        for schema in ["staging", "dim", "fact", "metrics"]:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        conn.commit()

        if drop_existing:
            logger.warning("Dropping existing tables")
            Base.metadata.drop_all(engine)

        # Create tables from SQLAlchemy models
        logger.info("Creating tables from models")
        Base.metadata.create_all(engine)

        # Execute additional SQL scripts
        sql_dir = Path(__file__).parent.parent / "sql" / "schema"
        if sql_dir.exists():
            for sql_file in sorted(sql_dir.glob("*.sql")):
                logger.info(f"Executing {sql_file.name}")
                sql_content = sql_file.read_text()
                for statement in sql_content.split(";"):
                    statement = statement.strip()
                    if statement:
                        try:
                            conn.execute(text(statement))
                        except Exception as e:
                            logger.warning(f"Statement failed: {e}")
                conn.commit()

        # Execute view creation
        views_dir = Path(__file__).parent.parent / "sql" / "views"
        if views_dir.exists():
            for sql_file in sorted(views_dir.glob("*.sql")):
                logger.info(f"Creating view from {sql_file.name}")
                sql_content = sql_file.read_text()
                try:
                    conn.execute(text(sql_content))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"View creation failed: {e}")

    logger.info("Database initialization completed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Initialize healthcare analytics database")
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing tables before creating",
    )
    args = parser.parse_args()

    init_database(drop_existing=args.drop_existing)


if __name__ == "__main__":
    main()
