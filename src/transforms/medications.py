"""Medications transformation module."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


# High-alert medication categories (ISMP list)
HIGH_ALERT_CATEGORIES = {
    "anticoagulants": ["warfarin", "heparin", "enoxaparin", "rivaroxaban", "apixaban", "dabigatran"],
    "insulins": ["insulin", "humalog", "novolog", "lantus", "levemir", "tresiba"],
    "opioids": ["morphine", "fentanyl", "hydromorphone", "oxycodone", "methadone", "hydrocodone"],
    "chemotherapy": ["methotrexate", "vincristine", "cyclophosphamide", "doxorubicin"],
    "paralytics": ["succinylcholine", "rocuronium", "vecuronium", "cisatracurium"],
    "concentrated_electrolytes": ["potassium chloride", "sodium chloride 23.4%", "magnesium sulfate"],
}

# Common drug classes for categorization
DRUG_CLASSES = {
    "antihypertensives": ["lisinopril", "amlodipine", "losartan", "metoprolol", "hydrochlorothiazide", "carvedilol"],
    "diabetes": ["metformin", "glipizide", "sitagliptin", "empagliflozin", "insulin"],
    "statins": ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "antibiotics": ["amoxicillin", "azithromycin", "cephalexin", "ciprofloxacin", "levofloxacin", "vancomycin"],
    "antidepressants": ["sertraline", "escitalopram", "fluoxetine", "bupropion", "venlafaxine", "duloxetine"],
    "ppis": ["omeprazole", "pantoprazole", "esomeprazole", "lansoprazole"],
    "nsaids": ["ibuprofen", "naproxen", "meloxicam", "celecoxib", "ketorolac"],
    "benzodiazepines": ["lorazepam", "diazepam", "alprazolam", "clonazepam", "midazolam"],
    "anticonvulsants": ["levetiracetam", "phenytoin", "valproic acid", "carbamazepine", "gabapentin", "pregabalin"],
    "diuretics": ["furosemide", "hydrochlorothiazide", "spironolactone", "bumetanide"],
}


class MedicationModel(BaseModel):
    """Validated medication data model."""

    source_id: str = Field(..., description="Source system medication ID")
    patient_id: str = Field(..., description="Patient identifier")
    encounter_id: str | None = Field(default=None, description="Encounter identifier")
    medication_code: str | None = Field(default=None, max_length=50)
    medication_name: str = Field(..., max_length=500)
    generic_name: str | None = Field(default=None, max_length=200)
    brand_name: str | None = Field(default=None, max_length=200)
    ndc_code: str | None = Field(default=None, max_length=20)
    rxnorm_code: str | None = Field(default=None, max_length=20)
    status: str | None = Field(default=None, max_length=30)
    intent: str | None = Field(default=None, max_length=30)
    dose_value: float | None = Field(default=None, ge=0)
    dose_unit: str | None = Field(default=None, max_length=30)
    route: str | None = Field(default=None, max_length=50)
    frequency: str | None = Field(default=None, max_length=100)
    prn: bool = Field(default=False)
    start_date: date | None = Field(default=None)
    end_date: date | None = Field(default=None)
    authored_date: datetime | None = Field(default=None)
    prescriber: str | None = Field(default=None, max_length=200)
    pharmacy: str | None = Field(default=None, max_length=200)
    quantity: float | None = Field(default=None, ge=0)
    refills: int | None = Field(default=None, ge=0)
    days_supply: int | None = Field(default=None, ge=0)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str | None:
        """Normalize medication status."""
        if not v:
            return None
        v = str(v).lower().strip()
        mappings = {
            "active": "active",
            "on-hold": "on_hold",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "completed": "completed",
            "stopped": "stopped",
            "entered-in-error": "error",
            "draft": "draft",
            "unknown": "unknown",
        }
        return mappings.get(v, v)

    @field_validator("route", mode="before")
    @classmethod
    def normalize_route(cls, v: Any) -> str | None:
        """Normalize administration route."""
        if not v:
            return None
        v = str(v).lower().strip()
        mappings = {
            "oral": "oral",
            "po": "oral",
            "by mouth": "oral",
            "iv": "intravenous",
            "intravenous": "intravenous",
            "im": "intramuscular",
            "intramuscular": "intramuscular",
            "sq": "subcutaneous",
            "sc": "subcutaneous",
            "subq": "subcutaneous",
            "subcutaneous": "subcutaneous",
            "topical": "topical",
            "top": "topical",
            "inh": "inhalation",
            "inhalation": "inhalation",
            "rectal": "rectal",
            "pr": "rectal",
            "ophthalmic": "ophthalmic",
            "otic": "otic",
            "nasal": "nasal",
            "transdermal": "transdermal",
            "td": "transdermal",
            "patch": "transdermal",
            "sl": "sublingual",
            "sublingual": "sublingual",
        }
        return mappings.get(v, v)


class MedicationsTransform:
    """
    Transform raw medication data into standardized format.

    This transform handles:
    - Drug name normalization
    - Route standardization
    - High-alert medication flagging
    - Drug class categorization
    - Opioid/controlled substance flagging
    - Days supply calculation

    Example:
        >>> transform = MedicationsTransform()
        >>> raw = {"source_id": "M1", "patient_id": "P1", "medication_name": "Metformin 500mg"}
        >>> result = transform.transform(raw)
        >>> print(result["drug_class"])
        diabetes
    """

    def __init__(self):
        """Initialize the transform."""
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw medication record.

        Args:
            raw_data: Raw medication data dictionary.

        Returns:
            Transformed and validated medication data.
        """
        med_name = str(raw_data.get("medication_name") or raw_data.get("drug_name") or "")

        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "patient_id": str(raw_data.get("patient_id", "")),
            "encounter_id": raw_data.get("encounter_id"),
            "medication_code": raw_data.get("medication_code"),
            "medication_name": med_name,
            "generic_name": raw_data.get("generic_name"),
            "brand_name": raw_data.get("brand_name"),
            "ndc_code": raw_data.get("ndc_code"),
            "rxnorm_code": raw_data.get("rxnorm_code"),
            "status": raw_data.get("status"),
            "intent": raw_data.get("intent"),
            "dose_value": self._parse_dose_value(raw_data.get("dose_value") or raw_data.get("dose")),
            "dose_unit": raw_data.get("dose_unit"),
            "route": raw_data.get("route"),
            "frequency": raw_data.get("frequency") or raw_data.get("sig"),
            "prn": self._parse_prn(raw_data.get("prn") or raw_data.get("frequency")),
            "start_date": self._parse_date(raw_data.get("start_date")),
            "end_date": self._parse_date(raw_data.get("end_date")),
            "authored_date": self._parse_datetime(raw_data.get("authored_date") or raw_data.get("order_date")),
            "prescriber": raw_data.get("prescriber") or raw_data.get("ordering_provider"),
            "pharmacy": raw_data.get("pharmacy"),
            "quantity": self._parse_float(raw_data.get("quantity")),
            "refills": self._parse_int(raw_data.get("refills")),
            "days_supply": self._parse_int(raw_data.get("days_supply")),
        }

        # Validate with Pydantic
        try:
            validated = MedicationModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            med_name_lower = med_name.lower()

            # Drug class
            result["drug_class"] = self._get_drug_class(med_name_lower)

            # High-alert flags
            result["is_high_alert"] = self._is_high_alert(med_name_lower)
            result["high_alert_category"] = self._get_high_alert_category(med_name_lower)

            # Controlled substance flags
            result["is_opioid"] = self._is_opioid(med_name_lower)
            result["is_controlled"] = self._is_controlled(med_name_lower)
            result["is_anticoagulant"] = self._is_anticoagulant(med_name_lower)

            # Parse dose from medication name if not provided
            if not result["dose_value"]:
                parsed = self._parse_dose_from_name(med_name)
                result["dose_value"] = parsed.get("value")
                result["dose_unit"] = parsed.get("unit") or result["dose_unit"]

            # Frequency analysis
            if result["frequency"]:
                result["doses_per_day"] = self._calculate_doses_per_day(result["frequency"])
            else:
                result["doses_per_day"] = None

            # Active days
            if result["start_date"] and result["end_date"]:
                result["therapy_days"] = (result["end_date"] - result["start_date"]).days
            else:
                result["therapy_days"] = None

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for medication",
                source_id=transformed.get("source_id"),
                medication_name=med_name[:50],
                error=str(e),
            )
            raise ValueError(f"Medication validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Transform a batch of medication records."""
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
                        "medication_name": record.get("medication_name", "")[:50],
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
    def _parse_date(value: Any) -> date | None:
        """Parse date value."""
        if not value:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, str):
            for fmt in ["%Y-%m-%d", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse datetime value."""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(value.split(".")[0].split("+")[0], fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _parse_dose_value(value: Any) -> float | None:
        """Parse dose value from various formats."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            import re

            # Extract first number from string
            match = re.search(r"(\d+\.?\d*)", value)
            if match:
                return float(match.group(1))
        return None

    @staticmethod
    def _parse_prn(value: Any) -> bool:
        """Determine if medication is PRN."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return "prn" in value.lower() or "as needed" in value.lower()
        return False

    @staticmethod
    def _get_drug_class(med_name: str) -> str | None:
        """Get drug class from medication name."""
        for drug_class, drugs in DRUG_CLASSES.items():
            for drug in drugs:
                if drug in med_name:
                    return drug_class
        return None

    @staticmethod
    def _is_high_alert(med_name: str) -> bool:
        """Check if medication is a high-alert medication."""
        for drugs in HIGH_ALERT_CATEGORIES.values():
            for drug in drugs:
                if drug in med_name:
                    return True
        return False

    @staticmethod
    def _get_high_alert_category(med_name: str) -> str | None:
        """Get high-alert category if applicable."""
        for category, drugs in HIGH_ALERT_CATEGORIES.items():
            for drug in drugs:
                if drug in med_name:
                    return category
        return None

    @staticmethod
    def _is_opioid(med_name: str) -> bool:
        """Check if medication is an opioid."""
        opioids = [
            "morphine", "fentanyl", "hydromorphone", "oxycodone", "oxycontin",
            "hydrocodone", "codeine", "methadone", "tramadol", "buprenorphine",
            "meperidine", "dilaudid", "percocet", "vicodin", "norco",
        ]
        return any(opioid in med_name for opioid in opioids)

    @staticmethod
    def _is_controlled(med_name: str) -> bool:
        """Check if medication is a controlled substance."""
        controlled = [
            "morphine", "fentanyl", "hydromorphone", "oxycodone", "hydrocodone",
            "codeine", "methadone", "tramadol", "buprenorphine", "alprazolam",
            "diazepam", "lorazepam", "clonazepam", "midazolam", "zolpidem",
            "amphetamine", "methylphenidate", "testosterone", "ketamine",
        ]
        return any(drug in med_name for drug in controlled)

    @staticmethod
    def _is_anticoagulant(med_name: str) -> bool:
        """Check if medication is an anticoagulant."""
        anticoagulants = [
            "warfarin", "coumadin", "heparin", "enoxaparin", "lovenox",
            "rivaroxaban", "xarelto", "apixaban", "eliquis", "dabigatran",
            "pradaxa", "edoxaban", "fondaparinux", "argatroban",
        ]
        return any(ac in med_name for ac in anticoagulants)

    @staticmethod
    def _parse_dose_from_name(med_name: str) -> dict[str, Any]:
        """Extract dose information from medication name."""
        import re

        result: dict[str, Any] = {"value": None, "unit": None}

        # Pattern: number followed by unit (e.g., "500mg", "10 mg", "0.5mg")
        pattern = r"(\d+\.?\d*)\s*(mg|g|mcg|ml|unit|units|meq)"
        match = re.search(pattern, med_name.lower())

        if match:
            result["value"] = float(match.group(1))
            result["unit"] = match.group(2)

        return result

    @staticmethod
    def _calculate_doses_per_day(frequency: str) -> float | None:
        """Calculate doses per day from frequency string."""
        freq = frequency.lower()

        # Common frequency mappings
        mappings = {
            "once daily": 1,
            "daily": 1,
            "qd": 1,
            "qday": 1,
            "twice daily": 2,
            "bid": 2,
            "three times daily": 3,
            "tid": 3,
            "four times daily": 4,
            "qid": 4,
            "every 4 hours": 6,
            "q4h": 6,
            "every 6 hours": 4,
            "q6h": 4,
            "every 8 hours": 3,
            "q8h": 3,
            "every 12 hours": 2,
            "q12h": 2,
            "weekly": 0.14,
            "biweekly": 0.07,
            "monthly": 0.03,
        }

        for pattern, doses in mappings.items():
            if pattern in freq:
                return doses

        return None
