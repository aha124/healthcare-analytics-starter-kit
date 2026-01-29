"""Data quality validators for healthcare analytics."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Callable

from config.logging_config import get_logger

logger = get_logger(__name__)


class ValidationSeverity(str, Enum):
    """Validation result severity levels."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationRule:
    """Definition of a validation rule."""

    name: str
    description: str
    validator: Callable[[Any], bool]
    severity: ValidationSeverity = ValidationSeverity.ERROR
    field: str | None = None
    error_message: str | None = None


@dataclass
class ValidationResult:
    """Result of a validation check."""

    is_valid: bool
    rule_name: str
    field: str | None
    severity: ValidationSeverity
    message: str
    value: Any = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_valid": self.is_valid,
            "rule_name": self.rule_name,
            "field": self.field,
            "severity": self.severity.value,
            "message": self.message,
        }


@dataclass
class ValidationReport:
    """Summary report of all validation results."""

    total_records: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    results: list[ValidationResult] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage."""
        if self.total_records == 0:
            return 0.0
        return (self.invalid_records / self.total_records) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "invalid_records": self.invalid_records,
            "error_rate_pct": round(self.error_rate, 2),
            "errors": self.errors,
            "warnings": self.warnings,
        }


class DataValidator:
    """
    Data quality validator for healthcare records.

    This validator provides:
    - Pre-built rules for common healthcare data
    - Custom rule support
    - Batch validation with reporting
    - Field-level and record-level validation

    Example:
        >>> validator = DataValidator()
        >>> validator.add_rule(ValidationRule(
        ...     name="valid_mrn",
        ...     description="MRN must not be empty",
        ...     field="mrn",
        ...     validator=lambda x: x is not None and len(str(x)) > 0,
        ... ))
        >>> results = validator.validate_record({"mrn": "12345"})
    """

    def __init__(self):
        """Initialize the validator with default rules."""
        self._rules: list[ValidationRule] = []
        self._logger = get_logger(__name__)
        self._add_default_rules()

    def _add_default_rules(self) -> None:
        """Add default validation rules for healthcare data."""
        # Patient rules
        self.add_rule(ValidationRule(
            name="valid_mrn_format",
            description="MRN should not be empty",
            field="mrn",
            validator=lambda x: x is not None and len(str(x).strip()) > 0,
            error_message="MRN is empty or invalid",
        ))

        self.add_rule(ValidationRule(
            name="valid_dob",
            description="Date of birth should be in the past",
            field="date_of_birth",
            validator=self._validate_past_date,
            error_message="Date of birth is in the future",
        ))

        self.add_rule(ValidationRule(
            name="reasonable_dob",
            description="Date of birth should be within 150 years",
            field="date_of_birth",
            validator=lambda x: self._validate_date_range(x, years_back=150),
            severity=ValidationSeverity.WARNING,
            error_message="Date of birth is over 150 years ago",
        ))

        self.add_rule(ValidationRule(
            name="valid_gender",
            description="Gender should be a recognized value",
            field="gender",
            validator=lambda x: x is None or x.lower() in [
                "male", "female", "other", "unknown", "m", "f", "o", "u"
            ],
            severity=ValidationSeverity.WARNING,
            error_message="Gender value not recognized",
        ))

        # Encounter rules
        self.add_rule(ValidationRule(
            name="valid_encounter_dates",
            description="Discharge date should be after admission date",
            validator=self._validate_encounter_dates,
            error_message="Discharge date is before admission date",
        ))

        self.add_rule(ValidationRule(
            name="reasonable_los",
            description="Length of stay should be under 365 days",
            validator=self._validate_reasonable_los,
            severity=ValidationSeverity.WARNING,
            error_message="Length of stay exceeds 365 days",
        ))

        # Diagnosis rules
        self.add_rule(ValidationRule(
            name="valid_icd10_format",
            description="ICD-10 code should match expected format",
            field="code",
            validator=self._validate_icd10_format,
            error_message="ICD-10 code format is invalid",
        ))

        # Lab result rules
        self.add_rule(ValidationRule(
            name="valid_lab_value",
            description="Numeric lab value should be a valid number",
            field="value",
            validator=lambda x: x is None or isinstance(x, (int, float)),
            error_message="Lab value is not a valid number",
        ))

        self.add_rule(ValidationRule(
            name="lab_value_in_range",
            description="Lab value should be within plausible range",
            validator=self._validate_lab_value_range,
            severity=ValidationSeverity.WARNING,
            error_message="Lab value is outside plausible range",
        ))

        # Vital signs rules
        self.add_rule(ValidationRule(
            name="valid_heart_rate",
            description="Heart rate should be between 20 and 300",
            field="heart_rate",
            validator=lambda x: x is None or (20 <= float(x) <= 300),
            error_message="Heart rate is outside valid range (20-300)",
        ))

        self.add_rule(ValidationRule(
            name="valid_blood_pressure",
            description="Blood pressure should be physiologically possible",
            validator=self._validate_blood_pressure,
            error_message="Blood pressure values are invalid",
        ))

        self.add_rule(ValidationRule(
            name="valid_temperature",
            description="Temperature should be between 85°F and 115°F",
            field="temperature",
            validator=lambda x: x is None or (85 <= float(x) <= 115),
            error_message="Temperature is outside valid range",
        ))

        self.add_rule(ValidationRule(
            name="valid_oxygen_saturation",
            description="SpO2 should be between 0 and 100",
            field="oxygen_saturation",
            validator=lambda x: x is None or (0 <= float(x) <= 100),
            error_message="Oxygen saturation is outside valid range (0-100)",
        ))

    def add_rule(self, rule: ValidationRule) -> None:
        """Add a validation rule."""
        self._rules.append(rule)

    def remove_rule(self, rule_name: str) -> None:
        """Remove a validation rule by name."""
        self._rules = [r for r in self._rules if r.name != rule_name]

    def validate_record(
        self,
        record: dict[str, Any],
        rules: list[str] | None = None,
    ) -> list[ValidationResult]:
        """
        Validate a single record against all applicable rules.

        Args:
            record: Record dictionary to validate.
            rules: Optional list of rule names to apply. If None, applies all.

        Returns:
            List of ValidationResult objects.
        """
        results = []

        for rule in self._rules:
            # Skip if not in specified rules
            if rules and rule.name not in rules:
                continue

            # Get value for field-level rules
            if rule.field:
                value = record.get(rule.field)
                try:
                    is_valid = rule.validator(value)
                except Exception:
                    is_valid = False
            else:
                # Record-level validation
                value = record
                try:
                    is_valid = rule.validator(record)
                except Exception:
                    is_valid = False

            if not is_valid:
                results.append(ValidationResult(
                    is_valid=False,
                    rule_name=rule.name,
                    field=rule.field,
                    severity=rule.severity,
                    message=rule.error_message or rule.description,
                    value=value if rule.field else None,
                ))

        return results

    def validate_batch(
        self,
        records: list[dict[str, Any]],
        rules: list[str] | None = None,
        stop_on_first_error: bool = False,
    ) -> ValidationReport:
        """
        Validate a batch of records.

        Args:
            records: List of records to validate.
            rules: Optional list of rule names to apply.
            stop_on_first_error: Stop validation on first error.

        Returns:
            ValidationReport with summary statistics.
        """
        report = ValidationReport(total_records=len(records))

        for record in records:
            results = self.validate_record(record, rules)

            if results:
                report.invalid_records += 1
                report.results.extend(results)

                for result in results:
                    if result.severity == ValidationSeverity.ERROR:
                        report.errors += 1
                    elif result.severity == ValidationSeverity.WARNING:
                        report.warnings += 1

                if stop_on_first_error:
                    break
            else:
                report.valid_records += 1

        self._logger.info(
            "Batch validation complete",
            total=report.total_records,
            valid=report.valid_records,
            invalid=report.invalid_records,
            errors=report.errors,
            warnings=report.warnings,
        )

        return report

    # Validator helper methods

    @staticmethod
    def _validate_past_date(value: Any) -> bool:
        """Validate that a date is in the past."""
        if value is None:
            return True
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value).date()
            except ValueError:
                return False
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            return value <= date.today()
        return False

    @staticmethod
    def _validate_date_range(value: Any, years_back: int = 150) -> bool:
        """Validate that a date is within a reasonable range."""
        if value is None:
            return True
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value).date()
            except ValueError:
                return False
        if isinstance(value, datetime):
            value = value.date()
        if isinstance(value, date):
            min_date = date.today().replace(year=date.today().year - years_back)
            return value >= min_date
        return False

    @staticmethod
    def _validate_encounter_dates(record: dict[str, Any]) -> bool:
        """Validate encounter admission/discharge dates."""
        admission = record.get("admission_date")
        discharge = record.get("discharge_date")

        if admission is None or discharge is None:
            return True

        if isinstance(admission, str):
            admission = datetime.fromisoformat(admission)
        if isinstance(discharge, str):
            discharge = datetime.fromisoformat(discharge)

        return discharge >= admission

    @staticmethod
    def _validate_reasonable_los(record: dict[str, Any]) -> bool:
        """Validate length of stay is reasonable."""
        los_days = record.get("length_of_stay_days")
        if los_days is None:
            return True
        return float(los_days) <= 365

    @staticmethod
    def _validate_icd10_format(code: Any) -> bool:
        """Validate ICD-10 code format."""
        if code is None:
            return True
        code = str(code).upper().strip().replace(".", "")
        # ICD-10-CM: Letter followed by 2-7 alphanumeric characters
        return bool(re.match(r"^[A-TV-Z]\d[A-Z\d]{0,5}$", code))

    @staticmethod
    def _validate_lab_value_range(record: dict[str, Any]) -> bool:
        """Validate lab value is within plausible range based on test type."""
        value = record.get("value")
        if value is None:
            return True

        test_name = (record.get("test_name") or "").upper()

        # Define plausible ranges for common tests
        ranges = {
            "GLUCOSE": (10, 1000),
            "HEMOGLOBIN": (1, 25),
            "CREATININE": (0.1, 30),
            "POTASSIUM": (1, 10),
            "SODIUM": (100, 180),
            "WBC": (0, 100),
        }

        for test, (low, high) in ranges.items():
            if test in test_name:
                return low <= float(value) <= high

        return True

    @staticmethod
    def _validate_blood_pressure(record: dict[str, Any]) -> bool:
        """Validate blood pressure values."""
        systolic = record.get("systolic_bp")
        diastolic = record.get("diastolic_bp")

        if systolic is None and diastolic is None:
            return True

        if systolic is not None:
            if not (40 <= float(systolic) <= 300):
                return False

        if diastolic is not None:
            if not (20 <= float(diastolic) <= 200):
                return False

        if systolic is not None and diastolic is not None:
            if float(diastolic) >= float(systolic):
                return False

        return True
