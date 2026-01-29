"""Daily data refresh pipeline for Healthcare Analytics Starter Kit.

This module orchestrates the daily ETL process:
1. Extract data from configured sources (FHIR, HL7, CSV, database)
2. Transform data through standardization pipelines
3. Load into staging tables
4. Update dimensional model
5. Compute metrics
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_logger, get_settings
from src.connectors import (
    FHIRConnector,
    HL7Connector,
    CSVConnector,
    DatabaseConnector,
)
from src.transforms import (
    PatientTransform,
    EncounterTransform,
    DiagnosisTransform,
    ProcedureTransform,
    LabResultTransform,
    VitalsTransform,
    MedicationTransform,
)
from src.loaders import PostgresLoader, IncrementalLoader
from src.quality import DataValidator, PHIScanner
from src.models import get_session

logger = get_logger(__name__)
settings = get_settings()


class DailyRefreshPipeline:
    """
    Orchestrates the daily data refresh process.

    This pipeline:
    - Extracts incremental data from all configured sources
    - Applies data quality validations
    - Scans for potential PHI exposure
    - Transforms and loads data into the warehouse
    - Updates metrics tables
    """

    def __init__(
        self,
        session: Session | None = None,
        lookback_days: int = 1,
    ):
        """
        Initialize the daily refresh pipeline.

        Args:
            session: SQLAlchemy session (created if not provided).
            lookback_days: Number of days to look back for incremental data.
        """
        self.session = session or get_session()
        self.lookback_days = lookback_days
        self.since_datetime = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Initialize components
        self.loader = PostgresLoader(self.session)
        self.incremental_loader = IncrementalLoader(self.session)
        self.validator = DataValidator()
        self.phi_scanner = PHIScanner()

        # Initialize transforms
        self.patient_transform = PatientTransform()
        self.encounter_transform = EncounterTransform()
        self.diagnosis_transform = DiagnosisTransform()
        self.procedure_transform = ProcedureTransform()
        self.lab_transform = LabResultTransform()
        self.vitals_transform = VitalsTransform()
        self.medication_transform = MedicationTransform()

        # Track statistics
        self.stats: dict[str, Any] = {
            "start_time": None,
            "end_time": None,
            "sources_processed": [],
            "records_extracted": {},
            "records_loaded": {},
            "validation_errors": {},
            "phi_warnings": 0,
        }

    def run(self) -> dict[str, Any]:
        """
        Execute the full daily refresh pipeline.

        Returns:
            Dictionary with pipeline statistics and results.
        """
        self.stats["start_time"] = datetime.now(timezone.utc)
        logger.info(
            "Starting daily refresh pipeline",
            since=self.since_datetime.isoformat(),
            lookback_days=self.lookback_days,
        )

        try:
            # Process each configured source
            if settings.fhir.enabled:
                self._process_fhir_source()

            if settings.hl7.enabled:
                self._process_hl7_source()

            if settings.csv.enabled:
                self._process_csv_source()

            # Update dimensional model
            self._update_dimensions()

            # Compute metrics
            self._compute_metrics()

            # Commit all changes
            self.session.commit()

            self.stats["end_time"] = datetime.now(timezone.utc)
            self.stats["status"] = "success"

            logger.info(
                "Daily refresh completed successfully",
                duration_seconds=(
                    self.stats["end_time"] - self.stats["start_time"]
                ).total_seconds(),
                records_loaded=self.stats["records_loaded"],
            )

        except Exception as e:
            self.session.rollback()
            self.stats["end_time"] = datetime.now(timezone.utc)
            self.stats["status"] = "failed"
            self.stats["error"] = str(e)

            logger.error(
                "Daily refresh failed",
                error=str(e),
                duration_seconds=(
                    self.stats["end_time"] - self.stats["start_time"]
                ).total_seconds(),
            )
            raise

        return self.stats

    def _process_fhir_source(self) -> None:
        """Process data from FHIR API source."""
        logger.info("Processing FHIR source")
        self.stats["sources_processed"].append("fhir")

        try:
            connector = FHIRConnector(
                base_url=str(settings.fhir.base_url),
                auth_method=settings.fhir.auth_method,
                client_id=settings.fhir.client_id,
                client_secret=(
                    settings.fhir.client_secret.get_secret_value()
                    if settings.fhir.client_secret
                    else None
                ),
            )

            # Extract and load patients
            patient_count = self._extract_transform_load(
                connector=connector,
                resource_type="patients",
                transform=self.patient_transform,
                table_name="staging.patients",
            )
            self.stats["records_loaded"]["fhir_patients"] = patient_count

            # Extract and load encounters
            encounter_count = self._extract_transform_load(
                connector=connector,
                resource_type="encounters",
                transform=self.encounter_transform,
                table_name="staging.encounters",
            )
            self.stats["records_loaded"]["fhir_encounters"] = encounter_count

            # Extract and load diagnoses
            diagnosis_count = self._extract_transform_load(
                connector=connector,
                resource_type="diagnoses",
                transform=self.diagnosis_transform,
                table_name="staging.diagnoses",
            )
            self.stats["records_loaded"]["fhir_diagnoses"] = diagnosis_count

            # Extract and load lab results
            lab_count = self._extract_transform_load(
                connector=connector,
                resource_type="lab_results",
                transform=self.lab_transform,
                table_name="staging.lab_results",
            )
            self.stats["records_loaded"]["fhir_labs"] = lab_count

            logger.info(
                "FHIR source processing completed",
                patients=patient_count,
                encounters=encounter_count,
                diagnoses=diagnosis_count,
                labs=lab_count,
            )

        except Exception as e:
            logger.error("FHIR source processing failed", error=str(e))
            self.stats["validation_errors"]["fhir"] = str(e)

    def _process_hl7_source(self) -> None:
        """Process data from HL7 message source."""
        logger.info("Processing HL7 source")
        self.stats["sources_processed"].append("hl7")

        try:
            connector = HL7Connector(
                message_directory=settings.hl7.message_directory,
            )

            # Process patient messages (ADT)
            patient_count = self._extract_transform_load(
                connector=connector,
                resource_type="patients",
                transform=self.patient_transform,
                table_name="staging.patients",
            )
            self.stats["records_loaded"]["hl7_patients"] = patient_count

            # Process encounter messages
            encounter_count = self._extract_transform_load(
                connector=connector,
                resource_type="encounters",
                transform=self.encounter_transform,
                table_name="staging.encounters",
            )
            self.stats["records_loaded"]["hl7_encounters"] = encounter_count

            logger.info(
                "HL7 source processing completed",
                patients=patient_count,
                encounters=encounter_count,
            )

        except Exception as e:
            logger.error("HL7 source processing failed", error=str(e))
            self.stats["validation_errors"]["hl7"] = str(e)

    def _process_csv_source(self) -> None:
        """Process data from CSV file source."""
        logger.info("Processing CSV source")
        self.stats["sources_processed"].append("csv")

        try:
            connector = CSVConnector(
                data_directory=settings.csv.data_directory,
            )

            # Process each data type if files exist
            for resource_type, transform, table_name in [
                ("patients", self.patient_transform, "staging.patients"),
                ("encounters", self.encounter_transform, "staging.encounters"),
                ("diagnoses", self.diagnosis_transform, "staging.diagnoses"),
                ("procedures", self.procedure_transform, "staging.procedures"),
                ("lab_results", self.lab_transform, "staging.lab_results"),
                ("vitals", self.vitals_transform, "staging.vitals"),
                ("medications", self.medication_transform, "staging.medications"),
            ]:
                count = self._extract_transform_load(
                    connector=connector,
                    resource_type=resource_type,
                    transform=transform,
                    table_name=table_name,
                )
                self.stats["records_loaded"][f"csv_{resource_type}"] = count

            logger.info("CSV source processing completed")

        except Exception as e:
            logger.error("CSV source processing failed", error=str(e))
            self.stats["validation_errors"]["csv"] = str(e)

    def _extract_transform_load(
        self,
        connector: Any,
        resource_type: str,
        transform: Any,
        table_name: str,
    ) -> int:
        """
        Extract, transform, and load a specific resource type.

        Args:
            connector: Data source connector.
            resource_type: Type of resource to extract.
            transform: Transform class instance.
            table_name: Target staging table.

        Returns:
            Number of records loaded.
        """
        loaded_count = 0
        batch = []
        batch_size = 1000

        # Get the appropriate fetch method
        fetch_method = getattr(connector, f"fetch_{resource_type}", None)
        if fetch_method is None:
            logger.warning(f"Connector does not support {resource_type}")
            return 0

        try:
            for raw_record in fetch_method(since=self.since_datetime):
                # Validate raw record
                validation_result = self.validator.validate_record(
                    raw_record, resource_type
                )
                if not validation_result.is_valid:
                    logger.warning(
                        "Validation failed for record",
                        resource_type=resource_type,
                        errors=validation_result.errors,
                    )
                    continue

                # Check for PHI exposure
                phi_findings = self.phi_scanner.scan_record(raw_record)
                if phi_findings:
                    self.stats["phi_warnings"] += 1
                    logger.warning(
                        "Potential PHI exposure detected",
                        resource_type=resource_type,
                        fields=phi_findings,
                    )

                # Transform record
                try:
                    transformed = transform.transform(raw_record)
                    if transformed:
                        batch.append(transformed.model_dump())
                except Exception as e:
                    logger.warning(
                        "Transform failed for record",
                        resource_type=resource_type,
                        error=str(e),
                    )
                    continue

                # Load batch when full
                if len(batch) >= batch_size:
                    self.loader.upsert_batch(table_name, batch)
                    loaded_count += len(batch)
                    batch = []

            # Load remaining records
            if batch:
                self.loader.upsert_batch(table_name, batch)
                loaded_count += len(batch)

        except Exception as e:
            logger.error(
                "ETL failed for resource type",
                resource_type=resource_type,
                error=str(e),
            )
            raise

        return loaded_count

    def _update_dimensions(self) -> None:
        """Update dimensional model from staging data."""
        logger.info("Updating dimensional model")

        try:
            # Update date dimension (idempotent)
            self.session.execute(text("""
                INSERT INTO dim.dates (date_key, full_date, year, quarter, month,
                    month_name, week_of_year, day_of_month, day_of_week, day_name,
                    is_weekend, is_holiday)
                SELECT
                    TO_CHAR(d, 'YYYYMMDD')::INTEGER,
                    d::DATE,
                    EXTRACT(YEAR FROM d)::INTEGER,
                    EXTRACT(QUARTER FROM d)::INTEGER,
                    EXTRACT(MONTH FROM d)::INTEGER,
                    TO_CHAR(d, 'Month'),
                    EXTRACT(WEEK FROM d)::INTEGER,
                    EXTRACT(DAY FROM d)::INTEGER,
                    EXTRACT(DOW FROM d)::INTEGER,
                    TO_CHAR(d, 'Day'),
                    EXTRACT(DOW FROM d) IN (0, 6),
                    FALSE
                FROM generate_series(
                    CURRENT_DATE - INTERVAL '1 year',
                    CURRENT_DATE + INTERVAL '2 years',
                    INTERVAL '1 day'
                ) AS d
                ON CONFLICT (date_key) DO NOTHING
            """))

            # Update patient dimension (SCD Type 2)
            self.session.execute(text("""
                -- Close existing records for changed patients
                UPDATE dim.patients dp
                SET valid_to = CURRENT_TIMESTAMP,
                    is_current = FALSE
                FROM staging.patients sp
                WHERE dp.source_patient_id = sp.source_patient_id
                    AND dp.is_current = TRUE
                    AND (
                        dp.first_name != COALESCE(sp.first_name, '')
                        OR dp.last_name != COALESCE(sp.last_name, '')
                        OR dp.gender != COALESCE(sp.gender, '')
                        OR dp.date_of_birth != sp.date_of_birth
                    )
            """))

            self.session.execute(text("""
                -- Insert new/changed patient records
                INSERT INTO dim.patients (
                    source_patient_id, mrn, first_name, last_name,
                    date_of_birth, gender, address_state, address_zip,
                    primary_language, marital_status, race, ethnicity,
                    valid_from, valid_to, is_current
                )
                SELECT
                    sp.source_patient_id,
                    sp.mrn,
                    sp.first_name,
                    sp.last_name,
                    sp.date_of_birth,
                    sp.gender,
                    sp.address_state,
                    sp.address_zip,
                    sp.primary_language,
                    sp.marital_status,
                    sp.race,
                    sp.ethnicity,
                    CURRENT_TIMESTAMP,
                    '9999-12-31'::TIMESTAMP,
                    TRUE
                FROM staging.patients sp
                WHERE NOT EXISTS (
                    SELECT 1 FROM dim.patients dp
                    WHERE dp.source_patient_id = sp.source_patient_id
                        AND dp.is_current = TRUE
                )
                ON CONFLICT DO NOTHING
            """))

            # Update fact encounters
            self.session.execute(text("""
                INSERT INTO fact.encounters (
                    encounter_key, patient_key, admit_date_key, discharge_date_key,
                    encounter_type, encounter_class, admit_source, discharge_disposition,
                    primary_diagnosis_code, drg_code, attending_provider_id,
                    facility_id, department_id, length_of_stay_days,
                    total_charges, total_cost
                )
                SELECT
                    se.source_encounter_id,
                    dp.patient_key,
                    TO_CHAR(se.admit_datetime, 'YYYYMMDD')::INTEGER,
                    TO_CHAR(se.discharge_datetime, 'YYYYMMDD')::INTEGER,
                    se.encounter_type,
                    se.encounter_class,
                    se.admit_source,
                    se.discharge_disposition,
                    se.primary_diagnosis_code,
                    se.drg_code,
                    se.attending_provider_id,
                    se.facility_id,
                    se.department_id,
                    EXTRACT(EPOCH FROM (se.discharge_datetime - se.admit_datetime)) / 86400,
                    se.total_charges,
                    se.total_cost
                FROM staging.encounters se
                JOIN dim.patients dp ON dp.source_patient_id = se.source_patient_id
                    AND dp.is_current = TRUE
                WHERE se.updated_at >= :since
                ON CONFLICT (encounter_key) DO UPDATE SET
                    discharge_date_key = EXCLUDED.discharge_date_key,
                    discharge_disposition = EXCLUDED.discharge_disposition,
                    length_of_stay_days = EXCLUDED.length_of_stay_days,
                    total_charges = EXCLUDED.total_charges,
                    total_cost = EXCLUDED.total_cost,
                    updated_at = CURRENT_TIMESTAMP
            """), {"since": self.since_datetime})

            logger.info("Dimensional model update completed")

        except Exception as e:
            logger.error("Dimensional model update failed", error=str(e))
            raise

    def _compute_metrics(self) -> None:
        """Compute and update metrics tables."""
        logger.info("Computing metrics")

        try:
            # Update daily census metrics
            self.session.execute(text("""
                INSERT INTO metrics.patient_census_daily (
                    census_date, total_census, icu_census, med_surg_census,
                    observation_census, admissions, discharges, transfers_in,
                    transfers_out, staffed_beds, avg_occupancy_rate
                )
                SELECT
                    d.full_date,
                    COUNT(DISTINCT CASE
                        WHEN e.admit_datetime::DATE <= d.full_date
                            AND (e.discharge_datetime IS NULL OR e.discharge_datetime::DATE > d.full_date)
                        THEN e.source_encounter_id
                    END) as total_census,
                    COUNT(DISTINCT CASE
                        WHEN e.department_id IN ('ICU', 'CCU', 'MICU', 'SICU')
                            AND e.admit_datetime::DATE <= d.full_date
                            AND (e.discharge_datetime IS NULL OR e.discharge_datetime::DATE > d.full_date)
                        THEN e.source_encounter_id
                    END) as icu_census,
                    COUNT(DISTINCT CASE
                        WHEN e.department_id IN ('MED', 'SURG', 'MEDSURG')
                            AND e.admit_datetime::DATE <= d.full_date
                            AND (e.discharge_datetime IS NULL OR e.discharge_datetime::DATE > d.full_date)
                        THEN e.source_encounter_id
                    END) as med_surg_census,
                    COUNT(DISTINCT CASE
                        WHEN e.encounter_class = 'observation'
                            AND e.admit_datetime::DATE <= d.full_date
                            AND (e.discharge_datetime IS NULL OR e.discharge_datetime::DATE > d.full_date)
                        THEN e.source_encounter_id
                    END) as observation_census,
                    COUNT(DISTINCT CASE
                        WHEN e.admit_datetime::DATE = d.full_date
                        THEN e.source_encounter_id
                    END) as admissions,
                    COUNT(DISTINCT CASE
                        WHEN e.discharge_datetime::DATE = d.full_date
                        THEN e.source_encounter_id
                    END) as discharges,
                    0 as transfers_in,
                    0 as transfers_out,
                    200 as staffed_beds,  -- Configure based on facility
                    0 as avg_occupancy_rate
                FROM dim.dates d
                CROSS JOIN staging.encounters e
                WHERE d.full_date >= CURRENT_DATE - INTERVAL '7 days'
                    AND d.full_date <= CURRENT_DATE
                GROUP BY d.full_date
                ON CONFLICT (census_date) DO UPDATE SET
                    total_census = EXCLUDED.total_census,
                    icu_census = EXCLUDED.icu_census,
                    med_surg_census = EXCLUDED.med_surg_census,
                    observation_census = EXCLUDED.observation_census,
                    admissions = EXCLUDED.admissions,
                    discharges = EXCLUDED.discharges,
                    updated_at = CURRENT_TIMESTAMP
            """))

            # Update ED throughput metrics
            self.session.execute(text("""
                INSERT INTO metrics.ed_throughput_daily (
                    census_date, ed_volume, admissions,
                    avg_door_to_provider_minutes, avg_ed_los_minutes,
                    lwbs_count, admission_rate
                )
                SELECT
                    e.admit_datetime::DATE as census_date,
                    COUNT(*) as ed_volume,
                    COUNT(CASE WHEN e.discharge_disposition = 'admitted' THEN 1 END) as admissions,
                    AVG(EXTRACT(EPOCH FROM (e.provider_contact_datetime - e.admit_datetime)) / 60)
                        as avg_door_to_provider_minutes,
                    AVG(EXTRACT(EPOCH FROM (e.discharge_datetime - e.admit_datetime)) / 60)
                        as avg_ed_los_minutes,
                    COUNT(CASE WHEN e.discharge_disposition = 'lwbs' THEN 1 END) as lwbs_count,
                    COUNT(CASE WHEN e.discharge_disposition = 'admitted' THEN 1 END) * 100.0
                        / NULLIF(COUNT(*), 0) as admission_rate
                FROM staging.encounters e
                WHERE e.encounter_type = 'emergency'
                    AND e.admit_datetime >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY e.admit_datetime::DATE
                ON CONFLICT (census_date) DO UPDATE SET
                    ed_volume = EXCLUDED.ed_volume,
                    admissions = EXCLUDED.admissions,
                    avg_door_to_provider_minutes = EXCLUDED.avg_door_to_provider_minutes,
                    avg_ed_los_minutes = EXCLUDED.avg_ed_los_minutes,
                    lwbs_count = EXCLUDED.lwbs_count,
                    admission_rate = EXCLUDED.admission_rate,
                    updated_at = CURRENT_TIMESTAMP
            """))

            logger.info("Metrics computation completed")

        except Exception as e:
            logger.error("Metrics computation failed", error=str(e))
            raise


def run_daily_refresh(
    lookback_days: int = 1,
    session: Session | None = None,
) -> dict[str, Any]:
    """
    Run the daily refresh pipeline.

    Args:
        lookback_days: Number of days to look back for changes.
        session: Optional SQLAlchemy session.

    Returns:
        Pipeline statistics dictionary.
    """
    pipeline = DailyRefreshPipeline(
        session=session,
        lookback_days=lookback_days,
    )
    return pipeline.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run daily refresh pipeline")
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=1,
        help="Number of days to look back for changes",
    )
    args = parser.parse_args()

    result = run_daily_refresh(lookback_days=args.lookback_days)
    print(f"Pipeline completed with status: {result['status']}")
