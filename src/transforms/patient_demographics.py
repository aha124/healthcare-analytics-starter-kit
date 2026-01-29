"""Patient demographics transformation module."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config.logging_config import get_logger

logger = get_logger(__name__)


class PatientDemographicsModel(BaseModel):
    """Validated patient demographics data model."""

    source_id: str = Field(..., description="Source system patient ID")
    mrn: str | None = Field(default=None, description="Medical Record Number")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    date_of_birth: date | None = Field(default=None)
    gender: str | None = Field(default=None, max_length=20)
    address_line1: str | None = Field(default=None, max_length=200)
    address_line2: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=50)
    postal_code: str | None = Field(default=None, max_length=20)
    country: str | None = Field(default="USA", max_length=50)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=100)
    language: str | None = Field(default=None, max_length=50)
    marital_status: str | None = Field(default=None, max_length=20)
    race: str | None = Field(default=None, max_length=50)
    ethnicity: str | None = Field(default=None, max_length=50)
    deceased: bool = Field(default=False)
    deceased_date: date | None = Field(default=None)
    ssn_hash: str | None = Field(default=None, description="Hashed SSN for matching")

    @field_validator("gender", mode="before")
    @classmethod
    def normalize_gender(cls, v: Any) -> str | None:
        """Normalize gender values to standard codes."""
        if not v:
            return None
        v = str(v).lower().strip()
        mapping = {
            "m": "male",
            "male": "male",
            "f": "female",
            "female": "female",
            "o": "other",
            "other": "other",
            "u": "unknown",
            "unknown": "unknown",
            "non-binary": "other",
            "nb": "other",
        }
        return mapping.get(v, "unknown")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def parse_date_of_birth(cls, v: Any) -> date | None:
        """Parse various date formats."""
        if not v:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y%m%d"]:
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        return None

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, v: Any) -> str | None:
        """Normalize postal code format."""
        if not v:
            return None
        v = str(v).strip().replace(" ", "")
        # Handle numeric ZIP codes that lost leading zeros
        if v.isdigit() and len(v) < 5:
            v = v.zfill(5)
        return v[:10]  # Truncate to reasonable length


class PatientDemographicsTransform:
    """
    Transform raw patient data into standardized demographics format.

    This transform handles:
    - Data validation and normalization
    - Gender standardization
    - Date parsing from multiple formats
    - Address normalization
    - Age calculation
    - PHI-safe hashing for matching

    Example:
        >>> transform = PatientDemographicsTransform()
        >>> raw_data = {"source_id": "123", "first_name": "John", "gender": "M"}
        >>> result = transform.transform(raw_data)
        >>> print(result["gender"])
        male
    """

    def __init__(self, hash_ssn: bool = True):
        """
        Initialize the transform.

        Args:
            hash_ssn: Whether to hash SSN values.
        """
        self.hash_ssn = hash_ssn
        self._logger = get_logger(__name__)

    def transform(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform a single raw patient record.

        Args:
            raw_data: Raw patient data dictionary.

        Returns:
            Transformed and validated patient data.

        Raises:
            ValueError: If required fields are missing.
        """
        # Extract and normalize fields
        transformed = {
            "source_id": str(raw_data.get("source_id", "")),
            "mrn": raw_data.get("mrn"),
            "first_name": self._clean_name(raw_data.get("first_name")),
            "last_name": self._clean_name(raw_data.get("last_name")),
            "middle_name": self._clean_name(raw_data.get("middle_name")),
            "date_of_birth": raw_data.get("date_of_birth") or raw_data.get("dob"),
            "gender": raw_data.get("gender") or raw_data.get("sex"),
            "address_line1": raw_data.get("address_line1") or raw_data.get("address"),
            "address_line2": raw_data.get("address_line2"),
            "city": raw_data.get("city"),
            "state": self._normalize_state(raw_data.get("state")),
            "postal_code": raw_data.get("postal_code") or raw_data.get("zip"),
            "country": raw_data.get("country", "USA"),
            "phone": self._normalize_phone(raw_data.get("phone")),
            "email": self._normalize_email(raw_data.get("email")),
            "language": raw_data.get("language"),
            "marital_status": self._normalize_marital_status(raw_data.get("marital_status")),
            "race": raw_data.get("race"),
            "ethnicity": raw_data.get("ethnicity"),
            "deceased": bool(raw_data.get("deceased", False)),
            "deceased_date": raw_data.get("deceased_date"),
        }

        # Handle SSN hashing
        ssn = raw_data.get("ssn")
        if ssn and self.hash_ssn:
            transformed["ssn_hash"] = self._hash_ssn(ssn)

        # Validate with Pydantic model
        try:
            validated = PatientDemographicsModel(**transformed)
            result = validated.model_dump()

            # Add computed fields
            if result["date_of_birth"]:
                result["age"] = self._calculate_age(result["date_of_birth"])
                result["age_group"] = self._get_age_group(result["age"])
            else:
                result["age"] = None
                result["age_group"] = None

            return result

        except Exception as e:
            self._logger.warning(
                "Validation failed for patient",
                source_id=transformed.get("source_id"),
                error=str(e),
            )
            raise ValueError(f"Patient validation failed: {e}")

    def transform_batch(
        self,
        records: list[dict[str, Any]],
        skip_invalid: bool = True,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Transform a batch of patient records.

        Args:
            records: List of raw patient records.
            skip_invalid: If True, skip invalid records instead of raising.

        Returns:
            Tuple of (valid_records, error_records).
        """
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
                        "raw_data": record,
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
    def _clean_name(name: Any) -> str | None:
        """Clean and normalize a name field."""
        if not name:
            return None
        name = str(name).strip()
        # Title case but handle special cases
        if name.isupper() or name.islower():
            name = name.title()
        return name[:100] if name else None

    @staticmethod
    def _normalize_state(state: Any) -> str | None:
        """Normalize state to two-letter code."""
        if not state:
            return None
        state = str(state).strip().upper()

        # Common state name to abbreviation mapping
        state_mapping = {
            "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
            "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT",
            "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
            "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
            "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
            "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI",
            "MINNESOTA": "MN", "MISSISSIPPI": "MS", "MISSOURI": "MO",
            "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV",
            "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
            "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND",
            "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
            "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD",
            "TENNESSEE": "TN", "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT",
            "VIRGINIA": "VA", "WASHINGTON": "WA", "WEST VIRGINIA": "WV",
            "WISCONSIN": "WI", "WYOMING": "WY", "DISTRICT OF COLUMBIA": "DC",
        }

        if len(state) == 2:
            return state
        return state_mapping.get(state, state[:2])

    @staticmethod
    def _normalize_phone(phone: Any) -> str | None:
        """Normalize phone number format."""
        if not phone:
            return None
        # Remove non-numeric characters
        digits = "".join(c for c in str(phone) if c.isdigit())
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        if len(digits) == 11 and digits[0] == "1":
            return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        return phone[:30] if phone else None

    @staticmethod
    def _normalize_email(email: Any) -> str | None:
        """Normalize email address."""
        if not email:
            return None
        email = str(email).strip().lower()
        if "@" in email:
            return email[:100]
        return None

    @staticmethod
    def _normalize_marital_status(status: Any) -> str | None:
        """Normalize marital status."""
        if not status:
            return None
        status = str(status).upper().strip()
        mapping = {
            "S": "single",
            "SINGLE": "single",
            "M": "married",
            "MARRIED": "married",
            "D": "divorced",
            "DIVORCED": "divorced",
            "W": "widowed",
            "WIDOWED": "widowed",
            "P": "partner",
            "DOMESTIC PARTNER": "partner",
            "U": "unknown",
            "UNKNOWN": "unknown",
        }
        return mapping.get(status, status.lower())

    @staticmethod
    def _hash_ssn(ssn: str) -> str:
        """Create a one-way hash of SSN for matching."""
        import hashlib

        # Remove non-numeric characters
        ssn_clean = "".join(c for c in ssn if c.isdigit())
        if len(ssn_clean) != 9:
            return ""
        # Use SHA-256 with a salt (in production, use a proper secret)
        salted = f"hask_salt_{ssn_clean}"
        return hashlib.sha256(salted.encode()).hexdigest()

    @staticmethod
    def _calculate_age(dob: date) -> int:
        """Calculate age from date of birth."""
        today = date.today()
        age = today.year - dob.year
        if (today.month, today.day) < (dob.month, dob.day):
            age -= 1
        return age

    @staticmethod
    def _get_age_group(age: int) -> str:
        """Get age group category."""
        if age < 1:
            return "infant"
        if age < 5:
            return "toddler"
        if age < 13:
            return "child"
        if age < 18:
            return "adolescent"
        if age < 30:
            return "young_adult"
        if age < 50:
            return "adult"
        if age < 65:
            return "middle_aged"
        if age < 80:
            return "senior"
        return "elderly"
