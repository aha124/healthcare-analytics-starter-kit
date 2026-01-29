"""Encounter/Visit transformation module."""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


class EncounterModel(BaseModel):
    """Validated encounter data model."""

    source_id: str = Field(..., description="Source system encounter ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_type: str | None = Field(default=None, max_length=50)
    encounter_class: str | None = Field(default=None, max_length=50)
    status: str | None = Field(default=None, max_length=30)
    admission_date: datetime | None = Field(default=None)
    discharge_date: datetime | None = Field(default=None)
    location: str | None = Field(default=None, max_length=200)
    department: str | None = Field(default=None, max_length=200)
    facility: str | None = Field(default=None, max_length=200)
    attending_provider: str | None = Field(default=None, max_length=200)
    admit_source: str | None = Field(default=None, max_length=100)
    discharge_disposition: str | None = Field(default=None, max_length=100)
    primary_diagnosis_code: str | None = Field(default=None, max_length=20)
    drg_code: str | None = Field(default=None, max_length=10)
    financial_class: str | None = Field(default=None, max_length=50)

    @field_validator("encounter_type", mode="before")
    @classmethod
    def normalize_encounter_type(cls, v: Any) -> str | None:
        """Normalize encounter type to standard values."""
        if not v:
            return None
        v = str(v).lower().strip()
        mapping = {
            "i": "inpatient",
            "inpatient": "inpatient",
            "ip": "inpatient",
            "o": "outpatient",
            "outpatient": "outpatient",
            "op": "outpatient",
            "e": "emergency",
            "emergency": "emergency",
            "ed": "emergency",
            "er": "emergency",
            "observation": "observation",
            "obs": "observation",
            "ambulatory": "ambulatory",
            "amb": "ambulatory",
            "telehealth": "telehealth",
            "virtual": "telehealth",
            "recurring": "recurring",
            "series": "recurring",
        }
        return mapping.get(v, v)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str | None:
        """Normalize encounter status."""
        if not v:
            return None
        v = str(v).lower().strip()
        mapping = {
            "planned": "planned",
            "scheduled": "planned",
            "arrived": "arrived",
            "checked-in": "arrived",
            "triaged": "triaged",
            "in-progress": "in_progress",
            "active": "in_progress",
            "onleave": "on_leave",
            "finished": "finished",
            "completed": "finished",
            "discharged": "finished",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "no-show": "no_show",
            "noshow": "no_show",
            "entered-in-error": "error",
        }
        return mapping.get(v, v)

    @field_validator("admission_date", "discharge_date", mode="before")
    @classmethod
    def parse_datetime(cls, v: Any) -> datetime | None:
        """Parse various datetime formats."""
        if not v:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%m/%d/%Y %H:%M:%S",
                "%m/%d/%Y",
            ]:
                try:
                    return datetime.strptime(v.split(".")[0].split("+")[0], fmt)
                except ValueError:
                    continue
        return None

    @model_validator(mode="after")
    def validate_dates(self) -> "EncounterModel":
        """Validate date logic."""
        if self.admission_date and self.discharge_date:
            if self.discharge_date < self.admission_date:
                # Swap if discharge is before admission (data error)
                self.admission_date, self.discharge_date = (
                    self.discharge_date,
                    self.admission_date,
                )
        return self


class EncountersTransform:
    """
    Transform raw encounter data into standardized format.

    This transform handles:
    - Encounter type normalization
    - Status standardization
    - Length of stay calculation
    - ED throughput metrics
    - Readmission flagging

    Example:
        >>> transform = EncountersTransform()
        >>> raw = {"source_id": "E123", "patient_id": "P456", "encounter_type": "IP"}
        >>> result = transform.transform(raw)
        >>> print(result["encounter_type"])
        inpatient
    """

    def __init__(self, readmission_window_days: int = 30):
        """
        Initialize the transform.

        Args:
            readmission_window_days: Days to consider for readmission flagging.
        """
        self.readmission_window_days = readmission_window_days
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw encounter record.

        Args:
            raw_data: Raw encounter data dictionary.

        Returns:
            Transformed and validated encounter data.
        """
        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "patient_id": str(raw_data.get("patient_id", "")),
            "encounter_type": raw_data.get("encounter_type") or raw_data.get("class"),
            "encounter_class": raw_data.get("encounter_class"),
            "status": raw_data.get("status"),
            "admission_date": raw_data.get("admission_date") or raw_data.get("arrival_date"),
            "discharge_date": raw_data.get("discharge_date") or raw_data.get("departure_date"),
            "location": raw_data.get("location"),
            "department": raw_data.get("department") or raw_data.get("unit"),
            "facility": raw_data.get("facility") or raw_data.get("hospital"),
            "attending_provider": raw_data.get("attending_provider") or raw_data.get("provider"),
            "admit_source": raw_data.get("admit_source"),
            "discharge_disposition": raw_data.get("discharge_disposition"),
            "primary_diagnosis_code": raw_data.get("primary_diagnosis_code"),
            "drg_code": raw_data.get("drg_code"),
            "financial_class": raw_data.get("financial_class") or raw_data.get("payer_class"),
        }

        # Validate with Pydantic
        try:
            validated = EncounterModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            result["length_of_stay_hours"] = self._calculate_los_hours(
                result["admission_date"],
                result["discharge_date"],
            )
            result["length_of_stay_days"] = self._calculate_los_days(
                result["admission_date"],
                result["discharge_date"],
            )
            result["is_inpatient"] = result["encounter_type"] == "inpatient"
            result["is_emergency"] = result["encounter_type"] == "emergency"
            result["is_completed"] = result["status"] in ["finished", "completed", "discharged"]

            # ED-specific metrics
            if result["is_emergency"]:
                result["ed_arrival_hour"] = (
                    result["admission_date"].hour if result["admission_date"] else None
                )
                result["ed_arrival_day_of_week"] = (
                    result["admission_date"].strftime("%A") if result["admission_date"] else None
                )

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for encounter",
                source_id=transformed.get("source_id"),
                error=str(e),
            )
            raise ValueError(f"Encounter validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of encounter records."""
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

    def flag_readmissions(
        self,
        encounters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Flag potential readmissions in encounter list.

        Args:
            encounters: List of encounter dictionaries (must include patient_id, admission_date).

        Returns:
            Encounters with readmission flags added.
        """
        # Group by patient
        by_patient: dict[str, list[dict[str, Any]]] = {}
        for enc in encounters:
            pid = enc.get("patient_id")
            if pid:
                by_patient.setdefault(pid, []).append(enc)

        # Sort each patient's encounters and flag readmissions
        window = timedelta(days=self.readmission_window_days)

        for patient_id, patient_encounters in by_patient.items():
            # Sort by admission date
            sorted_enc = sorted(
                patient_encounters,
                key=lambda x: x.get("admission_date") or datetime.min,
            )

            for i, enc in enumerate(sorted_enc):
                enc["is_readmission"] = False
                enc["days_since_last_discharge"] = None

                if i > 0 and enc.get("admission_date"):
                    prev = sorted_enc[i - 1]
                    prev_discharge = prev.get("discharge_date")

                    if prev_discharge:
                        days_diff = (enc["admission_date"] - prev_discharge).days
                        enc["days_since_last_discharge"] = days_diff

                        if 0 < days_diff <= self.readmission_window_days:
                            enc["is_readmission"] = True

        return encounters

    @staticmethod
    def _calculate_los_hours(
        admission: datetime | None,
        discharge: datetime | None,
    ) -> float | None:
        """Calculate length of stay in hours."""
        if not admission or not discharge:
            return None
        diff = discharge - admission
        return round(diff.total_seconds() / 3600, 2)

    @staticmethod
    def _calculate_los_days(
        admission: datetime | None,
        discharge: datetime | None,
    ) -> float | None:
        """Calculate length of stay in days."""
        if not admission or not discharge:
            return None
        diff = discharge - admission
        return round(diff.total_seconds() / 86400, 2)


class EDThroughputCalculator:
    """Calculate ED throughput metrics from encounters."""

    @staticmethod
    def calculate_metrics(
        ed_encounters: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Calculate ED throughput metrics.

        Args:
            ed_encounters: List of ED encounter dictionaries.

        Returns:
            Dictionary of ED metrics.
        """
        if not ed_encounters:
            return {}

        # Filter to completed encounters with valid times
        completed = [
            e for e in ed_encounters
            if e.get("admission_date") and e.get("discharge_date")
        ]

        if not completed:
            return {}

        # Calculate metrics
        los_hours = [e["length_of_stay_hours"] for e in completed if e.get("length_of_stay_hours")]

        # Count by disposition
        dispositions: dict[str, int] = {}
        for e in completed:
            disp = e.get("discharge_disposition", "unknown")
            dispositions[disp] = dispositions.get(disp, 0) + 1

        # Hourly arrival distribution
        arrival_hours: dict[int, int] = {}
        for e in completed:
            if e.get("admission_date"):
                hour = e["admission_date"].hour
                arrival_hours[hour] = arrival_hours.get(hour, 0) + 1

        return {
            "total_visits": len(completed),
            "avg_los_hours": sum(los_hours) / len(los_hours) if los_hours else None,
            "median_los_hours": sorted(los_hours)[len(los_hours) // 2] if los_hours else None,
            "min_los_hours": min(los_hours) if los_hours else None,
            "max_los_hours": max(los_hours) if los_hours else None,
            "disposition_counts": dispositions,
            "hourly_arrivals": arrival_hours,
            "admitted_count": dispositions.get("admitted", 0),
            "discharged_count": dispositions.get("discharged", 0) + dispositions.get("home", 0),
            "left_ama_count": dispositions.get("ama", 0) + dispositions.get("left_ama", 0),
        }
