"""Diagnosis transformation module."""

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


# ICD-10 Chapter mapping
ICD10_CHAPTERS = {
    "A": "Infectious and parasitic diseases",
    "B": "Infectious and parasitic diseases",
    "C": "Neoplasms",
    "D": "Blood diseases / Neoplasms",
    "E": "Endocrine, nutritional and metabolic diseases",
    "F": "Mental and behavioral disorders",
    "G": "Nervous system diseases",
    "H": "Eye and ear diseases",
    "I": "Circulatory system diseases",
    "J": "Respiratory system diseases",
    "K": "Digestive system diseases",
    "L": "Skin diseases",
    "M": "Musculoskeletal diseases",
    "N": "Genitourinary system diseases",
    "O": "Pregnancy and childbirth",
    "P": "Perinatal conditions",
    "Q": "Congenital malformations",
    "R": "Abnormal findings",
    "S": "Injury and poisoning",
    "T": "Injury and poisoning",
    "V": "External causes",
    "W": "External causes",
    "X": "External causes",
    "Y": "External causes",
    "Z": "Health status factors",
}


class DiagnosisModel(BaseModel):
    """Validated diagnosis data model."""

    source_id: str = Field(..., description="Source system diagnosis ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_id: str | None = Field(default=None, description="Encounter identifier")
    code: str = Field(..., max_length=20, description="Diagnosis code")
    code_system: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    diagnosis_type: str | None = Field(default=None, max_length=50)
    clinical_status: str | None = Field(default=None, max_length=30)
    verification_status: str | None = Field(default=None, max_length=30)
    severity: str | None = Field(default=None, max_length=30)
    onset_date: date | None = Field(default=None)
    abatement_date: date | None = Field(default=None)
    recorded_date: date | None = Field(default=None)
    rank: int | None = Field(default=None, ge=1, description="Diagnosis rank/sequence")
    present_on_admission: str | None = Field(default=None, max_length=5)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v: Any) -> str:
        """Normalize diagnosis code format."""
        if not v:
            raise ValueError("Diagnosis code is required")
        code = str(v).upper().strip()
        # Remove periods for consistent storage
        code = code.replace(".", "")
        return code

    @field_validator("code_system", mode="before")
    @classmethod
    def normalize_code_system(cls, v: Any) -> str | None:
        """Normalize code system identifier."""
        if not v:
            return None
        v = str(v).upper().strip()
        mappings = {
            "ICD10": "ICD-10-CM",
            "ICD-10": "ICD-10-CM",
            "ICD10CM": "ICD-10-CM",
            "ICD-10-CM": "ICD-10-CM",
            "ICD9": "ICD-9-CM",
            "ICD-9": "ICD-9-CM",
            "ICD9CM": "ICD-9-CM",
            "ICD-9-CM": "ICD-9-CM",
            "SNOMED": "SNOMED-CT",
            "SNOMED-CT": "SNOMED-CT",
            "SNOMEDCT": "SNOMED-CT",
        }
        return mappings.get(v, v)

    @field_validator("diagnosis_type", mode="before")
    @classmethod
    def normalize_diagnosis_type(cls, v: Any) -> str | None:
        """Normalize diagnosis type."""
        if not v:
            return None
        v = str(v).lower().strip()
        mappings = {
            "principal": "principal",
            "primary": "principal",
            "p": "principal",
            "1": "principal",
            "admitting": "admitting",
            "a": "admitting",
            "secondary": "secondary",
            "s": "secondary",
            "2": "secondary",
            "working": "working",
            "final": "final",
            "discharge": "final",
        }
        return mappings.get(v, v)

    @field_validator("present_on_admission", mode="before")
    @classmethod
    def normalize_poa(cls, v: Any) -> str | None:
        """Normalize present on admission indicator."""
        if not v:
            return None
        v = str(v).upper().strip()
        mappings = {
            "Y": "Y",
            "YES": "Y",
            "TRUE": "Y",
            "1": "Y",
            "N": "N",
            "NO": "N",
            "FALSE": "N",
            "0": "N",
            "U": "U",
            "UNKNOWN": "U",
            "W": "W",
            "UNABLE": "W",
        }
        return mappings.get(v, v)


class DiagnosesTransform:
    """
    Transform raw diagnosis data into standardized format.

    This transform handles:
    - ICD-10/ICD-9 code normalization
    - Code system detection
    - Chapter/category extraction
    - CCS grouping (Clinical Classifications Software)
    - Comorbidity flagging (Elixhauser/Charlson)

    Example:
        >>> transform = DiagnosesTransform()
        >>> raw = {"source_id": "D1", "patient_id": "P1", "code": "E11.9"}
        >>> result = transform.transform(raw)
        >>> print(result["icd10_chapter"])
        Endocrine, nutritional and metabolic diseases
    """

    # Common comorbidity codes for flagging
    DIABETES_CODES = {"E10", "E11", "E13"}
    HYPERTENSION_CODES = {"I10", "I11", "I12", "I13"}
    CHF_CODES = {"I50"}
    COPD_CODES = {"J44"}
    CKD_CODES = {"N18"}
    CANCER_CODES = {"C"}  # All C codes are neoplasms

    def __init__(self):
        """Initialize the transform."""
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw diagnosis record.

        Args:
            raw_data: Raw diagnosis data dictionary.

        Returns:
            Transformed and validated diagnosis data.
        """
        # Detect code system if not provided
        code = str(raw_data.get("code", "")).upper().strip()
        code_system = raw_data.get("code_system")

        if not code_system:
            code_system = self._detect_code_system(code)

        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "patient_id": str(raw_data.get("patient_id", "")),
            "encounter_id": raw_data.get("encounter_id"),
            "code": code,
            "code_system": code_system,
            "description": raw_data.get("description"),
            "diagnosis_type": raw_data.get("diagnosis_type") or raw_data.get("type"),
            "clinical_status": raw_data.get("clinical_status"),
            "verification_status": raw_data.get("verification_status"),
            "severity": raw_data.get("severity"),
            "onset_date": self._parse_date(raw_data.get("onset_date")),
            "abatement_date": self._parse_date(raw_data.get("abatement_date")),
            "recorded_date": self._parse_date(raw_data.get("recorded_date")),
            "rank": raw_data.get("rank") or raw_data.get("sequence"),
            "present_on_admission": raw_data.get("present_on_admission") or raw_data.get("poa"),
        }

        # Validate with Pydantic
        try:
            validated = DiagnosisModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            normalized_code = result["code"].replace(".", "")

            # ICD-10 specific fields
            if result["code_system"] == "ICD-10-CM":
                result["icd10_chapter"] = self._get_icd10_chapter(normalized_code)
                result["icd10_category"] = normalized_code[:3] if len(normalized_code) >= 3 else None
                result["icd10_subcategory"] = (
                    normalized_code[:4] if len(normalized_code) >= 4 else None
                )

            # Comorbidity flags
            result["is_diabetes"] = self._is_comorbidity(normalized_code, self.DIABETES_CODES)
            result["is_hypertension"] = self._is_comorbidity(normalized_code, self.HYPERTENSION_CODES)
            result["is_chf"] = self._is_comorbidity(normalized_code, self.CHF_CODES)
            result["is_copd"] = self._is_comorbidity(normalized_code, self.COPD_CODES)
            result["is_ckd"] = self._is_comorbidity(normalized_code, self.CKD_CODES)
            result["is_cancer"] = normalized_code.startswith("C")

            # Format code with period for display
            result["code_formatted"] = self._format_icd_code(normalized_code)

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for diagnosis",
                source_id=transformed.get("source_id"),
                code=code,
                error=str(e),
            )
            raise ValueError(f"Diagnosis validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of diagnosis records."""
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
    def _detect_code_system(code: str) -> str:
        """Detect code system from code format."""
        code = code.upper().strip().replace(".", "")

        # ICD-10-CM: Letter followed by digits (e.g., E11, J449, S52011A)
        if re.match(r"^[A-TV-Z]\d", code):
            return "ICD-10-CM"

        # ICD-10-PCS: 7 alphanumeric characters
        if re.match(r"^[A-HJ-NP-Z0-9]{7}$", code):
            return "ICD-10-PCS"

        # ICD-9-CM: 3-5 digits, possibly with V or E prefix
        if re.match(r"^[VE]?\d{3,5}$", code):
            return "ICD-9-CM"

        # SNOMED: Large numeric codes
        if re.match(r"^\d{6,18}$", code):
            return "SNOMED-CT"

        return "UNKNOWN"

    @staticmethod
    def _get_icd10_chapter(code: str) -> str | None:
        """Get ICD-10 chapter description from code."""
        if not code:
            return None
        first_char = code[0].upper()
        return ICD10_CHAPTERS.get(first_char)

    @staticmethod
    def _is_comorbidity(code: str, code_prefixes: set[str]) -> bool:
        """Check if code matches any comorbidity prefix."""
        code = code.upper().replace(".", "")
        for prefix in code_prefixes:
            if code.startswith(prefix):
                return True
        return False

    @staticmethod
    def _format_icd_code(code: str) -> str:
        """Format ICD code with appropriate period."""
        code = code.replace(".", "")
        if len(code) > 3:
            return f"{code[:3]}.{code[3:]}"
        return code

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        """Parse various date formats."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None


class ComorbidityCalculator:
    """Calculate comorbidity indices from diagnosis lists."""

    # Charlson Comorbidity Index weights
    CHARLSON_WEIGHTS = {
        "myocardial_infarction": 1,
        "congestive_heart_failure": 1,
        "peripheral_vascular": 1,
        "cerebrovascular": 1,
        "dementia": 1,
        "chronic_pulmonary": 1,
        "rheumatic": 1,
        "peptic_ulcer": 1,
        "mild_liver": 1,
        "diabetes_uncomplicated": 1,
        "diabetes_complicated": 2,
        "hemiplegia": 2,
        "renal": 2,
        "malignancy": 2,
        "moderate_severe_liver": 3,
        "metastatic_tumor": 6,
        "aids": 6,
    }

    @classmethod
    def calculate_charlson_index(
        cls,
        diagnoses: list[dict[str, Any]],
        age: int | None = None,
    ) -> dict[str, Any]:
        """
        Calculate Charlson Comorbidity Index.

        Args:
            diagnoses: List of diagnosis dictionaries with 'code' field.
            age: Patient age for age adjustment.

        Returns:
            Dictionary with CCI score and component flags.
        """
        codes = {d.get("code", "").upper().replace(".", "") for d in diagnoses}

        components = {
            "myocardial_infarction": any(c.startswith(("I21", "I22", "I25")) for c in codes),
            "congestive_heart_failure": any(c.startswith("I50") for c in codes),
            "peripheral_vascular": any(c.startswith(("I70", "I71", "I73")) for c in codes),
            "cerebrovascular": any(c.startswith(("I60", "I61", "I62", "I63", "I64", "I65", "I66", "I67", "I68", "I69")) for c in codes),
            "dementia": any(c.startswith(("F00", "F01", "F02", "F03", "G30")) for c in codes),
            "chronic_pulmonary": any(c.startswith(("J40", "J41", "J42", "J43", "J44", "J45", "J46", "J47")) for c in codes),
            "rheumatic": any(c.startswith(("M05", "M06", "M32", "M33", "M34")) for c in codes),
            "peptic_ulcer": any(c.startswith(("K25", "K26", "K27", "K28")) for c in codes),
            "mild_liver": any(c.startswith(("K70", "K73", "K74")) for c in codes),
            "diabetes_uncomplicated": any(c.startswith(("E10", "E11", "E13")) and not c.endswith(("2", "3", "4", "5")) for c in codes),
            "diabetes_complicated": any(c.startswith(("E10", "E11", "E13")) and c.endswith(("2", "3", "4", "5")) for c in codes),
            "hemiplegia": any(c.startswith(("G81", "G82", "G83")) for c in codes),
            "renal": any(c.startswith("N18") for c in codes),
            "malignancy": any(c.startswith("C") and not c.startswith("C77") for c in codes),
            "moderate_severe_liver": any(c.startswith(("K72", "K76")) for c in codes),
            "metastatic_tumor": any(c.startswith(("C77", "C78", "C79", "C80")) for c in codes),
            "aids": any(c.startswith("B20") for c in codes),
        }

        # Calculate base score
        score = sum(
            cls.CHARLSON_WEIGHTS[condition]
            for condition, present in components.items()
            if present
        )

        # Age adjustment
        age_points = 0
        if age:
            if age >= 50:
                age_points = (age - 40) // 10

        return {
            "charlson_score": score,
            "charlson_score_age_adjusted": score + age_points,
            "components": components,
            "age_points": age_points,
        }
