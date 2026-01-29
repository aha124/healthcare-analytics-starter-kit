#!/usr/bin/env python
"""
Cerner FHIR Integration Example

This example demonstrates how to connect to Cerner's (Oracle Health) FHIR R4 API
using OAuth 2.0 client credentials authentication.

Prerequisites:
1. Register your application at code.cerner.com
2. Obtain client credentials (client_id and client_secret)
3. Get your tenant ID from your Cerner representative

Usage:
    python examples/cerner_integration.py
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import setup_logging, get_logger
from src.connectors import FHIRConnector
from src.transforms import (
    PatientTransform,
    EncounterTransform,
    DiagnosisTransform,
    LabResultTransform,
)
from src.loaders import PostgresLoader
from src.models import get_session

# Configure logging
setup_logging(log_level="INFO", log_format="text")
logger = get_logger(__name__)


# Cerner Sandbox for testing (public, no auth required)
CERNER_SANDBOX_URL = "https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d"


def run_sandbox_demo():
    """Run demo against Cerner's public sandbox."""
    logger.info("Connecting to Cerner Sandbox (public)")

    connector = FHIRConnector(
        base_url=CERNER_SANDBOX_URL,
        auth_method="none",  # Sandbox is public
    )

    # Initialize transforms
    patient_transform = PatientTransform()
    encounter_transform = EncounterTransform()

    # Fetch sample patients from sandbox
    logger.info("Fetching patients from Cerner sandbox")

    patients = []
    for raw_patient in connector.fetch_patients():
        patient = patient_transform.transform(raw_patient)
        if patient:
            patients.append(patient)
            logger.info(
                "Patient",
                id=patient.source_patient_id,
                name=f"{patient.first_name} {patient.last_name}",
                gender=patient.gender,
            )

        if len(patients) >= 5:  # Limit for demo
            break

    # Fetch encounters for first patient
    if patients:
        first_patient_id = patients[0].source_patient_id
        logger.info("Fetching encounters", patient_id=first_patient_id)

        for raw_encounter in connector.fetch_encounters(patient_ids=[first_patient_id]):
            encounter = encounter_transform.transform(raw_encounter)
            if encounter:
                logger.info(
                    "Encounter",
                    id=encounter.source_encounter_id,
                    type=encounter.encounter_type,
                    class_=encounter.encounter_class,
                )

    return patients


def run_production_example():
    """
    Example of connecting to production Cerner instance.

    Note: This requires valid credentials and won't run without proper setup.
    """
    CERNER_TENANT_ID = os.getenv("CERNER_TENANT_ID")
    CERNER_CLIENT_ID = os.getenv("CERNER_CLIENT_ID")
    CERNER_CLIENT_SECRET = os.getenv("CERNER_CLIENT_SECRET")

    if not all([CERNER_TENANT_ID, CERNER_CLIENT_ID, CERNER_CLIENT_SECRET]):
        logger.info("Production credentials not configured, skipping")
        return

    logger.info("Connecting to Cerner Production", tenant_id=CERNER_TENANT_ID)

    connector = FHIRConnector(
        base_url=f"https://fhir-ehr.cerner.com/r4/{CERNER_TENANT_ID}",
        auth_method="oauth2",
        client_id=CERNER_CLIENT_ID,
        client_secret=CERNER_CLIENT_SECRET,
        token_url=f"https://authorization.cerner.com/tenants/{CERNER_TENANT_ID}/protocols/oauth2/profiles/smart-v1/token",
    )

    # Fetch recent data
    since = datetime.now(timezone.utc) - timedelta(days=1)

    patient_transform = PatientTransform()
    lab_transform = LabResultTransform()

    # Process patients
    for raw_patient in connector.fetch_patients(since=since):
        patient = patient_transform.transform(raw_patient)
        if patient:
            logger.info(
                "Processed patient",
                mrn=patient.mrn,
                age_group=patient.age_group,
            )

    # Process lab results
    for raw_lab in connector.fetch_lab_results(since=since):
        lab = lab_transform.transform(raw_lab)
        if lab:
            logger.info(
                "Processed lab",
                test=lab.test_name,
                value=lab.result_value,
                abnormal=lab.is_abnormal,
            )


def load_to_database_example():
    """
    Example of loading Cerner data into the analytics database.

    This demonstrates the full ETL flow from Cerner to PostgreSQL.
    """
    logger.info("Running database load example")

    # Get database session
    try:
        session = get_session()
    except Exception as e:
        logger.warning("Database not available, skipping load example", error=str(e))
        return

    loader = PostgresLoader(session)

    # Use sandbox for demo
    connector = FHIRConnector(
        base_url=CERNER_SANDBOX_URL,
        auth_method="none",
    )

    patient_transform = PatientTransform()

    # Collect batch of patients
    batch = []
    for raw_patient in connector.fetch_patients():
        patient = patient_transform.transform(raw_patient)
        if patient:
            batch.append(patient.model_dump())

        if len(batch) >= 10:
            break

    if batch:
        logger.info("Loading patients to database", count=len(batch))
        try:
            loader.upsert_batch("staging.patients", batch)
            session.commit()
            logger.info("Database load completed")
        except Exception as e:
            session.rollback()
            logger.error("Database load failed", error=str(e))


def main():
    """Run Cerner integration examples."""
    print("\n" + "=" * 50)
    print("Cerner FHIR Integration Examples")
    print("=" * 50)

    # Run sandbox demo (always works)
    print("\n1. Cerner Sandbox Demo")
    print("-" * 30)
    patients = run_sandbox_demo()
    print(f"   Processed {len(patients)} patients from sandbox")

    # Run production example (requires credentials)
    print("\n2. Production Example")
    print("-" * 30)
    run_production_example()

    # Run database load example (requires database)
    print("\n3. Database Load Example")
    print("-" * 30)
    load_to_database_example()

    print("\n" + "=" * 50)
    print("Examples completed")
    print("=" * 50)


if __name__ == "__main__":
    main()
