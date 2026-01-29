#!/usr/bin/env python
"""
Epic FHIR Integration Example

This example demonstrates how to connect to Epic's FHIR R4 API using
SMART Backend Services authentication (JWT-based).

Prerequisites:
1. Register your application in Epic's App Orchard
2. Generate an RSA key pair and upload the public key to App Orchard
3. Configure the environment variables below

Usage:
    python examples/epic_fhir_example.py
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import setup_logging, get_logger
from src.connectors import FHIRConnector
from src.transforms import PatientTransform, EncounterTransform
from src.quality import DataValidator, PHIScanner

# Configure logging
setup_logging(log_level="INFO", log_format="text")
logger = get_logger(__name__)


def main():
    """Run Epic FHIR integration example."""

    # Configuration from environment variables
    EPIC_FHIR_URL = os.getenv("EPIC_FHIR_URL", "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4")
    EPIC_CLIENT_ID = os.getenv("EPIC_CLIENT_ID")
    EPIC_PRIVATE_KEY_PATH = os.getenv("EPIC_PRIVATE_KEY_PATH", "./keys/epic_private_key.pem")

    if not EPIC_CLIENT_ID:
        logger.error("EPIC_CLIENT_ID environment variable is required")
        print("\nUsage:")
        print("  export EPIC_CLIENT_ID='your-app-orchard-client-id'")
        print("  export EPIC_PRIVATE_KEY_PATH='./keys/epic_private_key.pem'")
        print("  python examples/epic_fhir_example.py")
        return

    logger.info("Connecting to Epic FHIR API", base_url=EPIC_FHIR_URL)

    # Initialize connector with SMART Backend Services auth
    connector = FHIRConnector(
        base_url=EPIC_FHIR_URL,
        auth_method="smart_backend",
        client_id=EPIC_CLIENT_ID,
        private_key_path=EPIC_PRIVATE_KEY_PATH,
        # Token URL is derived from base_url for Epic
        token_url=f"{EPIC_FHIR_URL.rsplit('/api/', 1)[0]}/oauth2/token",
    )

    # Initialize transforms and validators
    patient_transform = PatientTransform()
    encounter_transform = EncounterTransform()
    validator = DataValidator()
    phi_scanner = PHIScanner()

    # Fetch patients modified in the last 24 hours
    since = datetime.now(timezone.utc) - timedelta(days=1)
    logger.info("Fetching patients", since=since.isoformat())

    patient_count = 0
    error_count = 0

    for raw_patient in connector.fetch_patients(since=since):
        patient_count += 1

        # Validate raw data
        validation = validator.validate_record(raw_patient, "patient")
        if not validation.is_valid:
            logger.warning(
                "Validation failed",
                patient_id=raw_patient.get("source_patient_id"),
                errors=validation.errors,
            )
            error_count += 1
            continue

        # Check for PHI exposure
        phi_findings = phi_scanner.scan_record(raw_patient)
        if phi_findings:
            logger.debug(
                "PHI fields detected (expected)",
                field_count=len(phi_findings),
            )

        # Transform to standard format
        patient = patient_transform.transform(raw_patient)
        if patient:
            logger.info(
                "Processed patient",
                mrn=patient.mrn,
                age=patient.age,
                gender=patient.gender,
            )

    logger.info(
        "Patient fetch completed",
        total=patient_count,
        errors=error_count,
    )

    # Fetch recent encounters
    logger.info("Fetching encounters", since=since.isoformat())

    encounter_count = 0
    for raw_encounter in connector.fetch_encounters(since=since):
        encounter_count += 1

        encounter = encounter_transform.transform(raw_encounter)
        if encounter:
            logger.info(
                "Processed encounter",
                encounter_id=encounter.source_encounter_id,
                type=encounter.encounter_type,
                los_hours=encounter.length_of_stay_hours,
            )

        # Limit for demo
        if encounter_count >= 10:
            break

    logger.info("Encounter fetch completed", total=encounter_count)

    # Summary
    print("\n" + "=" * 50)
    print("Epic FHIR Integration Summary")
    print("=" * 50)
    print(f"Patients processed: {patient_count}")
    print(f"Validation errors: {error_count}")
    print(f"Encounters processed: {encounter_count}")
    print("=" * 50)


if __name__ == "__main__":
    main()
