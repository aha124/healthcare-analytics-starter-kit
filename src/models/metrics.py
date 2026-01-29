"""Pre-aggregated metric tables for healthcare analytics dashboards."""

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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class MetricPatientCensus(Base, TimestampMixin):
    """Daily patient census metrics by location."""

    __tablename__ = "metric_patient_census"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    census_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Location
    facility: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(100))
    location_key: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("dim.dim_location.location_key")
    )

    # Census counts
    midnight_census: Mapped[int | None] = mapped_column(Integer)
    admissions: Mapped[int | None] = mapped_column(Integer)
    discharges: Mapped[int | None] = mapped_column(Integer)
    transfers_in: Mapped[int | None] = mapped_column(Integer)
    transfers_out: Mapped[int | None] = mapped_column(Integer)
    deaths: Mapped[int | None] = mapped_column(Integer)

    # Capacity metrics
    licensed_beds: Mapped[int | None] = mapped_column(Integer)
    operational_beds: Mapped[int | None] = mapped_column(Integer)
    occupancy_rate: Mapped[float | None] = mapped_column(Float)

    # Patient type breakdown
    inpatient_count: Mapped[int | None] = mapped_column(Integer)
    observation_count: Mapped[int | None] = mapped_column(Integer)
    icu_count: Mapped[int | None] = mapped_column(Integer)
    pediatric_count: Mapped[int | None] = mapped_column(Integer)

    # Acuity
    avg_acuity_score: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        UniqueConstraint("census_date", "location_key", name="uq_census_date_location"),
        Index("ix_metric_census_date", "census_date"),
        Index("ix_metric_census_facility", "facility"),
        {"schema": "metrics"},
    )


class MetricEdThroughput(Base, TimestampMixin):
    """ED throughput metrics by hour."""

    __tablename__ = "metric_ed_throughput"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_hour: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-23

    # Location
    facility: Mapped[str | None] = mapped_column(String(200))
    ed_location: Mapped[str | None] = mapped_column(String(100))

    # Volume metrics
    arrivals: Mapped[int | None] = mapped_column(Integer)
    departures: Mapped[int | None] = mapped_column(Integer)
    patients_in_ed: Mapped[int | None] = mapped_column(Integer)
    patients_waiting: Mapped[int | None] = mapped_column(Integer)
    patients_in_treatment: Mapped[int | None] = mapped_column(Integer)

    # Disposition
    admitted: Mapped[int | None] = mapped_column(Integer)
    discharged: Mapped[int | None] = mapped_column(Integer)
    transferred: Mapped[int | None] = mapped_column(Integer)
    left_without_seen: Mapped[int | None] = mapped_column(Integer)
    left_ama: Mapped[int | None] = mapped_column(Integer)

    # Time metrics (minutes)
    avg_door_to_provider: Mapped[float | None] = mapped_column(Float)
    avg_door_to_bed: Mapped[float | None] = mapped_column(Float)
    avg_length_of_stay: Mapped[float | None] = mapped_column(Float)
    avg_boarding_time: Mapped[float | None] = mapped_column(Float)

    # Percentiles
    median_los: Mapped[float | None] = mapped_column(Float)
    p90_los: Mapped[float | None] = mapped_column(Float)

    # Acuity
    esi_1_count: Mapped[int | None] = mapped_column(Integer)
    esi_2_count: Mapped[int | None] = mapped_column(Integer)
    esi_3_count: Mapped[int | None] = mapped_column(Integer)
    esi_4_count: Mapped[int | None] = mapped_column(Integer)
    esi_5_count: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("metric_date", "metric_hour", "facility", name="uq_ed_date_hour_facility"),
        Index("ix_metric_ed_date", "metric_date"),
        Index("ix_metric_ed_facility", "facility"),
        {"schema": "metrics"},
    )


class MetricReadmission(Base, TimestampMixin):
    """30-day readmission metrics."""

    __tablename__ = "metric_readmission"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    discharge_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Grouping dimensions
    facility: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    discharge_diagnosis_category: Mapped[str | None] = mapped_column(String(100))
    payer_type: Mapped[str | None] = mapped_column(String(50))
    age_group: Mapped[str | None] = mapped_column(String(20))

    # Index encounter
    index_discharges: Mapped[int | None] = mapped_column(Integer)

    # Readmission counts
    readmissions_7_day: Mapped[int | None] = mapped_column(Integer)
    readmissions_14_day: Mapped[int | None] = mapped_column(Integer)
    readmissions_30_day: Mapped[int | None] = mapped_column(Integer)

    # Rates
    readmission_rate_7_day: Mapped[float | None] = mapped_column(Float)
    readmission_rate_14_day: Mapped[float | None] = mapped_column(Float)
    readmission_rate_30_day: Mapped[float | None] = mapped_column(Float)

    # Potentially preventable
    potentially_preventable_30_day: Mapped[int | None] = mapped_column(Integer)
    ppr_rate: Mapped[float | None] = mapped_column(Float)

    # CMS penalties (if applicable)
    cms_expected_rate: Mapped[float | None] = mapped_column(Float)
    excess_readmission_ratio: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_metric_readmission_date", "discharge_date"),
        Index("ix_metric_readmission_facility", "facility"),
        Index("ix_metric_readmission_diagnosis", "discharge_diagnosis_category"),
        {"schema": "metrics"},
    )


class MetricLengthOfStay(Base, TimestampMixin):
    """Length of stay metrics by various dimensions."""

    __tablename__ = "metric_length_of_stay"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Grouping dimensions
    facility: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    service_line: Mapped[str | None] = mapped_column(String(100))
    drg_code: Mapped[str | None] = mapped_column(String(10))
    drg_description: Mapped[str | None] = mapped_column(String(200))
    payer_type: Mapped[str | None] = mapped_column(String(50))

    # Volume
    discharge_count: Mapped[int | None] = mapped_column(Integer)

    # LOS statistics (days)
    avg_los: Mapped[float | None] = mapped_column(Float)
    median_los: Mapped[float | None] = mapped_column(Float)
    min_los: Mapped[float | None] = mapped_column(Float)
    max_los: Mapped[float | None] = mapped_column(Float)
    std_dev_los: Mapped[float | None] = mapped_column(Float)
    p25_los: Mapped[float | None] = mapped_column(Float)
    p75_los: Mapped[float | None] = mapped_column(Float)
    p90_los: Mapped[float | None] = mapped_column(Float)

    # Comparison to geometric mean (CMS)
    expected_los: Mapped[float | None] = mapped_column(Float)
    los_index: Mapped[float | None] = mapped_column(Float)  # Observed / Expected

    # Long stay counts
    long_stay_count_7_plus: Mapped[int | None] = mapped_column(Integer)
    long_stay_count_14_plus: Mapped[int | None] = mapped_column(Integer)
    long_stay_count_30_plus: Mapped[int | None] = mapped_column(Integer)

    __table_args__ = (
        Index("ix_metric_los_date", "metric_date"),
        Index("ix_metric_los_facility", "facility"),
        Index("ix_metric_los_drg", "drg_code"),
        {"schema": "metrics"},
    )


class MetricQualityIndicator(Base, TimestampMixin):
    """Quality and safety metrics."""

    __tablename__ = "metric_quality_indicator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)
    metric_period: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, weekly, monthly

    # Location
    facility: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    unit: Mapped[str | None] = mapped_column(String(100))

    # Indicator
    indicator_code: Mapped[str] = mapped_column(String(50), nullable=False)
    indicator_name: Mapped[str] = mapped_column(String(200), nullable=False)
    indicator_category: Mapped[str | None] = mapped_column(String(100))

    # Numerator/Denominator
    numerator: Mapped[int | None] = mapped_column(Integer)
    denominator: Mapped[int | None] = mapped_column(Integer)
    rate: Mapped[float | None] = mapped_column(Float)
    rate_per_1000: Mapped[float | None] = mapped_column(Float)

    # Benchmarks
    target_rate: Mapped[float | None] = mapped_column(Float)
    benchmark_rate: Mapped[float | None] = mapped_column(Float)
    national_benchmark: Mapped[float | None] = mapped_column(Float)

    # Performance
    meets_target: Mapped[bool | None] = mapped_column(Boolean)
    variance_from_target: Mapped[float | None] = mapped_column(Float)
    percentile_rank: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_metric_quality_date", "metric_date"),
        Index("ix_metric_quality_indicator", "indicator_code"),
        Index("ix_metric_quality_facility", "facility"),
        {"schema": "metrics"},
    )


class MetricOperationalKPI(Base, TimestampMixin):
    """Operational KPI metrics."""

    __tablename__ = "metric_operational_kpi"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Location
    facility: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))

    # KPI identification
    kpi_code: Mapped[str] = mapped_column(String(50), nullable=False)
    kpi_name: Mapped[str] = mapped_column(String(200), nullable=False)
    kpi_category: Mapped[str | None] = mapped_column(String(100))

    # Value
    kpi_value: Mapped[float | None] = mapped_column(Float)
    kpi_unit: Mapped[str | None] = mapped_column(String(50))

    # Trend
    prior_period_value: Mapped[float | None] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    trend_direction: Mapped[str | None] = mapped_column(String(20))  # up, down, flat

    # Target
    target_value: Mapped[float | None] = mapped_column(Float)
    variance_from_target: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(20))  # green, yellow, red

    __table_args__ = (
        Index("ix_metric_kpi_date", "metric_date"),
        Index("ix_metric_kpi_code", "kpi_code"),
        Index("ix_metric_kpi_facility", "facility"),
        {"schema": "metrics"},
    )


# Common quality indicators to pre-populate
QUALITY_INDICATORS = [
    {"code": "MORT_30_AMI", "name": "30-Day Mortality - AMI", "category": "Mortality"},
    {"code": "MORT_30_HF", "name": "30-Day Mortality - Heart Failure", "category": "Mortality"},
    {"code": "MORT_30_PN", "name": "30-Day Mortality - Pneumonia", "category": "Mortality"},
    {"code": "READM_30_AMI", "name": "30-Day Readmission - AMI", "category": "Readmission"},
    {"code": "READM_30_HF", "name": "30-Day Readmission - Heart Failure", "category": "Readmission"},
    {"code": "READM_30_PN", "name": "30-Day Readmission - Pneumonia", "category": "Readmission"},
    {"code": "CAUTI", "name": "Catheter-Associated UTI", "category": "HAI"},
    {"code": "CLABSI", "name": "Central Line-Associated BSI", "category": "HAI"},
    {"code": "SSI_COLON", "name": "SSI - Colon Surgery", "category": "HAI"},
    {"code": "SSI_HYST", "name": "SSI - Hysterectomy", "category": "HAI"},
    {"code": "MRSA", "name": "MRSA Bacteremia", "category": "HAI"},
    {"code": "CDIFF", "name": "C. diff Infection", "category": "HAI"},
    {"code": "FALLS", "name": "Patient Falls", "category": "Safety"},
    {"code": "FALLS_INJ", "name": "Falls with Injury", "category": "Safety"},
    {"code": "PRESSURE_INJ", "name": "Hospital-Acquired Pressure Injuries", "category": "Safety"},
    {"code": "VTE_PROPH", "name": "VTE Prophylaxis", "category": "Process"},
    {"code": "SEPSIS_BUNDLE", "name": "Sepsis Bundle Compliance", "category": "Process"},
]

OPERATIONAL_KPIS = [
    {"code": "OR_UTIL", "name": "OR Utilization Rate", "category": "Surgical"},
    {"code": "OR_TURNOVER", "name": "OR Turnover Time", "category": "Surgical"},
    {"code": "FIRST_CASE_ON_TIME", "name": "First Case On-Time Start", "category": "Surgical"},
    {"code": "APPT_NO_SHOW", "name": "Appointment No-Show Rate", "category": "Access"},
    {"code": "CYCLE_TIME", "name": "Clinic Cycle Time", "category": "Access"},
    {"code": "DAYS_IN_AR", "name": "Days in A/R", "category": "Revenue Cycle"},
    {"code": "DENIAL_RATE", "name": "Claim Denial Rate", "category": "Revenue Cycle"},
    {"code": "CLEAN_CLAIM", "name": "Clean Claim Rate", "category": "Revenue Cycle"},
    {"code": "NURSE_TURNOVER", "name": "RN Turnover Rate", "category": "Workforce"},
    {"code": "OVERTIME_PCT", "name": "Overtime Percentage", "category": "Workforce"},
]
