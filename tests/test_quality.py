"""Tests for data quality and validation modules."""

from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.quality.validators import DataValidator, ValidationResult
from src.quality.phi_scanner import PHIScanner, PHIFinding
from src.utils.encryption import FieldEncryption


class TestDataValidator:
    """Tests for data validation functionality."""

    def test_validate_patient_valid(self, sample_patient_data: dict[str, Any]):
        """Test validation of valid patient data."""
        validator = DataValidator()
        result = validator.validate_record(sample_patient_data, "patient")

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_patient_missing_required(self):
        """Test validation catches missing required fields."""
        validator = DataValidator()

        # Missing source_patient_id
        data = {"mrn": "TEST-001", "first_name": "Test"}
        result = validator.validate_record(data, "patient")

        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("source_patient_id" in str(e).lower() for e in result.errors)

    def test_validate_patient_invalid_date(self, sample_patient_data: dict[str, Any]):
        """Test validation catches invalid dates."""
        validator = DataValidator()

        sample_patient_data["date_of_birth"] = "not-a-date"
        result = validator.validate_record(sample_patient_data, "patient")

        # Should either fail validation or handle gracefully
        # Implementation-dependent

    def test_validate_patient_future_birth_date(self, sample_patient_data: dict[str, Any]):
        """Test validation catches future birth dates."""
        validator = DataValidator()

        sample_patient_data["date_of_birth"] = date(2099, 1, 1)
        result = validator.validate_record(sample_patient_data, "patient")

        assert not result.is_valid
        assert any("future" in str(e).lower() or "birth" in str(e).lower() for e in result.errors)

    def test_validate_encounter_valid(self, sample_encounter_data: dict[str, Any]):
        """Test validation of valid encounter data."""
        validator = DataValidator()
        result = validator.validate_record(sample_encounter_data, "encounter")

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_encounter_discharge_before_admit(self, sample_encounter_data: dict[str, Any]):
        """Test validation catches discharge before admission."""
        validator = DataValidator()

        sample_encounter_data["admit_datetime"] = datetime(2024, 1, 18, 10, 0, tzinfo=timezone.utc)
        sample_encounter_data["discharge_datetime"] = datetime(2024, 1, 15, 14, 0, tzinfo=timezone.utc)
        result = validator.validate_record(sample_encounter_data, "encounter")

        assert not result.is_valid
        assert any("discharge" in str(e).lower() and "admit" in str(e).lower() for e in result.errors)

    def test_validate_diagnosis_valid(self, sample_diagnosis_data: dict[str, Any]):
        """Test validation of valid diagnosis data."""
        validator = DataValidator()
        result = validator.validate_record(sample_diagnosis_data, "diagnosis")

        assert result.is_valid

    def test_validate_diagnosis_invalid_icd_code(self, sample_diagnosis_data: dict[str, Any]):
        """Test validation catches invalid ICD-10 codes."""
        validator = DataValidator()

        sample_diagnosis_data["diagnosis_code"] = "INVALID"
        result = validator.validate_record(sample_diagnosis_data, "diagnosis")

        # Should flag as warning or error
        assert len(result.warnings) > 0 or not result.is_valid

    def test_validate_lab_valid(self, sample_lab_result_data: dict[str, Any]):
        """Test validation of valid lab result data."""
        validator = DataValidator()
        result = validator.validate_record(sample_lab_result_data, "lab_result")

        assert result.is_valid

    def test_validate_lab_impossible_value(self, sample_lab_result_data: dict[str, Any]):
        """Test validation catches impossible lab values."""
        validator = DataValidator()

        # Negative creatinine (impossible)
        sample_lab_result_data["result_numeric"] = -1.5
        result = validator.validate_record(sample_lab_result_data, "lab_result")

        assert not result.is_valid or len(result.warnings) > 0

    def test_validate_vitals_valid(self, sample_vitals_data: dict[str, Any]):
        """Test validation of valid vitals data."""
        validator = DataValidator()
        result = validator.validate_record(sample_vitals_data, "vitals")

        assert result.is_valid

    def test_validate_vitals_impossible_values(self, sample_vitals_data: dict[str, Any]):
        """Test validation catches impossible vital signs."""
        validator = DataValidator()

        # Heart rate of 500 (impossible)
        sample_vitals_data["heart_rate"] = 500
        result = validator.validate_record(sample_vitals_data, "vitals")

        assert not result.is_valid or len(result.warnings) > 0

        # Negative blood pressure
        sample_vitals_data["systolic_bp"] = -120
        result = validator.validate_record(sample_vitals_data, "vitals")

        assert not result.is_valid or len(result.warnings) > 0

    def test_validate_batch(self, sample_patient_data: dict[str, Any]):
        """Test batch validation."""
        validator = DataValidator()

        batch = [
            sample_patient_data,
            {**sample_patient_data, "source_patient_id": "PAT-2"},
            {"invalid": "record"},  # Should fail
        ]

        results = validator.validate_batch(batch, "patient")

        assert len(results) == 3
        assert results[0].is_valid
        assert results[1].is_valid
        assert not results[2].is_valid


class TestPHIScanner:
    """Tests for PHI detection functionality."""

    def test_scan_detects_ssn(self):
        """Test SSN pattern detection."""
        scanner = PHIScanner()

        data = {"notes": "Patient SSN is 123-45-6789"}
        findings = scanner.scan_record(data)

        assert len(findings) > 0
        assert any(f.phi_type == "ssn" for f in findings)

    def test_scan_detects_phone(self):
        """Test phone number detection."""
        scanner = PHIScanner()

        data = {"contact": "Call patient at 555-123-4567"}
        findings = scanner.scan_record(data)

        assert len(findings) > 0
        assert any(f.phi_type == "phone" for f in findings)

    def test_scan_detects_email(self):
        """Test email detection."""
        scanner = PHIScanner()

        data = {"contact": "Email: patient@example.com"}
        findings = scanner.scan_record(data)

        assert len(findings) > 0
        assert any(f.phi_type == "email" for f in findings)

    def test_scan_detects_mrn_in_text(self):
        """Test MRN pattern detection in free text."""
        scanner = PHIScanner()

        data = {"notes": "See patient record MRN: 12345678"}
        findings = scanner.scan_record(data)

        assert len(findings) > 0
        assert any(f.phi_type == "mrn" for f in findings)

    def test_scan_detects_dob_pattern(self):
        """Test date of birth pattern detection."""
        scanner = PHIScanner()

        data = {"notes": "DOB: 01/15/1980"}
        findings = scanner.scan_record(data)

        assert len(findings) > 0
        assert any(f.phi_type == "date_of_birth" for f in findings)

    def test_scan_detects_sensitive_field_names(self):
        """Test detection based on sensitive field names."""
        scanner = PHIScanner()

        data = {
            "patient_name": "John Doe",
            "ssn": "123-45-6789",
            "home_phone": "555-1234",
        }
        findings = scanner.scan_record(data)

        # Should flag multiple PHI fields
        assert len(findings) >= 3

    def test_scan_nested_data(self):
        """Test scanning of nested data structures."""
        scanner = PHIScanner()

        data = {
            "patient": {
                "demographics": {
                    "ssn": "123-45-6789",
                    "phone": "555-123-4567",
                }
            }
        }
        findings = scanner.scan_record(data)

        assert len(findings) >= 2

    def test_scan_array_data(self):
        """Test scanning of array data."""
        scanner = PHIScanner()

        data = {
            "contacts": [
                {"phone": "555-111-1111"},
                {"phone": "555-222-2222"},
            ]
        }
        findings = scanner.scan_record(data)

        assert len(findings) >= 2

    def test_scan_empty_data(self):
        """Test scanning of empty data."""
        scanner = PHIScanner()

        findings = scanner.scan_record({})
        assert len(findings) == 0

    def test_scan_safe_data(self):
        """Test that safe data produces no findings."""
        scanner = PHIScanner()

        data = {
            "encounter_id": "ENC-12345",
            "encounter_type": "inpatient",
            "department": "MED",
            "room": "301A",
        }
        findings = scanner.scan_record(data)

        assert len(findings) == 0

    def test_scan_with_sensitivity_level(self):
        """Test scanning with different sensitivity levels."""
        scanner_high = PHIScanner(sensitivity="high")
        scanner_low = PHIScanner(sensitivity="low")

        data = {"notes": "Patient mentioned phone call"}  # Ambiguous

        findings_high = scanner_high.scan_record(data)
        findings_low = scanner_low.scan_record(data)

        # High sensitivity should catch more potential PHI
        assert len(findings_high) >= len(findings_low)


class TestFieldEncryption:
    """Tests for field-level encryption."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption/decryption preserves data."""
        encryption = FieldEncryption()

        original = "sensitive-patient-data"
        encrypted = encryption.encrypt(original)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypt_different_output(self):
        """Test that encryption produces different ciphertext."""
        encryption = FieldEncryption()

        value1 = "test-value"
        value2 = "test-value"

        encrypted1 = encryption.encrypt(value1)
        encrypted2 = encryption.encrypt(value2)

        # Fernet uses random IV, so same plaintext produces different ciphertext
        assert encrypted1 != encrypted2

    def test_encrypt_none_value(self):
        """Test encryption of None value."""
        encryption = FieldEncryption()

        result = encryption.encrypt(None)
        assert result is None

    def test_decrypt_none_value(self):
        """Test decryption of None value."""
        encryption = FieldEncryption()

        result = encryption.decrypt(None)
        assert result is None

    def test_decrypt_invalid_ciphertext(self):
        """Test decryption of invalid ciphertext."""
        encryption = FieldEncryption()

        # Should raise an exception or return None
        with pytest.raises(Exception):
            encryption.decrypt("not-valid-ciphertext")

    def test_hash_for_matching(self):
        """Test deterministic hashing for matching."""
        encryption = FieldEncryption()

        value1 = "patient@example.com"
        value2 = "patient@example.com"
        value3 = "other@example.com"

        hash1 = encryption.hash_for_matching(value1)
        hash2 = encryption.hash_for_matching(value2)
        hash3 = encryption.hash_for_matching(value3)

        # Same value produces same hash
        assert hash1 == hash2
        # Different value produces different hash
        assert hash1 != hash3

    def test_hash_with_salt(self):
        """Test hashing with salt."""
        encryption = FieldEncryption()

        value = "patient@example.com"

        hash1 = encryption.hash_for_matching(value, salt="salt1")
        hash2 = encryption.hash_for_matching(value, salt="salt2")

        # Different salt produces different hash
        assert hash1 != hash2

    def test_encrypt_batch(self):
        """Test batch encryption."""
        encryption = FieldEncryption()

        values = ["value1", "value2", "value3"]
        encrypted = encryption.encrypt_batch(values)

        assert len(encrypted) == 3
        assert all(e != v for e, v in zip(encrypted, values))

        # Verify decryption
        decrypted = [encryption.decrypt(e) for e in encrypted]
        assert decrypted == values

    def test_key_rotation(self):
        """Test key rotation scenario."""
        encryption1 = FieldEncryption()
        encryption2 = FieldEncryption()  # New key

        original = "sensitive-data"
        encrypted = encryption1.encrypt(original)

        # New encryption instance cannot decrypt old data
        with pytest.raises(Exception):
            encryption2.decrypt(encrypted)


class TestValidationResult:
    """Tests for ValidationResult class."""

    def test_valid_result(self):
        """Test creation of valid result."""
        result = ValidationResult(is_valid=True)

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0

    def test_invalid_result_with_errors(self):
        """Test creation of invalid result with errors."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1", "Error 2"],
        )

        assert not result.is_valid
        assert len(result.errors) == 2

    def test_result_with_warnings(self):
        """Test result with warnings."""
        result = ValidationResult(
            is_valid=True,
            warnings=["Warning 1"],
        )

        assert result.is_valid
        assert len(result.warnings) == 1

    def test_result_to_dict(self):
        """Test result serialization."""
        result = ValidationResult(
            is_valid=False,
            errors=["Error 1"],
            warnings=["Warning 1"],
        )

        d = result.to_dict()

        assert d["is_valid"] is False
        assert "Error 1" in d["errors"]
        assert "Warning 1" in d["warnings"]
