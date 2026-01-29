"""PostgreSQL data loader for staging and dimensional tables."""

from datetime import datetime
from typing import Any, Generator, Type, TypeVar

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from config.logging_config import get_logger
from config.settings import get_settings
from src.models.base import Base

logger = get_logger(__name__)
T = TypeVar("T", bound=Base)


class PostgresLoader:
    """
    PostgreSQL data loader with upsert and batch operations.

    This loader provides:
    - Batch inserts with configurable batch sizes
    - Upsert (insert on conflict update) operations
    - Transaction management
    - Performance metrics

    Example:
        >>> loader = PostgresLoader()
        >>> records = [{"source_id": "1", "mrn": "MRN001", ...}]
        >>> loader.load_staging_patients(records, batch_size=500)
    """

    def __init__(
        self,
        connection_string: str | None = None,
        echo: bool = False,
    ):
        """
        Initialize the PostgreSQL loader.

        Args:
            connection_string: Database connection string. If not provided,
                              uses the connection string from settings.
            echo: Whether to echo SQL statements (for debugging).
        """
        settings = get_settings()
        self.connection_string = connection_string or settings.database.connection_string
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self._echo = echo
        self._logger = get_logger(__name__)

    def connect(self) -> None:
        """Initialize database connection."""
        self._logger.info("Connecting to PostgreSQL")
        self._engine = create_engine(
            self.connection_string,
            echo=self._echo,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
        self._session_factory = sessionmaker(bind=self._engine)

    def disconnect(self) -> None:
        """Close database connection."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
        self._logger.info("Disconnected from PostgreSQL")

    def get_session(self) -> Session:
        """Get a new database session."""
        if not self._session_factory:
            self.connect()
        return self._session_factory()

    def create_tables(self) -> None:
        """Create all tables defined in models."""
        if not self._engine:
            self.connect()
        Base.metadata.create_all(self._engine)
        self._logger.info("Database tables created")

    def load_records(
        self,
        model_class: Type[T],
        records: list[dict[str, Any]],
        batch_size: int = 1000,
        upsert_on: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Load records into a table with optional upsert.

        Args:
            model_class: SQLAlchemy model class to load into.
            records: List of record dictionaries.
            batch_size: Number of records per batch.
            upsert_on: Columns to use for conflict detection (enables upsert).

        Returns:
            Dictionary with load statistics.
        """
        if not records:
            return {"inserted": 0, "updated": 0, "errors": 0}

        if not self._engine:
            self.connect()

        table = model_class.__table__
        start_time = datetime.now()
        total_inserted = 0
        total_updated = 0
        total_errors = 0

        # Filter records to valid columns
        valid_columns = {col.name for col in table.columns}

        with self.get_session() as session:
            try:
                for batch in self._batch_records(records, batch_size):
                    # Clean records to only include valid columns
                    cleaned_batch = [
                        {k: v for k, v in record.items() if k in valid_columns}
                        for record in batch
                    ]

                    if upsert_on:
                        # Upsert operation
                        result = self._upsert_batch(
                            session, table, cleaned_batch, upsert_on
                        )
                        total_inserted += result.get("inserted", 0)
                        total_updated += result.get("updated", 0)
                    else:
                        # Simple insert
                        session.execute(insert(table), cleaned_batch)
                        total_inserted += len(cleaned_batch)

                    session.commit()

            except Exception as e:
                session.rollback()
                total_errors += 1
                self._logger.error("Load failed", error=str(e))
                raise

        elapsed = (datetime.now() - start_time).total_seconds()
        records_per_second = len(records) / elapsed if elapsed > 0 else 0

        self._logger.info(
            "Load complete",
            table=table.name,
            inserted=total_inserted,
            updated=total_updated,
            errors=total_errors,
            elapsed_seconds=round(elapsed, 2),
            records_per_second=round(records_per_second, 1),
        )

        return {
            "inserted": total_inserted,
            "updated": total_updated,
            "errors": total_errors,
            "elapsed_seconds": elapsed,
        }

    def _upsert_batch(
        self,
        session: Session,
        table: Any,
        records: list[dict[str, Any]],
        conflict_columns: list[str],
    ) -> dict[str, int]:
        """
        Perform upsert on a batch of records.

        Args:
            session: Database session.
            table: SQLAlchemy table object.
            records: Records to upsert.
            conflict_columns: Columns for conflict detection.

        Returns:
            Dictionary with insert/update counts.
        """
        if not records:
            return {"inserted": 0, "updated": 0}

        # Build upsert statement
        stmt = insert(table).values(records)

        # Get columns to update on conflict (all except conflict columns and primary key)
        update_columns = {
            col.name: stmt.excluded[col.name]
            for col in table.columns
            if col.name not in conflict_columns and not col.primary_key
        }

        # Add updated_at if it exists
        if "updated_at" in update_columns:
            from sqlalchemy import func

            update_columns["updated_at"] = func.now()

        # Create ON CONFLICT DO UPDATE statement
        stmt = stmt.on_conflict_do_update(
            index_elements=conflict_columns,
            set_=update_columns,
        )

        result = session.execute(stmt)

        # PostgreSQL doesn't easily distinguish inserts vs updates
        # Return total as inserted (could use xmax to distinguish)
        return {"inserted": result.rowcount, "updated": 0}

    @staticmethod
    def _batch_records(
        records: list[dict[str, Any]],
        batch_size: int,
    ) -> Generator[list[dict[str, Any]], None, None]:
        """Yield batches of records."""
        for i in range(0, len(records), batch_size):
            yield records[i : i + batch_size]

    def execute_sql(self, sql: str, params: dict[str, Any] | None = None) -> Any:
        """
        Execute raw SQL statement.

        Args:
            sql: SQL statement to execute.
            params: Optional parameters for the statement.

        Returns:
            Result of the execution.
        """
        if not self._engine:
            self.connect()

        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            session.commit()
            return result

    def truncate_table(self, model_class: Type[T]) -> None:
        """Truncate a table (delete all rows)."""
        table_name = model_class.__tablename__
        self.execute_sql(f"TRUNCATE TABLE {table_name} CASCADE")
        self._logger.info("Truncated table", table=table_name)

    def get_record_count(self, model_class: Type[T]) -> int:
        """Get the number of records in a table."""
        table_name = model_class.__tablename__
        result = self.execute_sql(f"SELECT COUNT(*) FROM {table_name}")
        return result.scalar()

    def __enter__(self) -> "PostgresLoader":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()
