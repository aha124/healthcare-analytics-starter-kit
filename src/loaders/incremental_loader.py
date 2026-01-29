"""Incremental data loading with watermark tracking."""

from datetime import datetime, timedelta
from typing import Any, Type

from sqlalchemy import Column, DateTime, Integer, String, select
from sqlalchemy.orm import Mapped, mapped_column

from config.logging_config import get_logger
from src.loaders.postgres_loader import PostgresLoader
from src.models.base import Base

logger = get_logger(__name__)


class LoadWatermark(Base):
    """Track high watermarks for incremental loads."""

    __tablename__ = "etl_watermark"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    last_value: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)


class IncrementalLoader(PostgresLoader):
    """
    Incremental data loader with watermark tracking.

    This loader extends PostgresLoader to support:
    - High watermark tracking for incremental loads
    - Automatic watermark updates
    - Recovery from failed loads
    - Lookback period for catching late-arriving data

    Example:
        >>> loader = IncrementalLoader()
        >>> # Get records since last load
        >>> since = loader.get_watermark("epic", "patients")
        >>> records = connector.fetch_patients(since=since)
        >>> loader.load_records(StagingPatient, records)
        >>> loader.update_watermark("epic", "patients", datetime.now())
    """

    def __init__(
        self,
        connection_string: str | None = None,
        lookback_hours: int = 2,
        echo: bool = False,
    ):
        """
        Initialize the incremental loader.

        Args:
            connection_string: Database connection string.
            lookback_hours: Hours to look back from watermark (for late data).
            echo: Whether to echo SQL statements.
        """
        super().__init__(connection_string, echo)
        self.lookback_hours = lookback_hours

    def get_watermark(
        self,
        source_system: str,
        entity_type: str,
        default: datetime | None = None,
    ) -> datetime:
        """
        Get the last watermark for a source/entity combination.

        Args:
            source_system: Source system identifier.
            entity_type: Entity type (patients, encounters, etc.).
            default: Default value if no watermark exists.

        Returns:
            Last watermark datetime (minus lookback period).
        """
        if not self._engine:
            self.connect()

        with self.get_session() as session:
            result = session.execute(
                select(LoadWatermark.last_value).where(
                    LoadWatermark.source_system == source_system,
                    LoadWatermark.entity_type == entity_type,
                )
            ).scalar()

            if result:
                # Apply lookback period
                watermark = result - timedelta(hours=self.lookback_hours)
                self._logger.info(
                    "Retrieved watermark",
                    source_system=source_system,
                    entity_type=entity_type,
                    watermark=watermark.isoformat(),
                )
                return watermark

        # Use default or epoch
        default_watermark = default or datetime(2020, 1, 1)
        self._logger.info(
            "No watermark found, using default",
            source_system=source_system,
            entity_type=entity_type,
            default=default_watermark.isoformat(),
        )
        return default_watermark

    def update_watermark(
        self,
        source_system: str,
        entity_type: str,
        value: datetime,
        records_processed: int = 0,
    ) -> None:
        """
        Update the watermark for a source/entity combination.

        Args:
            source_system: Source system identifier.
            entity_type: Entity type.
            value: New watermark value.
            records_processed: Number of records processed in this run.
        """
        if not self._engine:
            self.connect()

        with self.get_session() as session:
            # Check if watermark exists
            existing = session.execute(
                select(LoadWatermark).where(
                    LoadWatermark.source_system == source_system,
                    LoadWatermark.entity_type == entity_type,
                )
            ).scalar()

            if existing:
                existing.last_value = value
                existing.last_run_at = datetime.now()
                existing.records_processed = records_processed
            else:
                session.add(
                    LoadWatermark(
                        source_system=source_system,
                        entity_type=entity_type,
                        last_value=value,
                        last_run_at=datetime.now(),
                        records_processed=records_processed,
                    )
                )

            session.commit()

        self._logger.info(
            "Updated watermark",
            source_system=source_system,
            entity_type=entity_type,
            value=value.isoformat(),
            records_processed=records_processed,
        )

    def load_incremental(
        self,
        source_system: str,
        entity_type: str,
        model_class: Type[Base],
        records: list[dict[str, Any]],
        batch_size: int = 1000,
        upsert_on: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Load records and update watermark atomically.

        Args:
            source_system: Source system identifier.
            entity_type: Entity type.
            model_class: SQLAlchemy model class.
            records: Records to load.
            batch_size: Batch size for loading.
            upsert_on: Columns for upsert conflict detection.

        Returns:
            Load statistics.
        """
        if not records:
            self._logger.info(
                "No records to load",
                source_system=source_system,
                entity_type=entity_type,
            )
            return {"inserted": 0, "updated": 0, "errors": 0}

        # Find the max timestamp in records for watermark
        timestamp_fields = ["updated_at", "created_at", "effective_date", "recorded_date"]
        max_timestamp = None

        for record in records:
            for field in timestamp_fields:
                if field in record and record[field]:
                    ts = record[field]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if max_timestamp is None or ts > max_timestamp:
                        max_timestamp = ts

        # Load records
        result = self.load_records(
            model_class=model_class,
            records=records,
            batch_size=batch_size,
            upsert_on=upsert_on,
        )

        # Update watermark
        if max_timestamp and result.get("errors", 0) == 0:
            self.update_watermark(
                source_system=source_system,
                entity_type=entity_type,
                value=max_timestamp,
                records_processed=len(records),
            )

        return result

    def get_all_watermarks(self) -> list[dict[str, Any]]:
        """
        Get all watermarks.

        Returns:
            List of watermark dictionaries.
        """
        if not self._engine:
            self.connect()

        with self.get_session() as session:
            watermarks = session.execute(select(LoadWatermark)).scalars().all()
            return [
                {
                    "source_system": w.source_system,
                    "entity_type": w.entity_type,
                    "last_value": w.last_value.isoformat() if w.last_value else None,
                    "last_run_at": w.last_run_at.isoformat() if w.last_run_at else None,
                    "records_processed": w.records_processed,
                }
                for w in watermarks
            ]

    def reset_watermark(
        self,
        source_system: str,
        entity_type: str,
        new_value: datetime | None = None,
    ) -> None:
        """
        Reset watermark to a specific value or delete it.

        Args:
            source_system: Source system identifier.
            entity_type: Entity type.
            new_value: New watermark value (None to delete).
        """
        if not self._engine:
            self.connect()

        with self.get_session() as session:
            existing = session.execute(
                select(LoadWatermark).where(
                    LoadWatermark.source_system == source_system,
                    LoadWatermark.entity_type == entity_type,
                )
            ).scalar()

            if existing:
                if new_value:
                    existing.last_value = new_value
                    existing.last_run_at = datetime.now()
                    self._logger.info(
                        "Reset watermark",
                        source_system=source_system,
                        entity_type=entity_type,
                        new_value=new_value.isoformat(),
                    )
                else:
                    session.delete(existing)
                    self._logger.info(
                        "Deleted watermark",
                        source_system=source_system,
                        entity_type=entity_type,
                    )

            session.commit()
