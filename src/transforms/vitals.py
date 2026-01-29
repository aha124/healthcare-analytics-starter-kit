"""Vital signs transformation module."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


# Vital sign reference ranges
VITAL_RANGES = {
    "heart_rate": {
        "normal_low": 60,
        "normal_high": 100,
        "critical_low": 40,
        "critical_high": 150,
        "unit": "bpm",
    },
    "respiratory_rate": {
        "normal_low": 12,
        "normal_high": 20,
        "critical_low": 8,
        "critical_high": 30,
        "unit": "breaths/min",
    },
    "systolic_bp": {
        "normal_low": 90,
        "normal_high": 120,
        "critical_low": 70,
        "critical_high": 180,
        "unit": "mmHg",
    },
    "diastolic_bp": {
        "normal_low": 60,
        "normal_high": 80,
        "critical_low": 40,
        "critical_high": 120,
        "unit": "mmHg",
    },
    "temperature": {
        "normal_low": 97.0,
        "normal_high": 99.0,
        "critical_low": 95.0,
        "critical_high": 104.0,
        "unit": "°F",
    },
    "oxygen_saturation": {
        "normal_low": 95,
        "normal_high": 100,
        "critical_low": 90,
        "critical_high": 100,
        "unit": "%",
    },
    "pain_score": {
        "normal_low": 0,
        "normal_high": 3,
        "critical_low": 0,
        "critical_high": 10,
        "unit": "0-10",
    },
}


class VitalSignModel(BaseModel):
    """Validated vital sign data model."""

    source_id: str = Field(..., description="Source system vital ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_id: str | None = Field(default=None, description="Encounter identifier")
    recorded_date: datetime | None = Field(default=None)

    # Core vitals
    heart_rate: float | None = Field(default=None, ge=0, le=300)
    respiratory_rate: float | None = Field(default=None, ge=0, le=100)
    systolic_bp: float | None = Field(default=None, ge=0, le=300)
    diastolic_bp: float | None = Field(default=None, ge=0, le=200)
    mean_arterial_pressure: float | None = Field(default=None, ge=0, le=250)
    temperature: float | None = Field(default=None, ge=80, le=115)  # Fahrenheit
    temperature_unit: str = Field(default="F")
    oxygen_saturation: float | None = Field(default=None, ge=0, le=100)
    oxygen_device: str | None = Field(default=None, max_length=100)
    fio2: float | None = Field(default=None, ge=0.21, le=1.0)

    # Additional vitals
    weight: float | None = Field(default=None, ge=0)
    weight_unit: str = Field(default="kg")
    height: float | None = Field(default=None, ge=0)
    height_unit: str = Field(default="cm")
    bmi: float | None = Field(default=None, ge=0, le=100)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    gcs_total: int | None = Field(default=None, ge=3, le=15)
    gcs_eye: int | None = Field(default=None, ge=1, le=4)
    gcs_verbal: int | None = Field(default=None, ge=1, le=5)
    gcs_motor: int | None = Field(default=None, ge=1, le=6)

    # Context
    position: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=200)
    recorder: str | None = Field(default=None, max_length=200)

    @field_validator("temperature", mode="before")
    @classmethod
    def normalize_temperature(cls, v: Any) -> float | None:
        """Normalize temperature to Fahrenheit."""
        if v is None:
            return None
        try:
            temp = float(v)
            # If likely Celsius (below 50), convert to Fahrenheit
            if temp < 50:
                temp = (temp * 9 / 5) + 32
            return round(temp, 1)
        except (ValueError, TypeError):
            return None

    @model_validator(mode="after")
    def calculate_map(self) -> "VitalSignModel":
        """Calculate MAP if blood pressure is present."""
        if self.systolic_bp and self.diastolic_bp and not self.mean_arterial_pressure:
            self.mean_arterial_pressure = round(
                (self.systolic_bp + 2 * self.diastolic_bp) / 3, 1
            )
        return self

    @model_validator(mode="after")
    def calculate_bmi(self) -> "VitalSignModel":
        """Calculate BMI if height and weight are present."""
        if self.weight and self.height and not self.bmi:
            # Convert to metric if needed
            weight_kg = self.weight
            if self.weight_unit.lower() in ("lb", "lbs", "pounds"):
                weight_kg = self.weight * 0.453592

            height_m = self.height / 100
            if self.height_unit.lower() in ("in", "inches"):
                height_m = self.height * 0.0254

            if height_m > 0:
                self.bmi = round(weight_kg / (height_m ** 2), 1)
        return self


class VitalsTransform:
    """
    Transform raw vital signs data into standardized format.

    This transform handles:
    - Unit normalization (temperature, weight, height)
    - MAP calculation
    - BMI calculation
    - Early warning score calculation
    - Vital trend detection

    Example:
        >>> transform = VitalsTransform()
        >>> raw = {"source_id": "V1", "patient_id": "P1", "heart_rate": 88}
        >>> result = transform.transform(raw)
        >>> print(result["heart_rate_status"])
        normal
    """

    def __init__(self):
        """Initialize the transform."""
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw vital signs record.

        Args:
            raw_data: Raw vital signs data dictionary.

        Returns:
            Transformed and validated vital signs data.
        """
        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "patient_id": str(raw_data.get("patient_id", "")),
            "encounter_id": raw_data.get("encounter_id"),
            "recorded_date": self._parse_datetime(raw_data.get("recorded_date") or raw_data.get("effective_date")),
            "heart_rate": self._parse_float(raw_data.get("heart_rate") or raw_data.get("pulse")),
            "respiratory_rate": self._parse_float(raw_data.get("respiratory_rate") or raw_data.get("resp_rate")),
            "systolic_bp": self._parse_float(raw_data.get("systolic_bp") or raw_data.get("sbp")),
            "diastolic_bp": self._parse_float(raw_data.get("diastolic_bp") or raw_data.get("dbp")),
            "mean_arterial_pressure": self._parse_float(raw_data.get("mean_arterial_pressure") or raw_data.get("map")),
            "temperature": raw_data.get("temperature") or raw_data.get("temp"),
            "temperature_unit": raw_data.get("temperature_unit", "F"),
            "oxygen_saturation": self._parse_float(raw_data.get("oxygen_saturation") or raw_data.get("spo2")),
            "oxygen_device": raw_data.get("oxygen_device"),
            "fio2": self._parse_float(raw_data.get("fio2")),
            "weight": self._parse_float(raw_data.get("weight")),
            "weight_unit": raw_data.get("weight_unit", "kg"),
            "height": self._parse_float(raw_data.get("height")),
            "height_unit": raw_data.get("height_unit", "cm"),
            "bmi": self._parse_float(raw_data.get("bmi")),
            "pain_score": self._parse_int(raw_data.get("pain_score") or raw_data.get("pain")),
            "gcs_total": self._parse_int(raw_data.get("gcs_total") or raw_data.get("gcs")),
            "gcs_eye": self._parse_int(raw_data.get("gcs_eye")),
            "gcs_verbal": self._parse_int(raw_data.get("gcs_verbal")),
            "gcs_motor": self._parse_int(raw_data.get("gcs_motor")),
            "position": raw_data.get("position"),
            "location": raw_data.get("location"),
            "recorder": raw_data.get("recorder"),
        }

        # Validate with Pydantic
        try:
            validated = VitalSignModel(**transformed)
            result = validated.model_dump()

            # Add vital status flags
            for vital_name, ranges in VITAL_RANGES.items():
                value = result.get(vital_name)
                if value is not None:
                    result[f"{vital_name}_status"] = self._get_vital_status(value, ranges)

            # Calculate early warning score
            result["news_score"] = self._calculate_news_score(result)
            result["news_risk"] = self._get_news_risk_level(result["news_score"])

            # Blood pressure classification
            if result.get("systolic_bp") and result.get("diastolic_bp"):
                result["bp_classification"] = self._classify_blood_pressure(
                    result["systolic_bp"],
                    result["diastolic_bp"],
                )

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for vitals",
                source_id=transformed.get("source_id"),
                error=str(e),
            )
            raise ValueError(f"Vitals validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of vital sign records."""
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

    @staticmethod
    def _parse_float(value: Any) -> float | None:
        """Parse float value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_int(value: Any) -> int | None:
        """Parse integer value."""
        if value is None:
            return None
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse datetime value."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]:
                try:
                    return datetime.strptime(value.split(".")[0].split("+")[0], fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _get_vital_status(value: float, ranges: dict[str, Any]) -> str:
        """Determine status of a vital sign."""
        if value < ranges.get("critical_low", float("-inf")):
            return "critical_low"
        if value > ranges.get("critical_high", float("inf")):
            return "critical_high"
        if value < ranges.get("normal_low", float("-inf")):
            return "low"
        if value > ranges.get("normal_high", float("inf")):
            return "high"
        return "normal"

    @staticmethod
    def _calculate_news_score(vitals: dict[str, Any]) -> int | None:
        """
        Calculate National Early Warning Score (NEWS).

        Returns None if insufficient data.
        """
        score = 0
        has_data = False

        # Respiratory rate scoring
        rr = vitals.get("respiratory_rate")
        if rr is not None:
            has_data = True
            if rr <= 8:
                score += 3
            elif rr <= 11:
                score += 1
            elif rr <= 20:
                score += 0
            elif rr <= 24:
                score += 2
            else:
                score += 3

        # Oxygen saturation scoring
        spo2 = vitals.get("oxygen_saturation")
        if spo2 is not None:
            has_data = True
            if spo2 <= 91:
                score += 3
            elif spo2 <= 93:
                score += 2
            elif spo2 <= 95:
                score += 1

        # Supplemental oxygen
        if vitals.get("oxygen_device") or (vitals.get("fio2") and vitals["fio2"] > 0.21):
            score += 2

        # Temperature scoring
        temp = vitals.get("temperature")
        if temp is not None:
            has_data = True
            if temp <= 95.0:
                score += 3
            elif temp <= 96.8:
                score += 1
            elif temp <= 100.4:
                score += 0
            elif temp <= 102.2:
                score += 1
            else:
                score += 2

        # Systolic BP scoring
        sbp = vitals.get("systolic_bp")
        if sbp is not None:
            has_data = True
            if sbp <= 90:
                score += 3
            elif sbp <= 100:
                score += 2
            elif sbp <= 110:
                score += 1
            elif sbp <= 219:
                score += 0
            else:
                score += 3

        # Heart rate scoring
        hr = vitals.get("heart_rate")
        if hr is not None:
            has_data = True
            if hr <= 40:
                score += 3
            elif hr <= 50:
                score += 1
            elif hr <= 90:
                score += 0
            elif hr <= 110:
                score += 1
            elif hr <= 130:
                score += 2
            else:
                score += 3

        return score if has_data else None

    @staticmethod
    def _get_news_risk_level(score: int | None) -> str | None:
        """Get NEWS risk level from score."""
        if score is None:
            return None
        if score <= 4:
            return "low"
        if score <= 6:
            return "medium"
        return "high"

    @staticmethod
    def _classify_blood_pressure(systolic: float, diastolic: float) -> str:
        """Classify blood pressure according to AHA guidelines."""
        if systolic < 120 and diastolic < 80:
            return "normal"
        if systolic < 130 and diastolic < 80:
            return "elevated"
        if systolic < 140 or diastolic < 90:
            return "stage_1_hypertension"
        if systolic < 180 and diastolic < 120:
            return "stage_2_hypertension"
        return "hypertensive_crisis"
