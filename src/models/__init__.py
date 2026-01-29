"""SQLAlchemy models for Healthcare Analytics Starter Kit."""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from config.settings import get_settings
from src.models.base import Base, TimestampMixin, AuditMixin


def get_engine() -> Engine:
    """
    Create and return a SQLAlchemy engine with connection pooling.

    The engine is configured using environment variables:
    - POSTGRES_HOST: Database host (default: localhost)
    - POSTGRES_PORT: Database port (default: 5432)
    - POSTGRES_DB: Database name (default: healthcare_analytics)
    - POSTGRES_USER: Database user (default: hask_user)
    - POSTGRES_PASSWORD: Database password

    Returns:
        Engine: SQLAlchemy engine instance with connection pooling.
    """
    settings = get_settings()
    db_settings = settings.database

    engine = create_engine(
        db_settings.connection_string,
        pool_size=db_settings.pool_size,
        max_overflow=db_settings.max_overflow,
        pool_timeout=db_settings.pool_timeout,
        pool_pre_ping=True,  # Enable connection health checks
        echo=settings.environment == "development" and settings.log_level == "DEBUG",
    )

    return engine
from src.models.staging import (
    StagingPatient,
    StagingEncounter,
    StagingDiagnosis,
    StagingProcedure,
    StagingLabResult,
    StagingVital,
    StagingMedication,
)
from src.models.dimensional import (
    DimPatient,
    DimProvider,
    DimLocation,
    DimDate,
    DimDiagnosis,
    DimProcedure,
    DimMedication,
    FactEncounter,
    FactDiagnosis,
    FactProcedure,
    FactLabResult,
    FactVital,
    FactMedication,
)
from src.models.metrics import (
    MetricPatientCensus,
    MetricEdThroughput,
    MetricReadmission,
    MetricLengthOfStay,
    MetricQualityIndicator,
)

__all__ = [
    # Engine
    "get_engine",
    # Base
    "Base",
    "TimestampMixin",
    "AuditMixin",
    # Staging
    "StagingPatient",
    "StagingEncounter",
    "StagingDiagnosis",
    "StagingProcedure",
    "StagingLabResult",
    "StagingVital",
    "StagingMedication",
    # Dimensional
    "DimPatient",
    "DimProvider",
    "DimLocation",
    "DimDate",
    "DimDiagnosis",
    "DimProcedure",
    "DimMedication",
    "FactEncounter",
    "FactDiagnosis",
    "FactProcedure",
    "FactLabResult",
    "FactVital",
    "FactMedication",
    # Metrics
    "MetricPatientCensus",
    "MetricEdThroughput",
    "MetricReadmission",
    "MetricLengthOfStay",
    "MetricQualityIndicator",
]
