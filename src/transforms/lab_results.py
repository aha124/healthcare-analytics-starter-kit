"""Laboratory results transformation module."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


# Common lab reference ranges (simplified - real implementation would use age/sex specific)
REFERENCE_RANGES = {
    # Chemistry
    "GLUCOSE": {"low": 70, "high": 100, "unit": "mg/dL", "critical_low": 50, "critical_high": 400},
    "BUN": {"low": 7, "high": 20, "unit": "mg/dL"},
    "CREATININE": {"low": 0.7, "high": 1.3, "unit": "mg/dL", "critical_high": 10},
    "SODIUM": {"low": 136, "high": 145, "unit": "mEq/L", "critical_low": 120, "critical_high": 160},
    "POTASSIUM": {"low": 3.5, "high": 5.0, "unit": "mEq/L", "critical_low": 2.5, "critical_high": 6.5},
    "CHLORIDE": {"low": 98, "high": 106, "unit": "mEq/L"},
    "CO2": {"low": 23, "high": 29, "unit": "mEq/L"},
    "CALCIUM": {"low": 8.5, "high": 10.5, "unit": "mg/dL", "critical_low": 6.0, "critical_high": 13.0},
    "ALBUMIN": {"low": 3.5, "high": 5.0, "unit": "g/dL"},
    "BILIRUBIN": {"low": 0.1, "high": 1.2, "unit": "mg/dL"},
    "ALT": {"low": 7, "high": 56, "unit": "U/L"},
    "AST": {"low": 10, "high": 40, "unit": "U/L"},
    "ALP": {"low": 44, "high": 147, "unit": "U/L"},

    # Hematology
    "WBC": {"low": 4.5, "high": 11.0, "unit": "K/uL", "critical_low": 2.0, "critical_high": 30.0},
    "RBC": {"low": 4.5, "high": 5.5, "unit": "M/uL"},
    "HEMOGLOBIN": {"low": 12.0, "high": 17.5, "unit": "g/dL", "critical_low": 7.0},
    "HEMATOCRIT": {"low": 36, "high": 50, "unit": "%", "critical_low": 20},
    "PLATELET": {"low": 150, "high": 400, "unit": "K/uL", "critical_low": 50, "critical_high": 1000},

    # Coagulation
    "PT": {"low": 11, "high": 13.5, "unit": "seconds"},
    "INR": {"low": 0.8, "high": 1.1, "unit": "ratio"},
    "PTT": {"low": 25, "high": 35, "unit": "seconds"},

    # Cardiac
    "TROPONIN": {"low": 0, "high": 0.04, "unit": "ng/mL", "critical_high": 0.1},
    "BNP": {"low": 0, "high": 100, "unit": "pg/mL"},

    # Metabolic
    "HBA1C": {"low": 4.0, "high": 5.6, "unit": "%"},
    "TSH": {"low": 0.4, "high": 4.0, "unit": "mIU/L"},

    # Blood Gas
    "PH": {"low": 7.35, "high": 7.45, "unit": "", "critical_low": 7.2, "critical_high": 7.6},
    "PCO2": {"low": 35, "high": 45, "unit": "mmHg"},
    "PO2": {"low": 80, "high": 100, "unit": "mmHg", "critical_low": 40},
    "LACTATE": {"low": 0.5, "high": 2.2, "unit": "mmol/L", "critical_high": 4.0},
}


class LabResultModel(BaseModel):
    """Validated lab result data model."""

    source_id: str = Field(..., description="Source system result ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_id: str | None = Field(default=None, description="Encounter identifier")
    code: str = Field(..., max_length=50, description="Lab test code (LOINC preferred)")
    code_system: str | None = Field(default=None, max_length=50)
    test_name: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    value: float | None = Field(default=None)
    value_string: str | None = Field(default=None, max_length=500)
    value_unit: str | None = Field(default=None, max_length=50)
    reference_range_low: float | None = Field(default=None)
    reference_range_high: float | None = Field(default=None)
    reference_range_text: str | None = Field(default=None, max_length=200)
    interpretation: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=30)
    effective_date: datetime | None = Field(default=None)
    issued_date: datetime | None = Field(default=None)
    specimen_type: str | None = Field(default=None, max_length=100)
    ordering_provider: str | None = Field(default=None, max_length=200)
    performing_lab: str | None = Field(default=None, max_length=200)

    @field_validator("interpretation", mode="before")
    @classmethod
    def normalize_interpretation(cls, v: Any) -> str | None:
        """Normalize interpretation/abnormal flag."""
        if not v:
            return None
        v = str(v).upper().strip()
        mappings = {
            "N": "normal",
            "NORMAL": "normal",
            "NL": "normal",
            "A": "abnormal",
            "ABNORMAL": "abnormal",
            "ABN": "abnormal",
            "H": "high",
            "HIGH": "high",
            "HH": "critical_high",
            "CRITICAL HIGH": "critical_high",
            "L": "low",
            "LOW": "low",
            "LL": "critical_low",
            "CRITICAL LOW": "critical_low",
            "C": "critical",
            "CRITICAL": "critical",
            "AA": "critical",
        }
        return mappings.get(v, v.lower())

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str | None:
        """Normalize result status."""
        if not v:
            return None
        v = str(v).lower().strip()
        mappings = {
            "registered": "registered",
            "preliminary": "preliminary",
            "final": "final",
            "f": "final",
            "amended": "amended",
            "corrected": "corrected",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "entered-in-error": "error",
        }
        return mappings.get(v, v)


class LabResultsTransform:
    """
    Transform raw lab result data into standardized format.

    This transform handles:
    - LOINC code normalization
    - Numeric value parsing
    - Reference range application
    - Abnormal flag calculation
    - Critical value detection
    - Panel grouping

    Example:
        >>> transform = LabResultsTransform()
        >>> raw = {"source_id": "L1", "patient_id": "P1", "code": "2345-7", "value": "95"}
        >>> result = transform.transform(raw)
        >>> print(result["is_abnormal"])
        False
    """

    def __init__(self):
        """Initialize the transform."""
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw lab result record.

        Args:
            raw_data: Raw lab result data dictionary.

        Returns:
            Transformed and validated lab result data.
        """
        # Parse numeric value
        raw_value = raw_data.get("value")
        numeric_value = self._parse_numeric_value(raw_value)
        value_string = str(raw_value) if raw_value is not None and numeric_value is None else None

        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "patient_id": str(raw_data.get("patient_id", "")),
            "encounter_id": raw_data.get("encounter_id"),
            "code": str(raw_data.get("code", "")).strip(),
            "code_system": raw_data.get("code_system"),
            "test_name": raw_data.get("test_name") or raw_data.get("description"),
            "category": raw_data.get("category"),
            "value": numeric_value,
            "value_string": value_string,
            "value_unit": raw_data.get("value_unit") or raw_data.get("unit"),
            "reference_range_low": self._parse_numeric_value(raw_data.get("reference_range_low")),
            "reference_range_high": self._parse_numeric_value(raw_data.get("reference_range_high")),
            "reference_range_text": raw_data.get("reference_range_text") or raw_data.get("reference_range"),
            "interpretation": raw_data.get("interpretation") or raw_data.get("abnormal_flag"),
            "status": raw_data.get("status"),
            "effective_date": self._parse_datetime(raw_data.get("effective_date")),
            "issued_date": self._parse_datetime(raw_data.get("issued_date")),
            "specimen_type": raw_data.get("specimen_type"),
            "ordering_provider": raw_data.get("ordering_provider"),
            "performing_lab": raw_data.get("performing_lab"),
        }

        # Validate with Pydantic
        try:
            validated = LabResultModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            test_name_upper = (result["test_name"] or "").upper()

            # Try to apply default reference ranges if not provided
            if result["value"] is not None:
                ref_range = self._get_default_reference_range(test_name_upper)
                if ref_range:
                    if result["reference_range_low"] is None:
                        result["reference_range_low"] = ref_range.get("low")
                    if result["reference_range_high"] is None:
                        result["reference_range_high"] = ref_range.get("high")

            # Calculate abnormal flags
            result["is_abnormal"] = self._is_abnormal(
                result["value"],
                result["reference_range_low"],
                result["reference_range_high"],
            )
            result["is_critical"] = self._is_critical(
                result["value"],
                test_name_upper,
            )
            result["delta_from_normal"] = self._calculate_delta(
                result["value"],
                result["reference_range_low"],
                result["reference_range_high"],
            )

            # Categorize test type
            result["test_category"] = self._categorize_test(test_name_upper)

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for lab result",
                source_id=transformed.get("source_id"),
                code=transformed.get("code"),
                error=str(e),
            )
            raise ValueError(f"Lab result validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of lab result records."""
        valid = []
        errors = []

        for record in records:
            try:
                transformed = self.transform(record)
                valid.append(transformed)
            except Exception as e:
                if skip_invalid:
                    errors.append({
                        "source_id": record.get("source_id"),
                        "code": record.get("code"),
                        "error": str(e),
                    })
                else:
                    raise

        self._logger.info(
            "Batch transform complete",
            total=len(records),
            valid=len(valid),
            errors=len(errors),
        )

        return valid, errors

    @staticmethod
    def _parse_numeric_value(value: Any) -> float | None:
        """Parse numeric value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # Remove common prefixes/suffixes
            cleaned = value.strip().lstrip("<>").rstrip("%")
            try:
                return float(Decimal(cleaned))
            except (InvalidOperation, ValueError):
                return None
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse various datetime formats."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y",
            ]:
                try:
                    return datetime.strptime(value.split(".")[0].split("+")[0], fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _get_default_reference_range(test_name: str) -> dict[str, Any] | None:
        """Get default reference range for common tests."""
        # Search for matching test
        for key, ranges in REFERENCE_RANGES.items():
            if key in test_name:
                return ranges
        return None

    @staticmethod
    def _is_abnormal(
        value: float | None,
        low: float | None,
        high: float | None,
    ) -> bool | None:
        """Determine if value is outside reference range."""
        if value is None:
            return None
        if low is not None and value < low:
            return True
        if high is not None and value > high:
            return True
        if low is not None or high is not None:
            return False
        return None

    @staticmethod
    def _is_critical(value: float | None, test_name: str) -> bool | None:
        """Determine if value is in critical range."""
        if value is None:
            return None

        ref = None
        for key, ranges in REFERENCE_RANGES.items():
            if key in test_name:
                ref = ranges
                break

        if not ref:
            return None

        critical_low = ref.get("critical_low")
        critical_high = ref.get("critical_high")

        if critical_low is not None and value < critical_low:
            return True
        if critical_high is not None and value > critical_high:
            return True

        return False

    @staticmethod
    def _calculate_delta(
        value: float | None,
        low: float | None,
        high: float | None,
    ) -> float | None:
        """Calculate how far value is from normal range."""
        if value is None:
            return None

        if low is not None and value < low:
            return round(value - low, 2)
        if high is not None and value > high:
            return round(value - high, 2)
        return 0.0

    @staticmethod
    def _categorize_test(test_name: str) -> str:
        """Categorize test into broad category."""
        categories = {
            "chemistry": ["GLUCOSE", "BUN", "CREATININE", "SODIUM", "POTASSIUM", "CHLORIDE", "CO2", "CALCIUM", "ALBUMIN", "BILIRUBIN", "ALT", "AST", "ALP"],
            "hematology": ["WBC", "RBC", "HEMOGLOBIN", "HEMATOCRIT", "PLATELET", "MCV", "MCH", "MCHC", "RDW"],
            "coagulation": ["PT", "INR", "PTT", "FIBRINOGEN", "D-DIMER"],
            "cardiac": ["TROPONIN", "BNP", "CK-MB", "CK"],
            "metabolic": ["HBA1C", "TSH", "T3", "T4", "LIPID", "CHOLESTEROL", "TRIGLYCERIDE", "HDL", "LDL"],
            "blood_gas": ["PH", "PCO2", "PO2", "LACTATE", "BICARBONATE"],
            "urinalysis": ["UA", "URINE", "PROTEIN", "SPECIFIC GRAVITY"],
            "infectious": ["CULTURE", "PROCALCITONIN", "CRP", "ESR"],
        }

        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in test_name:
                    return category

        return "other"
