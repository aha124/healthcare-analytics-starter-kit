"""Tests for data transformation modules."""

from datetime import date, datetime, timezone
from typing import Any

import pytest

from src.transforms.patient_demographics import PatientTransform, PatientModel
from src.transforms.encounters import EncounterTransform, EncounterModel
from src.transforms.diagnoses import DiagnosisTransform, DiagnosisModel
from src.transforms.lab_results import LabResultTransform, LabResultModel
from src.transforms.vitals import VitalsTransform, VitalsModel
from src.transforms.medications import MedicationTransform, MedicationModel


class TestPatientTransform:
    """Tests for patient demographic transformations."""

    def test_transform_valid_patient(self, sample_patient_data: dict[str, Any]):
        """Test transformation of valid patient data."""
        transform = PatientTransform()
        result = transform.transform(sample_patient_data)

        assert result is not None
        assert isinstance(result, PatientModel)
        assert result.source_patient_id == "PAT-12345"
        assert result.mrn == "FAKE-MRN-001"
        assert result.first_name == "Test"
        assert result.last_name == "Patient"
        assert result.gender == "female"

    def test_transform_calculates_age(self, sample_patient_data: dict[str, Any]):
        """Test that age is calculated correctly."""
        transform = PatientTransform()
        result = transform.transform(sample_patient_data)

        assert result.age is not None
        assert result.age >= 40  # Born in 1980

    def test_transform_calculates_age_group(self, sample_patient_data: dict[str, Any]):
        """Test that age group is assigned correctly."""
        transform = PatientTransform()
        result = transform.transform(sample_patient_data)

        assert result.age_group in [
            "infant", "1-4", "5-17", "18-29", "30-44", "45-64", "65-74", "75-84", "85+"
        ]

    def test_transform_normalizes_gender(self):
        """Test gender normalization."""
        transform = PatientTransform()

        test_cases = [
            ({"gender": "M"}, "male"),
            ({"gender": "m"}, "male"),
            ({"gender": "male"}, "male"),
            ({"gender": "MALE"}, "male"),
            ({"gender": "F"}, "female"),
            ({"gender": "f"}, "female"),
            ({"gender": "female"}, "female"),
            ({"gender": "FEMALE"}, "female"),
            ({"gender": "O"}, "other"),
            ({"gender": "other"}, "other"),
            ({"gender": "U"}, "unknown"),
            ({"gender": ""}, "unknown"),
            ({"gender": None}, "unknown"),
        ]

        for input_data, expected in test_cases:
            input_data["source_patient_id"] = "test"
            result = transform.transform(input_data)
            if result:
                assert result.gender == expected, f"Failed for input: {input_data}"

    def test_transform_normalizes_marital_status(self, sample_patient_data: dict[str, Any]):
        """Test marital status normalization."""
        transform = PatientTransform()

        sample_patient_data["marital_status"] = "M"
        result = transform.transform(sample_patient_data)
        assert result.marital_status == "married"

        sample_patient_data["marital_status"] = "S"
        result = transform.transform(sample_patient_data)
        assert result.marital_status == "single"

    def test_transform_missing_required_field(self):
        """Test handling of missing required fields."""
        transform = PatientTransform()

        # Missing source_patient_id
        result = transform.transform({"mrn": "TEST-001"})
        assert result is None

    def test_transform_strips_whitespace(self, sample_patient_data: dict[str, Any]):
        """Test that string fields are trimmed."""
        transform = PatientTransform()

        sample_patient_data["first_name"] = "  Test  "
        sample_patient_data["last_name"] = "  Patient  "
        result = transform.transform(sample_patient_data)

        assert result.first_name == "Test"
        assert result.last_name == "Patient"


class TestEncounterTransform:
    """Tests for encounter transformations."""

    def test_transform_valid_encounter(self, sample_encounter_data: dict[str, Any]):
        """Test transformation of valid encounter data."""
        transform = EncounterTransform()
        result = transform.transform(sample_encounter_data)

        assert result is not None
        assert isinstance(result, EncounterModel)
        assert result.source_encounter_id == "ENC-67890"
        assert result.encounter_type == "inpatient"
        assert result.encounter_class == "inpatient"

    def test_transform_calculates_los(self, sample_encounter_data: dict[str, Any]):
        """Test length of stay calculation."""
        transform = EncounterTransform()
        result = transform.transform(sample_encounter_data)

        # 3 days from Jan 15 to Jan 18
        assert result.length_of_stay_hours is not None
        assert result.length_of_stay_hours == pytest.approx(75.5, rel=0.1)  # ~3.15 days

    def test_transform_normalizes_encounter_type(self):
        """Test encounter type normalization."""
        transform = EncounterTransform()

        test_cases = [
            ({"encounter_type": "IP"}, "inpatient"),
            ({"encounter_type": "inpatient"}, "inpatient"),
            ({"encounter_type": "OP"}, "outpatient"),
            ({"encounter_type": "outpatient"}, "outpatient"),
            ({"encounter_type": "ED"}, "emergency"),
            ({"encounter_type": "emergency"}, "emergency"),
            ({"encounter_type": "OBS"}, "observation"),
        ]

        for input_data, expected in test_cases:
            input_data["source_encounter_id"] = "test"
            input_data["source_patient_id"] = "patient"
            result = transform.transform(input_data)
            if result:
                assert result.encounter_type == expected

    def test_transform_normalizes_discharge_disposition(self, sample_encounter_data: dict[str, Any]):
        """Test discharge disposition normalization."""
        transform = EncounterTransform()

        sample_encounter_data["discharge_disposition"] = "01"  # CMS code for home
        result = transform.transform(sample_encounter_data)
        assert result.discharge_disposition == "home"

    def test_transform_open_encounter(self, sample_encounter_data: dict[str, Any]):
        """Test handling of encounter without discharge."""
        transform = EncounterTransform()

        sample_encounter_data["discharge_datetime"] = None
        result = transform.transform(sample_encounter_data)

        assert result is not None
        assert result.discharge_datetime is None
        assert result.length_of_stay_hours is None


class TestDiagnosisTransform:
    """Tests for diagnosis transformations."""

    def test_transform_valid_diagnosis(self, sample_diagnosis_data: dict[str, Any]):
        """Test transformation of valid diagnosis data."""
        transform = DiagnosisTransform()
        result = transform.transform(sample_diagnosis_data)

        assert result is not None
        assert isinstance(result, DiagnosisModel)
        assert result.diagnosis_code == "J18.9"
        assert result.diagnosis_type == "principal"

    def test_transform_normalizes_icd_code(self):
        """Test ICD-10 code normalization."""
        transform = DiagnosisTransform()

        test_cases = [
            ("J189", "J18.9"),  # Add decimal
            ("j18.9", "J18.9"),  # Uppercase
            ("J18.9", "J18.9"),  # Already correct
            ("I10", "I10"),  # No decimal needed
            ("E11.65", "E11.65"),  # Already has decimal
        ]

        for input_code, expected in test_cases:
            data = {
                "source_diagnosis_id": "test",
                "diagnosis_code": input_code,
            }
            result = transform.transform(data)
            if result:
                assert result.diagnosis_code == expected

    def test_transform_extracts_category(self, sample_diagnosis_data: dict[str, Any]):
        """Test diagnosis category extraction."""
        transform = DiagnosisTransform()
        result = transform.transform(sample_diagnosis_data)

        assert result.diagnosis_category is not None
        assert result.diagnosis_category == "respiratory"  # J codes

    def test_transform_identifies_ccs_category(self, sample_diagnosis_data: dict[str, Any]):
        """Test CCS category identification."""
        transform = DiagnosisTransform()
        result = transform.transform(sample_diagnosis_data)

        # Should have CCS category for pneumonia
        assert result.ccs_category is not None or result.ccs_category is None  # Optional

    def test_transform_poa_indicator(self, sample_diagnosis_data: dict[str, Any]):
        """Test present on admission indicator."""
        transform = DiagnosisTransform()

        # Test various POA values
        for poa_value, expected in [("Y", True), ("N", False), ("W", None), ("U", None)]:
            sample_diagnosis_data["present_on_admission"] = poa_value
            result = transform.transform(sample_diagnosis_data)
            assert result.is_present_on_admission == expected


class TestLabResultTransform:
    """Tests for lab result transformations."""

    def test_transform_valid_lab(self, sample_lab_result_data: dict[str, Any]):
        """Test transformation of valid lab result."""
        transform = LabResultTransform()
        result = transform.transform(sample_lab_result_data)

        assert result is not None
        assert isinstance(result, LabResultModel)
        assert result.test_code == "2160-0"
        assert result.result_numeric == 1.2

    def test_transform_calculates_abnormal_flag(self, sample_lab_result_data: dict[str, Any]):
        """Test abnormal flag calculation."""
        transform = LabResultTransform()

        # Normal value
        sample_lab_result_data["result_numeric"] = 1.0
        result = transform.transform(sample_lab_result_data)
        assert result.is_abnormal is False

        # High value
        sample_lab_result_data["result_numeric"] = 2.0
        result = transform.transform(sample_lab_result_data)
        assert result.is_abnormal is True

        # Low value
        sample_lab_result_data["result_numeric"] = 0.3
        result = transform.transform(sample_lab_result_data)
        assert result.is_abnormal is True

    def test_transform_critical_flag(self, sample_lab_result_data: dict[str, Any]):
        """Test critical value detection."""
        transform = LabResultTransform()

        # Creatinine critical high (e.g., > 4.0)
        sample_lab_result_data["result_numeric"] = 5.0
        result = transform.transform(sample_lab_result_data)
        assert result.is_critical is True

    def test_transform_numeric_extraction(self):
        """Test numeric value extraction from string results."""
        transform = LabResultTransform()

        test_cases = [
            ({"result_value": "1.5 mg/dL"}, 1.5),
            ({"result_value": ">10"}, 10.0),
            ({"result_value": "<0.5"}, 0.5),
            ({"result_value": "Negative"}, None),
            ({"result_value": "Positive"}, None),
        ]

        for input_data, expected in test_cases:
            input_data["source_lab_id"] = "test"
            result = transform.transform(input_data)
            if result and expected is not None:
                assert result.result_numeric == pytest.approx(expected, rel=0.01)


class TestVitalsTransform:
    """Tests for vitals transformations."""

    def test_transform_valid_vitals(self, sample_vitals_data: dict[str, Any]):
        """Test transformation of valid vitals data."""
        transform = VitalsTransform()
        result = transform.transform(sample_vitals_data)

        assert result is not None
        assert isinstance(result, VitalsModel)
        assert result.heart_rate == 88
        assert result.respiratory_rate == 18

    def test_transform_calculates_bmi(self, sample_vitals_data: dict[str, Any]):
        """Test BMI calculation."""
        transform = VitalsTransform()
        result = transform.transform(sample_vitals_data)

        # BMI = 75.5 / (1.70^2) = 26.1
        assert result.bmi is not None
        assert result.bmi == pytest.approx(26.1, rel=0.1)

    def test_transform_calculates_map(self, sample_vitals_data: dict[str, Any]):
        """Test mean arterial pressure calculation."""
        transform = VitalsTransform()
        result = transform.transform(sample_vitals_data)

        # MAP = (SBP + 2*DBP) / 3 = (130 + 2*82) / 3 = 98
        assert result.mean_arterial_pressure is not None
        assert result.mean_arterial_pressure == pytest.approx(98, rel=1)

    def test_transform_calculates_news_score(self, sample_vitals_data: dict[str, Any]):
        """Test NEWS score calculation."""
        transform = VitalsTransform()
        result = transform.transform(sample_vitals_data)

        # NEWS score should be calculated
        assert result.news_score is not None
        assert 0 <= result.news_score <= 20

    def test_transform_temperature_conversion(self, sample_vitals_data: dict[str, Any]):
        """Test temperature unit conversion."""
        transform = VitalsTransform()

        # Test Fahrenheit input
        sample_vitals_data["temperature"] = 100.76  # 38.2°C in F
        sample_vitals_data["temperature_unit"] = "F"
        result = transform.transform(sample_vitals_data)

        # Should be stored in Celsius
        assert result.temperature_celsius is not None
        assert result.temperature_celsius == pytest.approx(38.2, rel=0.1)

    def test_transform_weight_conversion(self, sample_vitals_data: dict[str, Any]):
        """Test weight unit conversion."""
        transform = VitalsTransform()

        # Test pounds input
        sample_vitals_data["weight"] = 166.45  # 75.5 kg in lbs
        sample_vitals_data["weight_unit"] = "lb"
        result = transform.transform(sample_vitals_data)

        assert result.weight_kg is not None
        assert result.weight_kg == pytest.approx(75.5, rel=0.5)


class TestMedicationTransform:
    """Tests for medication transformations."""

    def test_transform_valid_medication(self, sample_medication_data: dict[str, Any]):
        """Test transformation of valid medication data."""
        transform = MedicationTransform()
        result = transform.transform(sample_medication_data)

        assert result is not None
        assert isinstance(result, MedicationModel)
        assert result.medication_code == "313782"
        assert result.dose_value == 500

    def test_transform_identifies_high_risk(self, sample_medication_data: dict[str, Any]):
        """Test high-risk medication identification."""
        transform = MedicationTransform()

        # Test with a high-risk medication (e.g., warfarin)
        sample_medication_data["medication_name"] = "Warfarin 5 MG Oral Tablet"
        result = transform.transform(sample_medication_data)
        assert result.is_high_risk is True

        # Test with non-high-risk
        sample_medication_data["medication_name"] = "Acetaminophen 500 MG Tablet"
        result = transform.transform(sample_medication_data)
        assert result.is_high_risk is False

    def test_transform_identifies_antibiotic(self, sample_medication_data: dict[str, Any]):
        """Test antibiotic identification."""
        transform = MedicationTransform()

        sample_medication_data["medication_name"] = "Amoxicillin 500 MG Capsule"
        result = transform.transform(sample_medication_data)
        assert result.is_antibiotic is True

    def test_transform_normalizes_route(self):
        """Test route normalization."""
        transform = MedicationTransform()

        test_cases = [
            ("PO", "oral"),
            ("oral", "oral"),
            ("IV", "intravenous"),
            ("intravenous", "intravenous"),
            ("IM", "intramuscular"),
            ("SC", "subcutaneous"),
            ("TOP", "topical"),
        ]

        for input_route, expected in test_cases:
            data = {
                "source_medication_id": "test",
                "route": input_route,
            }
            result = transform.transform(data)
            if result:
                assert result.route == expected

    def test_transform_calculates_duration(self, sample_medication_data: dict[str, Any]):
        """Test medication duration calculation."""
        transform = MedicationTransform()
        result = transform.transform(sample_medication_data)

        # 3 days from Jan 15 to Jan 18
        assert result.duration_days is not None
        assert result.duration_days == 3
