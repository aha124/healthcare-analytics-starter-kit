"""Staging table models for raw data ingestion."""

from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class StagingPatient(Base, TimestampMixin):
    """Staging table for patient demographics."""

    __tablename__ = "staging_patient"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # Demographics
    mrn: Mapped[str | None] = mapped_column(String(50))
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    gender: Mapped[str | None] = mapped_column(String(20))

    # Address
    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(50))

    # Contact
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(100))

    # Additional demographics
    language: Mapped[str | None] = mapped_column(String(50))
    marital_status: Mapped[str | None] = mapped_column(String(20))
    race: Mapped[str | None] = mapped_column(String(50))
    ethnicity: Mapped[str | None] = mapped_column(String(50))

    # Status
    deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    deceased_date: Mapped[date | None] = mapped_column(Date)

    # Encrypted fields (hashed for matching)
    ssn_hash: Mapped[str | None] = mapped_column(String(100))

    # Raw data for debugging
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing status
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_patient_source", "source_system", "source_id"),
        Index("ix_staging_patient_mrn", "mrn"),
        Index("ix_staging_patient_batch", "batch_id"),
        Index("ix_staging_patient_processed", "is_processed"),
    )


class StagingEncounter(Base, TimestampMixin):
    """Staging table for encounters/visits."""

    __tablename__ = "staging_encounter"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))

    # Encounter details
    encounter_type: Mapped[str | None] = mapped_column(String(50))
    encounter_class: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(30))

    # Dates
    admission_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharge_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Location
    location: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    facility: Mapped[str | None] = mapped_column(String(200))

    # Provider
    attending_provider: Mapped[str | None] = mapped_column(String(200))

    # Admission/Discharge
    admit_source: Mapped[str | None] = mapped_column(String(100))
    discharge_disposition: Mapped[str | None] = mapped_column(String(100))

    # Clinical
    primary_diagnosis_code: Mapped[str | None] = mapped_column(String(20))
    drg_code: Mapped[str | None] = mapped_column(String(10))
    financial_class: Mapped[str | None] = mapped_column(String(50))

    # Computed
    length_of_stay_hours: Mapped[float | None] = mapped_column(Float)
    length_of_stay_days: Mapped[float | None] = mapped_column(Float)

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_encounter_source", "source_system", "source_id"),
        Index("ix_staging_encounter_patient", "patient_source_id"),
        Index("ix_staging_encounter_batch", "batch_id"),
        Index("ix_staging_encounter_dates", "admission_date", "discharge_date"),
    )


class StagingDiagnosis(Base, TimestampMixin):
    """Staging table for diagnoses."""

    __tablename__ = "staging_diagnosis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))
    encounter_source_id: Mapped[str | None] = mapped_column(String(100))

    # Diagnosis details
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    code_system: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500))

    # Type and status
    diagnosis_type: Mapped[str | None] = mapped_column(String(50))
    clinical_status: Mapped[str | None] = mapped_column(String(30))
    verification_status: Mapped[str | None] = mapped_column(String(30))
    severity: Mapped[str | None] = mapped_column(String(30))

    # Dates
    onset_date: Mapped[date | None] = mapped_column(Date)
    abatement_date: Mapped[date | None] = mapped_column(Date)
    recorded_date: Mapped[date | None] = mapped_column(Date)

    # Additional
    rank: Mapped[int | None] = mapped_column(Integer)
    present_on_admission: Mapped[str | None] = mapped_column(String(5))

    # Computed
    icd10_chapter: Mapped[str | None] = mapped_column(String(100))
    icd10_category: Mapped[str | None] = mapped_column(String(10))

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_diagnosis_source", "source_system", "source_id"),
        Index("ix_staging_diagnosis_code", "code"),
        Index("ix_staging_diagnosis_encounter", "encounter_source_id"),
        Index("ix_staging_diagnosis_batch", "batch_id"),
    )


class StagingProcedure(Base, TimestampMixin):
    """Staging table for procedures."""

    __tablename__ = "staging_procedure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))
    encounter_source_id: Mapped[str | None] = mapped_column(String(100))

    # Procedure details
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    code_system: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(500))

    # Status and timing
    status: Mapped[str | None] = mapped_column(String(30))
    performed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)

    # Location and performer
    performer: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str | None] = mapped_column(String(200))

    # Additional
    laterality: Mapped[str | None] = mapped_column(String(20))
    body_site: Mapped[str | None] = mapped_column(String(100))
    device: Mapped[str | None] = mapped_column(String(200))
    anesthesia_type: Mapped[str | None] = mapped_column(String(50))

    # Computed
    cpt_category: Mapped[str | None] = mapped_column(String(50))
    is_surgical: Mapped[bool | None] = mapped_column(Boolean)

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_procedure_source", "source_system", "source_id"),
        Index("ix_staging_procedure_code", "code"),
        Index("ix_staging_procedure_encounter", "encounter_source_id"),
        Index("ix_staging_procedure_batch", "batch_id"),
    )


class StagingLabResult(Base, TimestampMixin):
    """Staging table for lab results."""

    __tablename__ = "staging_lab_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))
    encounter_source_id: Mapped[str | None] = mapped_column(String(100))

    # Lab test details
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    code_system: Mapped[str | None] = mapped_column(String(50))
    test_name: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))

    # Result values
    value: Mapped[float | None] = mapped_column(Float)
    value_string: Mapped[str | None] = mapped_column(String(500))
    value_unit: Mapped[str | None] = mapped_column(String(50))

    # Reference ranges
    reference_range_low: Mapped[float | None] = mapped_column(Float)
    reference_range_high: Mapped[float | None] = mapped_column(Float)
    reference_range_text: Mapped[str | None] = mapped_column(String(200))

    # Status and interpretation
    interpretation: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(30))

    # Dates
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Additional
    specimen_type: Mapped[str | None] = mapped_column(String(100))
    ordering_provider: Mapped[str | None] = mapped_column(String(200))
    performing_lab: Mapped[str | None] = mapped_column(String(200))

    # Computed flags
    is_abnormal: Mapped[bool | None] = mapped_column(Boolean)
    is_critical: Mapped[bool | None] = mapped_column(Boolean)

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_lab_source", "source_system", "source_id"),
        Index("ix_staging_lab_code", "code"),
        Index("ix_staging_lab_patient", "patient_source_id"),
        Index("ix_staging_lab_date", "effective_date"),
        Index("ix_staging_lab_batch", "batch_id"),
    )


class StagingVital(Base, TimestampMixin):
    """Staging table for vital signs."""

    __tablename__ = "staging_vital"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))
    encounter_source_id: Mapped[str | None] = mapped_column(String(100))

    # Recording time
    recorded_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Core vitals
    heart_rate: Mapped[float | None] = mapped_column(Float)
    respiratory_rate: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[float | None] = mapped_column(Float)
    diastolic_bp: Mapped[float | None] = mapped_column(Float)
    mean_arterial_pressure: Mapped[float | None] = mapped_column(Float)
    temperature: Mapped[float | None] = mapped_column(Float)
    oxygen_saturation: Mapped[float | None] = mapped_column(Float)

    # Additional
    oxygen_device: Mapped[str | None] = mapped_column(String(100))
    fio2: Mapped[float | None] = mapped_column(Float)
    weight: Mapped[float | None] = mapped_column(Float)
    height: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    pain_score: Mapped[int | None] = mapped_column(Integer)

    # GCS
    gcs_total: Mapped[int | None] = mapped_column(Integer)
    gcs_eye: Mapped[int | None] = mapped_column(Integer)
    gcs_verbal: Mapped[int | None] = mapped_column(Integer)
    gcs_motor: Mapped[int | None] = mapped_column(Integer)

    # Context
    position: Mapped[str | None] = mapped_column(String(50))
    location: Mapped[str | None] = mapped_column(String(200))
    recorder: Mapped[str | None] = mapped_column(String(200))

    # Computed
    news_score: Mapped[int | None] = mapped_column(Integer)
    bp_classification: Mapped[str | None] = mapped_column(String(50))

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_vital_source", "source_system", "source_id"),
        Index("ix_staging_vital_patient", "patient_source_id"),
        Index("ix_staging_vital_date", "recorded_date"),
        Index("ix_staging_vital_batch", "batch_id"),
    )


class StagingMedication(Base, TimestampMixin):
    """Staging table for medications."""

    __tablename__ = "staging_medication"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str | None] = mapped_column(String(50))

    # References
    patient_source_id: Mapped[str | None] = mapped_column(String(100))
    encounter_source_id: Mapped[str | None] = mapped_column(String(100))

    # Medication details
    medication_code: Mapped[str | None] = mapped_column(String(50))
    medication_name: Mapped[str] = mapped_column(String(500), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(200))
    brand_name: Mapped[str | None] = mapped_column(String(200))
    ndc_code: Mapped[str | None] = mapped_column(String(20))
    rxnorm_code: Mapped[str | None] = mapped_column(String(20))

    # Prescription details
    status: Mapped[str | None] = mapped_column(String(30))
    intent: Mapped[str | None] = mapped_column(String(30))
    dose_value: Mapped[float | None] = mapped_column(Float)
    dose_unit: Mapped[str | None] = mapped_column(String(30))
    route: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(100))
    prn: Mapped[bool] = mapped_column(Boolean, default=False)

    # Dates
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    authored_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Prescriber and pharmacy
    prescriber: Mapped[str | None] = mapped_column(String(200))
    pharmacy: Mapped[str | None] = mapped_column(String(200))

    # Quantity
    quantity: Mapped[float | None] = mapped_column(Float)
    refills: Mapped[int | None] = mapped_column(Integer)
    days_supply: Mapped[int | None] = mapped_column(Integer)

    # Computed flags
    drug_class: Mapped[str | None] = mapped_column(String(50))
    is_high_alert: Mapped[bool | None] = mapped_column(Boolean)
    is_controlled: Mapped[bool | None] = mapped_column(Boolean)
    is_opioid: Mapped[bool | None] = mapped_column(Boolean)

    # Raw data
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Processing
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_staging_medication_source", "source_system", "source_id"),
        Index("ix_staging_medication_patient", "patient_source_id"),
        Index("ix_staging_medication_name", "medication_name"),
        Index("ix_staging_medication_batch", "batch_id"),
    )
