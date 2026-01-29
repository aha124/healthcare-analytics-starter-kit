"""Procedure transformation module."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


class ProcedureModel(BaseModel):
    """Validated procedure data model."""

    source_id: str = Field(..., description="Source system procedure ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_id: str | None = Field(default=None, description="Encounter identifier")
    code: str = Field(..., max_length=20, description="Procedure code")
    code_system: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=30)
    performed_date: datetime | None = Field(default=None)
    performer: str | None = Field(default=None, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    laterality: str | None = Field(default=None, max_length=20)
    body_site: str | None = Field(default=None, max_length=100)
    device: str | None = Field(default=None, max_length=200)
    anesthesia_type: str | None = Field(default=None, max_length=50)
    duration_minutes: int | None = Field(default=None, ge=0)

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v: Any) -> str:
        """Normalize procedure code format."""
        if not v:
            raise ValueError("Procedure code is required")
        return str(v).upper().strip().replace(".", "")

    @field_validator("code_system", mode="before")
    @classmethod
    def normalize_code_system(cls, v: Any) -> str | None:
        """Normalize code system identifier."""
        if not v:
            return None
        v = str(v).upper().strip()
        mappings = {
            "CPT": "CPT-4",
            "CPT4": "CPT-4",
            "CPT-4": "CPT-4",
            "HCPCS": "HCPCS",
            "ICD10PCS": "ICD-10-PCS",
            "ICD-10-PCS": "ICD-10-PCS",
            "ICD10-PCS": "ICD-10-PCS",
            "ICD9": "ICD-9-CM",
            "ICD-9": "ICD-9-CM",
            "SNOMED": "SNOMED-CT",
            "SNOMED-CT": "SNOMED-CT",
        }
        return mappings.get(v, v)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str | None:
        """Normalize procedure status."""
        if not v:
            return None
        v = str(v).lower().strip()
        mappings = {
            "preparation": "preparation",
            "prep": "preparation",
            "in-progress": "in_progress",
            "in progress": "in_progress",
            "active": "in_progress",
            "not-done": "not_done",
            "cancelled": "not_done",
            "on-hold": "on_hold",
            "stopped": "stopped",
            "completed": "completed",
            "done": "completed",
            "finished": "completed",
            "entered-in-error": "error",
        }
        return mappings.get(v, v)


class ProceduresTransform:
    """
    Transform raw procedure data into standardized format.

    This transform handles:
    - CPT/HCPCS/ICD-10-PCS code normalization
    - Code system detection
    - Procedure category classification
    - OR procedure flagging
    - Revenue code mapping

    Example:
        >>> transform = ProceduresTransform()
        >>> raw = {"source_id": "PR1", "patient_id": "P1", "code": "99213"}
        >>> result = transform.transform(raw)
        >>> print(result["code_system"])
        CPT-4
    """

    # CPT code ranges for categorization
    CPT_CATEGORIES = {
        (0, 99): "Anesthesia",
        (100, 1999): "Anesthesia",
        (10000, 19999): "Integumentary",
        (20000, 29999): "Musculoskeletal",
        (30000, 32999): "Respiratory",
        (33000, 37999): "Cardiovascular",
        (38000, 38999): "Hemic/Lymphatic",
        (39000, 39599): "Mediastinum/Diaphragm",
        (40000, 49999): "Digestive",
        (50000, 53899): "Urinary",
        (54000, 55899): "Male Genital",
        (55900, 59899): "Female Genital",
        (60000, 60699): "Endocrine",
        (61000, 64999): "Nervous",
        (65000, 68899): "Eye/Ocular",
        (69000, 69979): "Auditory",
        (70000, 79999): "Radiology",
        (80000, 89999): "Pathology/Lab",
        (90000, 99499): "Medicine/E&M",
        (99500, 99607): "Home Services",
    }

    # Surgical/OR procedure indicators
    SURGICAL_CODE_RANGES = [
        (10000, 69999),  # Surgery section
    ]

    def __init__(self):
        """Initialize the transform."""
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw procedure record.

        Args:
            raw_data: Raw procedure data dictionary.

        Returns:
            Transformed and validated procedure data.
        """
        code = str(raw_data.get("code", "")).upper().strip().replace(".", "")
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
            "status": raw_data.get("status"),
            "performed_date": self._parse_datetime(raw_data.get("performed_date")),
            "performer": raw_data.get("performer"),
            "location": raw_data.get("location"),
            "laterality": raw_data.get("laterality"),
            "body_site": raw_data.get("body_site"),
            "device": raw_data.get("device"),
            "anesthesia_type": raw_data.get("anesthesia_type"),
            "duration_minutes": raw_data.get("duration_minutes"),
        }

        # Validate with Pydantic
        try:
            validated = ProcedureModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            if result["code_system"] == "CPT-4":
                result["cpt_category"] = self._get_cpt_category(code)
                result["is_surgical"] = self._is_surgical_procedure(code)
                result["is_evaluation_management"] = code.startswith("99")
            else:
                result["cpt_category"] = None
                result["is_surgical"] = False
                result["is_evaluation_management"] = False

            # Extract day of week for OR scheduling analysis
            if result["performed_date"]:
                result["performed_day_of_week"] = result["performed_date"].strftime("%A")
                result["performed_hour"] = result["performed_date"].hour
            else:
                result["performed_day_of_week"] = None
                result["performed_hour"] = None

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for procedure",
                source_id=transformed.get("source_id"),
                code=code,
                error=str(e),
            )
            raise ValueError(f"Procedure validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of procedure records."""
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
        code = code.upper().strip()

        # CPT-4: 5 digits (some with modifiers like F suffix)
        if code.isdigit() and len(code) == 5:
            return "CPT-4"

        # HCPCS: Letter followed by 4 digits
        if len(code) == 5 and code[0].isalpha() and code[1:].isdigit():
            return "HCPCS"

        # ICD-10-PCS: 7 alphanumeric characters
        if len(code) == 7 and code.isalnum():
            return "ICD-10-PCS"

        # ICD-9-CM Procedure: 2-4 digits
        if code.isdigit() and 2 <= len(code) <= 4:
            return "ICD-9-CM"

        return "UNKNOWN"

    def _get_cpt_category(self, code: str) -> str | None:
        """Get CPT category from code."""
        try:
            code_num = int(code[:5])
            for (start, end), category in self.CPT_CATEGORIES.items():
                if start <= code_num <= end:
                    return category
        except (ValueError, TypeError):
            pass
        return None

    def _is_surgical_procedure(self, code: str) -> bool:
        """Check if code represents a surgical procedure."""
        try:
            code_num = int(code[:5])
            for start, end in self.SURGICAL_CODE_RANGES:
                if start <= code_num <= end:
                    return True
        except (ValueError, TypeError):
            pass
        return False

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse various datetime formats."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time())
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


class ORUtilizationCalculator:
    """Calculate OR utilization metrics from procedure data."""

    @staticmethod
    def calculate_metrics(
        procedures: list[dict[str, Any]],
        available_hours_per_day: float = 10.0,
    ) -> dict[str, Any]:
        """
        Calculate OR utilization metrics.

        Args:
            procedures: List of procedure dictionaries.
            available_hours_per_day: Available OR hours per day.

        Returns:
            Dictionary of OR metrics.
        """
        # Filter to surgical procedures with duration
        surgical = [
            p for p in procedures
            if p.get("is_surgical") and p.get("duration_minutes")
        ]

        if not surgical:
            return {}

        durations = [p["duration_minutes"] for p in surgical]
        total_minutes = sum(durations)

        # Group by day
        by_day: dict[str, list[int]] = {}
        for p in surgical:
            if p.get("performed_date"):
                day = p["performed_date"].strftime("%Y-%m-%d")
                by_day.setdefault(day, []).append(p["duration_minutes"])

        # Calculate daily utilization
        daily_utilization = {}
        for day, day_durations in by_day.items():
            utilized_minutes = sum(day_durations)
            available_minutes = available_hours_per_day * 60
            daily_utilization[day] = round(utilized_minutes / available_minutes * 100, 1)

        return {
            "total_cases": len(surgical),
            "total_or_minutes": total_minutes,
            "avg_case_duration": round(sum(durations) / len(durations), 1),
            "median_case_duration": sorted(durations)[len(durations) // 2],
            "min_case_duration": min(durations),
            "max_case_duration": max(durations),
            "operating_days": len(by_day),
            "avg_daily_utilization_pct": (
                round(sum(daily_utilization.values()) / len(daily_utilization), 1)
                if daily_utilization
                else None
            ),
            "daily_utilization": daily_utilization,
        }
