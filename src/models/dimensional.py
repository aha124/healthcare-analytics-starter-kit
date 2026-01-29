"""Dimensional (Star Schema) models for healthcare analytics."""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import AuditMixin, Base


# =============================================================================
# DIMENSION TABLES
# =============================================================================


class DimDate(Base):
    """Date dimension for time-based analysis."""

    __tablename__ = "dim_date"

    date_key: Mapped[int] = mapped_column(Integer, primary_key=True)  # YYYYMMDD format
    full_date: Mapped[date] = mapped_column(Date, unique=True, nullable=False)

    # Date components
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    month_name: Mapped[str] = mapped_column(String(20), nullable=False)
    week_of_year: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    day_name: Mapped[str] = mapped_column(String(20), nullable=False)
    day_of_year: Mapped[int] = mapped_column(Integer, nullable=False)

    # Fiscal calendar (adjust as needed)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_month: Mapped[int] = mapped_column(Integer, nullable=False)

    # Flags
    is_weekend: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_holiday: Mapped[bool] = mapped_column(Boolean, default=False)
    holiday_name: Mapped[str | None] = mapped_column(String(50))

    # Relative dates
    is_current_day: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current_week: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current_month: Mapped[bool] = mapped_column(Boolean, default=False)
    is_current_year: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (
        Index("ix_dim_date_year_month", "year", "month"),
        Index("ix_dim_date_fiscal", "fiscal_year", "fiscal_quarter"),
    )


class DimPatient(Base, AuditMixin):
    """Patient dimension."""

    __tablename__ = "dim_patient"

    patient_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business keys
    mrn: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # SCD Type 2 fields
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Demographics
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    age: Mapped[int | None] = mapped_column(Integer)
    age_group: Mapped[str | None] = mapped_column(String(20))
    gender: Mapped[str | None] = mapped_column(String(20))

    # Geography
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(50))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(50))

    # Additional demographics
    language: Mapped[str | None] = mapped_column(String(50))
    marital_status: Mapped[str | None] = mapped_column(String(20))
    race: Mapped[str | None] = mapped_column(String(50))
    ethnicity: Mapped[str | None] = mapped_column(String(50))

    # Status
    deceased: Mapped[bool] = mapped_column(Boolean, default=False)
    deceased_date: Mapped[date | None] = mapped_column(Date)

    # Hash for change detection
    row_hash: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        Index("ix_dim_patient_mrn_current", "mrn", "is_current"),
        Index("ix_dim_patient_demographics", "gender", "age_group"),
        Index("ix_dim_patient_geography", "state", "city"),
    )


class DimProvider(Base, AuditMixin):
    """Healthcare provider dimension."""

    __tablename__ = "dim_provider"

    provider_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business keys
    provider_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    npi: Mapped[str | None] = mapped_column(String(20))

    # Name
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    full_name: Mapped[str | None] = mapped_column(String(200))
    credentials: Mapped[str | None] = mapped_column(String(50))

    # Classification
    specialty: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))
    provider_type: Mapped[str | None] = mapped_column(String(50))

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_dim_provider_npi", "npi"),
        Index("ix_dim_provider_specialty", "specialty"),
    )


class DimLocation(Base, AuditMixin):
    """Healthcare facility/location dimension."""

    __tablename__ = "dim_location"

    location_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business key
    location_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # Hierarchy
    facility_name: Mapped[str | None] = mapped_column(String(200))
    building: Mapped[str | None] = mapped_column(String(100))
    floor: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(100))
    room: Mapped[str | None] = mapped_column(String(50))
    bed: Mapped[str | None] = mapped_column(String(20))

    # Classification
    location_type: Mapped[str | None] = mapped_column(String(50))
    service_line: Mapped[str | None] = mapped_column(String(100))
    cost_center: Mapped[str | None] = mapped_column(String(50))

    # Capacity
    licensed_beds: Mapped[int | None] = mapped_column(Integer)
    operational_beds: Mapped[int | None] = mapped_column(Integer)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_dim_location_facility", "facility_name"),
        Index("ix_dim_location_type", "location_type"),
    )


class DimDiagnosis(Base, AuditMixin):
    """Diagnosis code dimension."""

    __tablename__ = "dim_diagnosis"

    diagnosis_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business key
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    code_system: Mapped[str] = mapped_column(String(50), nullable=False)

    # Description
    short_description: Mapped[str | None] = mapped_column(String(100))
    long_description: Mapped[str | None] = mapped_column(String(500))

    # Hierarchy (ICD-10)
    chapter: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str | None] = mapped_column(String(10))
    subcategory: Mapped[str | None] = mapped_column(String(10))

    # Groupings
    ccs_category: Mapped[str | None] = mapped_column(String(100))
    drg_mdc: Mapped[str | None] = mapped_column(String(100))

    # Flags
    is_chronic: Mapped[bool | None] = mapped_column(Boolean)
    is_comorbidity: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        UniqueConstraint("code", "code_system", name="uq_diagnosis_code_system"),
        Index("ix_dim_diagnosis_code", "code"),
        Index("ix_dim_diagnosis_chapter", "chapter"),
    )


class DimProcedure(Base, AuditMixin):
    """Procedure code dimension."""

    __tablename__ = "dim_procedure"

    procedure_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business key
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    code_system: Mapped[str] = mapped_column(String(50), nullable=False)

    # Description
    short_description: Mapped[str | None] = mapped_column(String(100))
    long_description: Mapped[str | None] = mapped_column(String(500))

    # Category
    category: Mapped[str | None] = mapped_column(String(100))
    subcategory: Mapped[str | None] = mapped_column(String(100))

    # Flags
    is_surgical: Mapped[bool | None] = mapped_column(Boolean)
    is_inpatient_only: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        UniqueConstraint("code", "code_system", name="uq_procedure_code_system"),
        Index("ix_dim_procedure_code", "code"),
    )


class DimMedication(Base, AuditMixin):
    """Medication dimension."""

    __tablename__ = "dim_medication"

    medication_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Business keys
    rxnorm_code: Mapped[str | None] = mapped_column(String(20))
    ndc_code: Mapped[str | None] = mapped_column(String(20))

    # Names
    generic_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200))

    # Classification
    drug_class: Mapped[str | None] = mapped_column(String(100))
    therapeutic_class: Mapped[str | None] = mapped_column(String(100))
    pharmacologic_class: Mapped[str | None] = mapped_column(String(100))

    # Route and form
    route: Mapped[str | None] = mapped_column(String(50))
    form: Mapped[str | None] = mapped_column(String(50))
    strength: Mapped[str | None] = mapped_column(String(50))

    # Flags
    is_controlled: Mapped[bool | None] = mapped_column(Boolean)
    dea_schedule: Mapped[str | None] = mapped_column(String(10))
    is_high_alert: Mapped[bool | None] = mapped_column(Boolean)
    is_antibiotic: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        Index("ix_dim_medication_rxnorm", "rxnorm_code"),
        Index("ix_dim_medication_generic", "generic_name"),
        Index("ix_dim_medication_class", "drug_class"),
    )


# =============================================================================
# FACT TABLES
# =============================================================================


class FactEncounter(Base, AuditMixin):
    """Encounter fact table."""

    __tablename__ = "fact_encounter"

    encounter_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    admission_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )
    discharge_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )
    location_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_location.location_key")
    )
    attending_provider_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_provider.provider_key")
    )
    primary_diagnosis_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_diagnosis.diagnosis_key")
    )

    # Degenerate dimensions
    encounter_number: Mapped[str | None] = mapped_column(String(50))
    encounter_type: Mapped[str | None] = mapped_column(String(50))
    encounter_class: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str | None] = mapped_column(String(30))
    admit_source: Mapped[str | None] = mapped_column(String(100))
    discharge_disposition: Mapped[str | None] = mapped_column(String(100))
    drg_code: Mapped[str | None] = mapped_column(String(10))
    financial_class: Mapped[str | None] = mapped_column(String(50))

    # Timestamps (for detailed analysis)
    admission_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discharge_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Measures
    length_of_stay_hours: Mapped[float | None] = mapped_column(Float)
    length_of_stay_days: Mapped[float | None] = mapped_column(Float)
    diagnosis_count: Mapped[int | None] = mapped_column(Integer)
    procedure_count: Mapped[int | None] = mapped_column(Integer)
    total_charges: Mapped[float | None] = mapped_column(Float)
    total_cost: Mapped[float | None] = mapped_column(Float)

    # Flags
    is_readmission: Mapped[bool | None] = mapped_column(Boolean)
    days_since_last_discharge: Mapped[int | None] = mapped_column(Integer)
    is_ed_visit: Mapped[bool | None] = mapped_column(Boolean)
    was_admitted_from_ed: Mapped[bool | None] = mapped_column(Boolean)

    # Relationships
    patient = relationship("DimPatient", foreign_keys=[patient_key])
    location = relationship("DimLocation", foreign_keys=[location_key])
    attending_provider = relationship("DimProvider", foreign_keys=[attending_provider_key])
    primary_diagnosis = relationship("DimDiagnosis", foreign_keys=[primary_diagnosis_key])

    __table_args__ = (
        Index("ix_fact_encounter_patient", "patient_key"),
        Index("ix_fact_encounter_admission_date", "admission_date_key"),
        Index("ix_fact_encounter_type", "encounter_type"),
        Index("ix_fact_encounter_location", "location_key"),
    )


class FactDiagnosis(Base, AuditMixin):
    """Diagnosis fact table (bridge between encounters and diagnoses)."""

    __tablename__ = "fact_diagnosis"

    fact_diagnosis_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    encounter_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("fact_encounter.encounter_key"), nullable=False
    )
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    diagnosis_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_diagnosis.diagnosis_key"), nullable=False
    )
    diagnosis_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )

    # Attributes
    diagnosis_type: Mapped[str | None] = mapped_column(String(50))
    rank: Mapped[int | None] = mapped_column(Integer)
    present_on_admission: Mapped[str | None] = mapped_column(String(5))
    clinical_status: Mapped[str | None] = mapped_column(String(30))

    # Relationships
    encounter = relationship("FactEncounter")
    diagnosis = relationship("DimDiagnosis")

    __table_args__ = (
        Index("ix_fact_diagnosis_encounter", "encounter_key"),
        Index("ix_fact_diagnosis_diagnosis", "diagnosis_key"),
        Index("ix_fact_diagnosis_patient", "patient_key"),
    )


class FactProcedure(Base, AuditMixin):
    """Procedure fact table."""

    __tablename__ = "fact_procedure"

    fact_procedure_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    encounter_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fact_encounter.encounter_key")
    )
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    procedure_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_procedure.procedure_key"), nullable=False
    )
    procedure_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )
    location_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_location.location_key")
    )
    provider_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_provider.provider_key")
    )

    # Timestamps
    procedure_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Measures
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    charges: Mapped[float | None] = mapped_column(Float)

    # Attributes
    status: Mapped[str | None] = mapped_column(String(30))
    anesthesia_type: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    procedure = relationship("DimProcedure")

    __table_args__ = (
        Index("ix_fact_procedure_encounter", "encounter_key"),
        Index("ix_fact_procedure_patient", "patient_key"),
        Index("ix_fact_procedure_date", "procedure_date_key"),
    )


class FactLabResult(Base, AuditMixin):
    """Lab result fact table."""

    __tablename__ = "fact_lab_result"

    fact_lab_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    encounter_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fact_encounter.encounter_key")
    )
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    result_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )

    # Lab test info (could be a dimension for larger datasets)
    test_code: Mapped[str] = mapped_column(String(50), nullable=False)
    test_name: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))

    # Timestamps
    result_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Measures
    numeric_value: Mapped[float | None] = mapped_column(Float)
    text_value: Mapped[str | None] = mapped_column(String(500))
    unit: Mapped[str | None] = mapped_column(String(50))

    # Reference ranges
    reference_low: Mapped[float | None] = mapped_column(Float)
    reference_high: Mapped[float | None] = mapped_column(Float)

    # Interpretation
    interpretation: Mapped[str | None] = mapped_column(String(50))
    is_abnormal: Mapped[bool | None] = mapped_column(Boolean)
    is_critical: Mapped[bool | None] = mapped_column(Boolean)

    __table_args__ = (
        Index("ix_fact_lab_patient", "patient_key"),
        Index("ix_fact_lab_encounter", "encounter_key"),
        Index("ix_fact_lab_test", "test_code"),
        Index("ix_fact_lab_date", "result_date_key"),
    )


class FactVital(Base, AuditMixin):
    """Vital signs fact table."""

    __tablename__ = "fact_vital"

    fact_vital_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    encounter_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fact_encounter.encounter_key")
    )
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    recorded_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )
    location_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_location.location_key")
    )

    # Timestamp
    recorded_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Measures
    heart_rate: Mapped[float | None] = mapped_column(Float)
    respiratory_rate: Mapped[float | None] = mapped_column(Float)
    systolic_bp: Mapped[float | None] = mapped_column(Float)
    diastolic_bp: Mapped[float | None] = mapped_column(Float)
    mean_arterial_pressure: Mapped[float | None] = mapped_column(Float)
    temperature_f: Mapped[float | None] = mapped_column(Float)
    oxygen_saturation: Mapped[float | None] = mapped_column(Float)
    pain_score: Mapped[int | None] = mapped_column(Integer)
    bmi: Mapped[float | None] = mapped_column(Float)
    gcs_total: Mapped[int | None] = mapped_column(Integer)

    # Computed scores
    news_score: Mapped[int | None] = mapped_column(Integer)
    news_risk_level: Mapped[str | None] = mapped_column(String(20))
    bp_classification: Mapped[str | None] = mapped_column(String(50))

    __table_args__ = (
        Index("ix_fact_vital_patient", "patient_key"),
        Index("ix_fact_vital_encounter", "encounter_key"),
        Index("ix_fact_vital_date", "recorded_date_key"),
    )


class FactMedication(Base, AuditMixin):
    """Medication fact table."""

    __tablename__ = "fact_medication"

    fact_medication_key: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Dimension keys
    encounter_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("fact_encounter.encounter_key")
    )
    patient_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_patient.patient_key"), nullable=False
    )
    medication_key: Mapped[int] = mapped_column(
        Integer, ForeignKey("dim_medication.medication_key"), nullable=False
    )
    order_date_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_date.date_key")
    )
    provider_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim_provider.provider_key")
    )

    # Timestamps
    order_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)

    # Prescription details
    dose_value: Mapped[float | None] = mapped_column(Float)
    dose_unit: Mapped[str | None] = mapped_column(String(30))
    route: Mapped[str | None] = mapped_column(String(50))
    frequency: Mapped[str | None] = mapped_column(String(100))
    is_prn: Mapped[bool | None] = mapped_column(Boolean)

    # Measures
    quantity: Mapped[float | None] = mapped_column(Float)
    days_supply: Mapped[int | None] = mapped_column(Integer)
    refills: Mapped[int | None] = mapped_column(Integer)

    # Status
    status: Mapped[str | None] = mapped_column(String(30))

    # Relationships
    medication = relationship("DimMedication")

    __table_args__ = (
        Index("ix_fact_medication_patient", "patient_key"),
        Index("ix_fact_medication_encounter", "encounter_key"),
        Index("ix_fact_medication_medication", "medication_key"),
        Index("ix_fact_medication_date", "order_date_key"),
    )
