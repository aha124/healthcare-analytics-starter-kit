"""SQLAlchemy models for Healthcare Analytics Starter Kit."""

from src.models.base import Base, TimestampMixin, AuditMixin
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
