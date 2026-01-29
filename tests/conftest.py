"""Pytest configuration and fixtures for Healthcare Analytics tests."""

from datetime import date, datetime, timezone
from typing import Any, Generator
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.base import Base


@pytest.fixture(scope="session")
def engine():
    """Create a test database engine using SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Generator[Session, None, None]:
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_patient_data() -> dict[str, Any]:
    """Sample patient data for testing."""
    return {
        "source_patient_id": "PAT-12345",
        "mrn": "FAKE-MRN-001",
        "first_name": "Test",
        "last_name": "Patient",
        "date_of_birth": date(1980, 5, 15),
        "gender": "female",
        "address_line1": "123 Test Street",
        "address_city": "Testville",
        "address_state": "CA",
        "address_zip": "90210",
        "phone_home": "555-123-4567",
        "email": "test.patient@example.com",
        "ssn": "123-45-6789",
        "primary_language": "English",
        "marital_status": "married",
        "race": "white",
        "ethnicity": "not_hispanic",
        "emergency_contact_name": "Emergency Contact",
        "emergency_contact_phone": "555-987-6543",
    }


@pytest.fixture
def sample_encounter_data() -> dict[str, Any]:
    """Sample encounter data for testing."""
    return {
        "source_encounter_id": "ENC-67890",
        "source_patient_id": "PAT-12345",
        "encounter_type": "inpatient",
        "encounter_class": "inpatient",
        "admit_datetime": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "discharge_datetime": datetime(2024, 1, 18, 14, 0, 0, tzinfo=timezone.utc),
        "admit_source": "emergency",
        "discharge_disposition": "home",
        "primary_diagnosis_code": "J18.9",
        "attending_provider_id": "PROV-001",
        "facility_id": "FAC-001",
        "department_id": "MED",
        "room_number": "301A",
        "bed_number": "1",
    }


@pytest.fixture
def sample_diagnosis_data() -> dict[str, Any]:
    """Sample diagnosis data for testing."""
    return {
        "source_diagnosis_id": "DX-11111",
        "source_encounter_id": "ENC-67890",
        "source_patient_id": "PAT-12345",
        "diagnosis_code": "J18.9",
        "diagnosis_code_system": "ICD-10-CM",
        "diagnosis_description": "Pneumonia, unspecified organism",
        "diagnosis_type": "principal",
        "diagnosis_rank": 1,
        "present_on_admission": "Y",
        "diagnosis_datetime": datetime(2024, 1, 15, 11, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_lab_result_data() -> dict[str, Any]:
    """Sample lab result data for testing."""
    return {
        "source_lab_id": "LAB-22222",
        "source_encounter_id": "ENC-67890",
        "source_patient_id": "PAT-12345",
        "test_code": "2160-0",
        "test_code_system": "LOINC",
        "test_name": "Creatinine [Mass/volume] in Serum or Plasma",
        "result_value": "1.2",
        "result_numeric": 1.2,
        "result_unit": "mg/dL",
        "reference_range_low": 0.6,
        "reference_range_high": 1.3,
        "abnormal_flag": None,
        "result_status": "final",
        "collection_datetime": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        "result_datetime": datetime(2024, 1, 15, 14, 0, 0, tzinfo=timezone.utc),
    }


@pytest.fixture
def sample_vitals_data() -> dict[str, Any]:
    """Sample vitals data for testing."""
    return {
        "source_vital_id": "VIT-33333",
        "source_encounter_id": "ENC-67890",
        "source_patient_id": "PAT-12345",
        "vital_datetime": datetime(2024, 1, 15, 10, 45, 0, tzinfo=timezone.utc),
        "heart_rate": 88,
        "respiratory_rate": 18,
        "systolic_bp": 130,
        "diastolic_bp": 82,
        "temperature": 38.2,
        "temperature_unit": "C",
        "oxygen_saturation": 95,
        "weight": 75.5,
        "weight_unit": "kg",
        "height": 170,
        "height_unit": "cm",
        "pain_scale": 3,
    }


@pytest.fixture
def sample_medication_data() -> dict[str, Any]:
    """Sample medication data for testing."""
    return {
        "source_medication_id": "MED-44444",
        "source_encounter_id": "ENC-67890",
        "source_patient_id": "PAT-12345",
        "medication_code": "313782",
        "medication_code_system": "RxNorm",
        "medication_name": "Acetaminophen 500 MG Oral Tablet",
        "dose_value": 500,
        "dose_unit": "mg",
        "route": "oral",
        "frequency": "Q6H",
        "order_datetime": datetime(2024, 1, 15, 11, 30, 0, tzinfo=timezone.utc),
        "start_datetime": datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        "end_datetime": datetime(2024, 1, 18, 12, 0, 0, tzinfo=timezone.utc),
        "status": "active",
        "prescriber_id": "PROV-001",
    }


@pytest.fixture
def sample_fhir_patient() -> dict[str, Any]:
    """Sample FHIR Patient resource for testing."""
    return {
        "resourceType": "Patient",
        "id": "fhir-patient-123",
        "identifier": [
            {
                "type": {"coding": [{"code": "MR"}]},
                "value": "FAKE-MRN-001",
            }
        ],
        "name": [
            {
                "family": "TestPatient",
                "given": ["John", "Robert"],
            }
        ],
        "gender": "male",
        "birthDate": "1985-03-20",
        "address": [
            {
                "line": ["456 FHIR Avenue"],
                "city": "Healthcare City",
                "state": "NY",
                "postalCode": "10001",
            }
        ],
        "telecom": [
            {"system": "phone", "value": "555-FHIR-001", "use": "home"},
            {"system": "email", "value": "john.test@example.com"},
        ],
        "communication": [{"language": {"text": "English"}, "preferred": True}],
        "maritalStatus": {"coding": [{"code": "M"}]},
        "extension": [
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race",
                "extension": [{"valueCoding": {"display": "White"}}],
            },
            {
                "url": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity",
                "extension": [{"valueCoding": {"display": "Not Hispanic"}}],
            },
        ],
    }


@pytest.fixture
def sample_fhir_encounter() -> dict[str, Any]:
    """Sample FHIR Encounter resource for testing."""
    return {
        "resourceType": "Encounter",
        "id": "fhir-encounter-456",
        "status": "finished",
        "class": {"code": "IMP"},
        "type": [{"coding": [{"code": "inpatient"}]}],
        "subject": {"reference": "Patient/fhir-patient-123"},
        "period": {
            "start": "2024-01-15T10:30:00Z",
            "end": "2024-01-18T14:00:00Z",
        },
        "hospitalization": {
            "admitSource": {"coding": [{"code": "emd"}]},
            "dischargeDisposition": {"coding": [{"code": "home"}]},
        },
        "diagnosis": [
            {
                "condition": {"reference": "Condition/dx-123"},
                "use": {"coding": [{"code": "AD"}]},
            }
        ],
        "participant": [
            {
                "type": [{"coding": [{"code": "ATND"}]}],
                "individual": {"reference": "Practitioner/prov-001"},
            }
        ],
        "location": [
            {
                "location": {"reference": "Location/loc-001"},
            }
        ],
    }


@pytest.fixture
def sample_hl7_adt_message() -> str:
    """Sample HL7 v2.x ADT message for testing."""
    return """MSH|^~\\&|EPIC|HOSPITAL|ANALYTICS|WAREHOUSE|20240115103000||ADT^A01|MSG001|P|2.5.1
EVN|A01|20240115103000
PID|1||FAKE-MRN-002^^^HOSPITAL^MR||TestHL7^Jane^Marie||19900715|F|||789 HL7 Street^^Medical Town^TX^75001||555-HL7-0001|||S|||999-88-7777
PV1|1|I|MED^301^A^HOSPITAL||||1234567^Smith^John^A^^^MD|||MED||||ADM|||1234567^Smith^John^A^^^MD|IP||||||||||||||||||HOSPITAL|||20240115103000
DG1|1||J18.9^Pneumonia^ICD10|||A"""


@pytest.fixture
def mock_fhir_response() -> dict[str, Any]:
    """Mock FHIR Bundle response for testing."""
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": 1,
        "entry": [
            {
                "resource": {
                    "resourceType": "Patient",
                    "id": "test-patient",
                    "name": [{"family": "Test", "given": ["User"]}],
                }
            }
        ],
    }


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for testing API calls."""
    client = MagicMock()
    client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"data": []},
    )
    return client
