"""Tests for data source connectors."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.connectors.fhir_connector import FHIRConnector
from src.connectors.hl7_connector import HL7Connector
from src.connectors.csv_connector import CSVConnector


class TestFHIRConnector:
    """Tests for FHIR API connector."""

    def test_init_with_basic_auth(self):
        """Test connector initialization with basic auth."""
        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="basic",
            username="user",
            password="pass",
        )
        assert connector.base_url == "https://fhir.example.com/r4"
        assert connector.auth_method == "basic"

    def test_init_with_bearer_token(self):
        """Test connector initialization with bearer token."""
        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="bearer",
            access_token="test-token-123",
        )
        assert connector.auth_method == "bearer"

    def test_normalize_patient(self, sample_fhir_patient: dict[str, Any]):
        """Test FHIR patient resource normalization."""
        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
        )

        result = connector._normalize_patient(sample_fhir_patient)

        assert result["source_patient_id"] == "fhir-patient-123"
        assert result["mrn"] == "FAKE-MRN-001"
        assert result["first_name"] == "John"
        assert result["last_name"] == "TestPatient"
        assert result["gender"] == "male"
        assert result["date_of_birth"] == "1985-03-20"
        assert result["address_city"] == "Healthcare City"
        assert result["address_state"] == "NY"

    def test_normalize_encounter(self, sample_fhir_encounter: dict[str, Any]):
        """Test FHIR encounter resource normalization."""
        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
        )

        result = connector._normalize_encounter(sample_fhir_encounter)

        assert result["source_encounter_id"] == "fhir-encounter-456"
        assert result["source_patient_id"] == "fhir-patient-123"
        assert result["encounter_class"] == "inpatient"
        assert "admit_datetime" in result
        assert "discharge_datetime" in result

    @patch("httpx.Client")
    def test_fetch_patients_pagination(self, mock_client_class):
        """Test patient fetching with pagination."""
        # Setup mock responses
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        # First page response
        page1_response = MagicMock()
        page1_response.status_code = 200
        page1_response.json.return_value = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 2,
            "link": [
                {"relation": "next", "url": "https://fhir.example.com/r4/Patient?page=2"}
            ],
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-1",
                        "name": [{"family": "Test1", "given": ["User1"]}],
                    }
                }
            ],
        }

        # Second page response (no next link)
        page2_response = MagicMock()
        page2_response.status_code = 200
        page2_response.json.return_value = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": 2,
            "entry": [
                {
                    "resource": {
                        "resourceType": "Patient",
                        "id": "patient-2",
                        "name": [{"family": "Test2", "given": ["User2"]}],
                    }
                }
            ],
        }

        mock_client.get.side_effect = [page1_response, page2_response]

        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
        )

        # Collect all patients
        patients = list(connector.fetch_patients())

        assert len(patients) == 2
        assert patients[0]["source_patient_id"] == "patient-1"
        assert patients[1]["source_patient_id"] == "patient-2"

    def test_build_search_params_with_date(self):
        """Test search parameter building with date filter."""
        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
        )

        since = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        params = connector._build_search_params("Patient", since=since)

        assert "_lastUpdated" in params
        assert params["_lastUpdated"] == "ge2024-01-01T00:00:00+00:00"


class TestHL7Connector:
    """Tests for HL7 v2.x message connector."""

    def test_parse_adt_message(self, sample_hl7_adt_message: str):
        """Test parsing of HL7 ADT message."""
        connector = HL7Connector(message_directory=Path("/tmp/hl7"))

        result = connector._parse_message(sample_hl7_adt_message)

        assert result is not None
        assert result["message_type"] == "ADT"
        assert result["trigger_event"] == "A01"

    def test_extract_patient_from_adt(self, sample_hl7_adt_message: str):
        """Test patient extraction from ADT message."""
        connector = HL7Connector(message_directory=Path("/tmp/hl7"))

        parsed = connector._parse_message(sample_hl7_adt_message)
        patient = connector._extract_patient(parsed)

        assert patient is not None
        assert patient["mrn"] == "FAKE-MRN-002"
        assert patient["last_name"] == "TestHL7"
        assert patient["first_name"] == "Jane"
        assert patient["gender"] == "F"
        assert patient["address_state"] == "TX"

    def test_extract_encounter_from_adt(self, sample_hl7_adt_message: str):
        """Test encounter extraction from ADT message."""
        connector = HL7Connector(message_directory=Path("/tmp/hl7"))

        parsed = connector._parse_message(sample_hl7_adt_message)
        encounter = connector._extract_encounter(parsed)

        assert encounter is not None
        assert encounter["encounter_class"] == "inpatient"
        assert encounter["department_id"] == "MED"
        assert encounter["room_number"] == "301"

    def test_extract_diagnosis_from_adt(self, sample_hl7_adt_message: str):
        """Test diagnosis extraction from ADT message."""
        connector = HL7Connector(message_directory=Path("/tmp/hl7"))

        parsed = connector._parse_message(sample_hl7_adt_message)
        diagnoses = connector._extract_diagnoses(parsed)

        assert len(diagnoses) == 1
        assert diagnoses[0]["diagnosis_code"] == "J18.9"
        assert diagnoses[0]["diagnosis_description"] == "Pneumonia"

    def test_invalid_message_handling(self):
        """Test handling of invalid HL7 messages."""
        connector = HL7Connector(message_directory=Path("/tmp/hl7"))

        result = connector._parse_message("This is not a valid HL7 message")

        assert result is None


class TestCSVConnector:
    """Tests for CSV file connector."""

    def test_init_with_directory(self, tmp_path: Path):
        """Test connector initialization with directory."""
        connector = CSVConnector(data_directory=tmp_path)
        assert connector.data_directory == tmp_path

    def test_read_patient_csv(self, tmp_path: Path):
        """Test reading patient data from CSV."""
        # Create test CSV file
        csv_content = """source_patient_id,mrn,first_name,last_name,date_of_birth,gender
PAT-001,FAKE-001,Test,User1,1980-01-15,M
PAT-002,FAKE-002,Jane,User2,1990-05-20,F
"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content)

        connector = CSVConnector(data_directory=tmp_path)
        patients = list(connector.fetch_patients())

        assert len(patients) == 2
        assert patients[0]["mrn"] == "FAKE-001"
        assert patients[1]["first_name"] == "Jane"

    def test_read_encounters_csv(self, tmp_path: Path):
        """Test reading encounter data from CSV."""
        csv_content = """source_encounter_id,source_patient_id,encounter_type,admit_datetime,discharge_datetime
ENC-001,PAT-001,inpatient,2024-01-15 10:00:00,2024-01-18 14:00:00
ENC-002,PAT-002,emergency,2024-01-16 08:30:00,2024-01-16 15:00:00
"""
        csv_file = tmp_path / "encounters.csv"
        csv_file.write_text(csv_content)

        connector = CSVConnector(data_directory=tmp_path)
        encounters = list(connector.fetch_encounters())

        assert len(encounters) == 2
        assert encounters[0]["encounter_type"] == "inpatient"
        assert encounters[1]["encounter_type"] == "emergency"

    def test_missing_file_handling(self, tmp_path: Path):
        """Test handling of missing CSV files."""
        connector = CSVConnector(data_directory=tmp_path)

        # Should return empty iterator, not raise error
        patients = list(connector.fetch_patients())
        assert patients == []

    def test_malformed_csv_handling(self, tmp_path: Path):
        """Test handling of malformed CSV data."""
        csv_content = """source_patient_id,mrn,first_name
PAT-001,FAKE-001
PAT-002,FAKE-002,Jane,ExtraField
"""
        csv_file = tmp_path / "patients.csv"
        csv_file.write_text(csv_content)

        connector = CSVConnector(data_directory=tmp_path)

        # Should handle gracefully
        patients = list(connector.fetch_patients())
        # Implementation decides whether to skip or include partial rows


class TestConnectorAuthentication:
    """Tests for connector authentication mechanisms."""

    @patch("httpx.Client")
    def test_oauth2_token_refresh(self, mock_client_class):
        """Test OAuth2 token refresh flow."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        # Token endpoint response
        token_response = MagicMock()
        token_response.status_code = 200
        token_response.json.return_value = {
            "access_token": "new-token-123",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_client.post.return_value = token_response

        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="oauth2",
            client_id="test-client",
            client_secret="test-secret",
            token_url="https://auth.example.com/oauth/token",
        )

        # Trigger authentication
        connector._authenticate()

        assert connector.access_token == "new-token-123"


class TestConnectorErrorHandling:
    """Tests for connector error handling."""

    @patch("httpx.Client")
    def test_retry_on_server_error(self, mock_client_class):
        """Test retry logic on server errors."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        # First call fails, second succeeds
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = Exception("Server Error")

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [],
        }

        mock_client.get.side_effect = [error_response, success_response]

        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
            max_retries=3,
        )

        # Should succeed after retry
        patients = list(connector.fetch_patients())
        assert patients == []

    @patch("httpx.Client")
    def test_rate_limit_handling(self, mock_client_class):
        """Test rate limit (429) handling."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.headers = {"Retry-After": "1"}

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "resourceType": "Bundle",
            "entry": [],
        }

        mock_client.get.side_effect = [rate_limit_response, success_response]

        connector = FHIRConnector(
            base_url="https://fhir.example.com/r4",
            auth_method="none",
        )

        # Should handle rate limiting
        patients = list(connector.fetch_patients())
        assert mock_client.get.call_count >= 2
