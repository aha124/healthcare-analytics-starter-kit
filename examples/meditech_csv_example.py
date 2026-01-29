#!/usr/bin/env python
"""
MEDITECH CSV Import Example

This example demonstrates how to import healthcare data from MEDITECH
flat file exports (CSV/TXT format) into the analytics warehouse.

MEDITECH typically exports data in pipe-delimited format with specific
column naming conventions. This example shows how to:
1. Read MEDITECH export files
2. Map MEDITECH columns to standard format
3. Transform and validate data
4. Load into the analytics database

Usage:
    python examples/meditech_csv_example.py --data-dir /path/to/exports
"""

import argparse
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import setup_logging, get_logger
from src.connectors import CSVConnector
from src.transforms import (
    PatientTransform,
    EncounterTransform,
    DiagnosisTransform,
    VitalsTransform,
)
from src.quality import DataValidator, PHIScanner
from src.loaders import PostgresLoader
from src.models import get_session

# Configure logging
setup_logging(log_level="INFO", log_format="text")
logger = get_logger(__name__)


# MEDITECH field mapping
# Maps MEDITECH column names to standard schema
MEDITECH_PATIENT_MAPPING = {
    "PT_ACCT": "source_patient_id",
    "PT_MRN": "mrn",
    "PT_LNAME": "last_name",
    "PT_FNAME": "first_name",
    "PT_MNAME": "middle_name",
    "PT_DOB": "date_of_birth",
    "PT_SEX": "gender",
    "PT_SSN": "ssn",
    "PT_ADDR1": "address_line1",
    "PT_ADDR2": "address_line2",
    "PT_CITY": "address_city",
    "PT_STATE": "address_state",
    "PT_ZIP": "address_zip",
    "PT_PHONE": "phone_home",
    "PT_EMAIL": "email",
    "PT_LANG": "primary_language",
    "PT_MARITAL": "marital_status",
    "PT_RACE": "race",
    "PT_ETHNIC": "ethnicity",
}

MEDITECH_ENCOUNTER_MAPPING = {
    "ENC_NUM": "source_encounter_id",
    "PT_ACCT": "source_patient_id",
    "ENC_TYPE": "encounter_type",
    "ENC_CLASS": "encounter_class",
    "ADM_DT": "admit_datetime",
    "ADM_TM": "_admit_time",  # Will be combined with date
    "DIS_DT": "discharge_datetime",
    "DIS_TM": "_discharge_time",
    "ADM_SRC": "admit_source",
    "DIS_DISP": "discharge_disposition",
    "ATT_PROV": "attending_provider_id",
    "FAC_ID": "facility_id",
    "DEPT_ID": "department_id",
    "ROOM": "room_number",
    "BED": "bed_number",
    "PRI_DX": "primary_diagnosis_code",
    "DRG": "drg_code",
}


def create_sample_data(data_dir: Path):
    """Create sample MEDITECH-style export files for testing."""
    data_dir.mkdir(parents=True, exist_ok=True)

    # Sample patient file (pipe-delimited)
    patient_content = """PT_ACCT|PT_MRN|PT_LNAME|PT_FNAME|PT_DOB|PT_SEX|PT_ADDR1|PT_CITY|PT_STATE|PT_ZIP
PAT001|FAKE-MT-001|TestPatient|Alice|19800515|F|123 Main St|Springfield|IL|62701
PAT002|FAKE-MT-002|TestPatient|Bob|19751220|M|456 Oak Ave|Chicago|IL|60601
PAT003|FAKE-MT-003|TestPatient|Carol|19901003|F|789 Pine Rd|Aurora|IL|60505
"""
    (data_dir / "patients.txt").write_text(patient_content)

    # Sample encounter file
    encounter_content = """ENC_NUM|PT_ACCT|ENC_TYPE|ENC_CLASS|ADM_DT|ADM_TM|DIS_DT|DIS_TM|ADM_SRC|DIS_DISP|DEPT_ID|ROOM|BED|PRI_DX
ENC001|PAT001|IP|inpatient|20240115|1030|20240118|1400|7|01|MED|301|A|J18.9
ENC002|PAT002|ER|emergency|20240116|0845|20240116|1530|1|01|ED|ER5||R10.9
ENC003|PAT003|OP|outpatient|20240117|0900|20240117|1000|9|01|CARD|201|B|I10
"""
    (data_dir / "encounters.txt").write_text(encounter_content)

    # Sample vitals file
    vitals_content = """VIT_ID|ENC_NUM|PT_ACCT|VIT_DT|VIT_TM|HR|RR|SBP|DBP|TEMP|TEMP_U|SPO2|WT|WT_U|HT|HT_U
VIT001|ENC001|PAT001|20240115|1045|88|18|130|82|38.2|C|95|75.5|kg|170|cm
VIT002|ENC001|PAT001|20240116|0800|82|16|125|78|37.5|C|97|75.5|kg|170|cm
VIT003|ENC002|PAT002|20240116|0900|95|20|145|90|37.0|C|98|82.0|kg|175|cm
"""
    (data_dir / "vitals.txt").write_text(vitals_content)

    logger.info("Created sample data files", directory=str(data_dir))
    return data_dir


def process_meditech_exports(data_dir: Path, load_to_db: bool = False):
    """Process MEDITECH export files."""
    logger.info("Processing MEDITECH exports", directory=str(data_dir))

    # Initialize connector with MEDITECH settings
    connector = CSVConnector(
        data_directory=data_dir,
        delimiter="|",
        encoding="cp1252",  # MEDITECH often uses Windows encoding
        file_patterns={
            "patients": "patients*.txt",
            "encounters": "encounters*.txt",
            "vitals": "vitals*.txt",
        },
        field_mapping={
            "patients": MEDITECH_PATIENT_MAPPING,
            "encounters": MEDITECH_ENCOUNTER_MAPPING,
        },
    )

    # Initialize transforms and validators
    patient_transform = PatientTransform()
    encounter_transform = EncounterTransform()
    vitals_transform = VitalsTransform()
    validator = DataValidator()
    phi_scanner = PHIScanner()

    results = {
        "patients": {"processed": 0, "errors": 0},
        "encounters": {"processed": 0, "errors": 0},
        "vitals": {"processed": 0, "errors": 0},
    }

    # Process patients
    logger.info("Processing patient records")
    patient_batch = []
    for raw_patient in connector.fetch_patients():
        # Check for PHI (expected in patient data)
        phi_findings = phi_scanner.scan_record(raw_patient)
        if phi_findings:
            logger.debug("PHI fields found (expected)", count=len(phi_findings))

        # Validate
        validation = validator.validate_record(raw_patient, "patient")
        if not validation.is_valid:
            logger.warning("Validation failed", errors=validation.errors)
            results["patients"]["errors"] += 1
            continue

        # Transform
        patient = patient_transform.transform(raw_patient)
        if patient:
            patient_batch.append(patient.model_dump())
            results["patients"]["processed"] += 1
            logger.info(
                "Processed patient",
                mrn=patient.mrn,
                name=f"{patient.first_name} {patient.last_name}",
            )

    # Process encounters
    logger.info("Processing encounter records")
    encounter_batch = []
    for raw_encounter in connector.fetch_encounters():
        # Combine date and time fields (MEDITECH often separates these)
        if "_admit_time" in raw_encounter and raw_encounter.get("admit_datetime"):
            raw_encounter["admit_datetime"] = combine_date_time(
                raw_encounter["admit_datetime"],
                raw_encounter.get("_admit_time"),
            )
        if "_discharge_time" in raw_encounter and raw_encounter.get("discharge_datetime"):
            raw_encounter["discharge_datetime"] = combine_date_time(
                raw_encounter["discharge_datetime"],
                raw_encounter.get("_discharge_time"),
            )

        encounter = encounter_transform.transform(raw_encounter)
        if encounter:
            encounter_batch.append(encounter.model_dump())
            results["encounters"]["processed"] += 1
            logger.info(
                "Processed encounter",
                id=encounter.source_encounter_id,
                type=encounter.encounter_type,
                los=encounter.length_of_stay_hours,
            )

    # Process vitals
    logger.info("Processing vitals records")
    vitals_batch = []
    for raw_vitals in connector.fetch_vitals():
        vitals = vitals_transform.transform(raw_vitals)
        if vitals:
            vitals_batch.append(vitals.model_dump())
            results["vitals"]["processed"] += 1
            logger.info(
                "Processed vitals",
                id=vitals.source_vital_id,
                hr=vitals.heart_rate,
                temp=vitals.temperature_celsius,
                news=vitals.news_score,
            )

    # Load to database if requested
    if load_to_db:
        logger.info("Loading data to database")
        try:
            session = get_session()
            loader = PostgresLoader(session)

            if patient_batch:
                loader.upsert_batch("staging.patients", patient_batch)
            if encounter_batch:
                loader.upsert_batch("staging.encounters", encounter_batch)
            if vitals_batch:
                loader.upsert_batch("staging.vitals", vitals_batch)

            session.commit()
            logger.info("Database load completed")
        except Exception as e:
            logger.error("Database load failed", error=str(e))

    return results


def combine_date_time(date_val: str, time_val: str | None) -> str:
    """Combine MEDITECH date and time fields."""
    if not time_val:
        return date_val

    # MEDITECH formats: YYYYMMDD and HHMM
    try:
        date_str = str(date_val).replace("-", "")
        time_str = str(time_val).zfill(4)
        combined = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:]}:00"
        return combined
    except Exception:
        return date_val


def main():
    """Run MEDITECH CSV import example."""
    parser = argparse.ArgumentParser(description="MEDITECH CSV Import Example")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("/tmp/meditech_sample"),
        help="Directory containing MEDITECH export files",
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create sample data files for testing",
    )
    parser.add_argument(
        "--load-db",
        action="store_true",
        help="Load processed data to database",
    )

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("MEDITECH CSV Import Example")
    print("=" * 50)

    # Create sample data if requested or if directory doesn't exist
    if args.create_sample or not args.data_dir.exists():
        print("\nCreating sample MEDITECH export files...")
        create_sample_data(args.data_dir)

    # Process exports
    print(f"\nProcessing files from: {args.data_dir}")
    print("-" * 50)

    results = process_meditech_exports(args.data_dir, load_to_db=args.load_db)

    # Summary
    print("\n" + "=" * 50)
    print("Import Summary")
    print("=" * 50)
    for resource, counts in results.items():
        print(f"  {resource.capitalize()}: {counts['processed']} processed, {counts['errors']} errors")
    print("=" * 50)


if __name__ == "__main__":
    main()
