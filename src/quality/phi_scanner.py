"""PHI (Protected Health Information) detection utility."""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from config.logging_config import get_logger

logger = get_logger(__name__)


class PHIType(str, Enum):
    """Types of PHI that can be detected."""

    SSN = "ssn"
    PHONE = "phone"
    EMAIL = "email"
    DATE_OF_BIRTH = "date_of_birth"
    MRN = "mrn"
    ADDRESS = "address"
    NAME = "name"
    ACCOUNT_NUMBER = "account_number"
    LICENSE_NUMBER = "license_number"
    DEVICE_ID = "device_id"
    IP_ADDRESS = "ip_address"
    CREDIT_CARD = "credit_card"
    BIOMETRIC = "biometric"
    PHOTO = "photo"


@dataclass
class PHIMatch:
    """Represents a detected PHI match."""

    phi_type: PHIType
    field_name: str
    value_preview: str  # Redacted/truncated preview
    confidence: float  # 0.0 to 1.0
    pattern_matched: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "phi_type": self.phi_type.value,
            "field_name": self.field_name,
            "value_preview": self.value_preview,
            "confidence": self.confidence,
            "pattern_matched": self.pattern_matched,
        }


class PHIScanner:
    """
    Scanner for detecting Protected Health Information (PHI) in data.

    This scanner helps ensure PHI is not inadvertently exposed in:
    - Log files
    - Error messages
    - Analytics exports
    - Non-production environments

    IMPORTANT: This is a detection tool, not a compliance solution.
    Always work with your compliance team for proper PHI handling.

    Example:
        >>> scanner = PHIScanner(sensitivity="high")
        >>> matches = scanner.scan_record({"notes": "Patient SSN: 123-45-6789"})
        >>> for match in matches:
        ...     print(f"Found {match.phi_type}: {match.field_name}")
    """

    # Regex patterns for PHI detection
    PATTERNS = {
        PHIType.SSN: [
            r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",  # 123-45-6789 or 123 45 6789
            r"\bssn\s*[:=]\s*\d{9}\b",  # ssn: 123456789
        ],
        PHIType.PHONE: [
            r"\b\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",  # (555) 123-4567
            r"\b\d{3}[-.\s]\d{4}\b",  # 123-4567
        ],
        PHIType.EMAIL: [
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        ],
        PHIType.DATE_OF_BIRTH: [
            r"\b(?:dob|birth\s*date|date\s*of\s*birth)\s*[:=]\s*[\d/\-]+",
            r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b",  # MM/DD/YYYY
        ],
        PHIType.MRN: [
            r"\b(?:mrn|medical\s*record)\s*[:=#]?\s*[A-Z0-9\-]+",
            r"\b[A-Z]{2,3}[-]?\d{6,10}\b",  # Common MRN formats
        ],
        PHIType.CREDIT_CARD: [
            r"\b(?:4\d{3}|5[1-5]\d{2}|6011|3[47]\d{2})[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",
        ],
        PHIType.IP_ADDRESS: [
            r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        ],
        PHIType.LICENSE_NUMBER: [
            r"\b(?:license|dl|driver)\s*#?\s*[:=]?\s*[A-Z0-9\-]+",
        ],
    }

    # Field names that likely contain PHI
    PHI_FIELD_NAMES = {
        PHIType.SSN: ["ssn", "social_security", "social_security_number", "ss_number"],
        PHIType.PHONE: ["phone", "telephone", "mobile", "cell", "fax", "phone_number"],
        PHIType.EMAIL: ["email", "email_address", "e_mail"],
        PHIType.DATE_OF_BIRTH: ["dob", "date_of_birth", "birth_date", "birthdate"],
        PHIType.MRN: ["mrn", "medical_record_number", "patient_id", "chart_number"],
        PHIType.NAME: [
            "name", "first_name", "last_name", "middle_name", "patient_name",
            "full_name", "maiden_name", "legal_name",
        ],
        PHIType.ADDRESS: [
            "address", "street", "address_line", "city", "zip", "postal_code",
            "street_address", "home_address",
        ],
    }

    def __init__(self, sensitivity: str = "medium"):
        """
        Initialize the PHI scanner.

        Args:
            sensitivity: Detection sensitivity level (low, medium, high).
                - low: Only obvious patterns
                - medium: Patterns + suspicious field names
                - high: All patterns + field names + fuzzy matching
        """
        self.sensitivity = sensitivity
        self._logger = get_logger(__name__)

    def scan_record(
        self,
        record: dict[str, Any],
        exclude_fields: list[str] | None = None,
    ) -> list[PHIMatch]:
        """
        Scan a record for potential PHI.

        Args:
            record: Dictionary to scan.
            exclude_fields: Fields to skip (e.g., already encrypted fields).

        Returns:
            List of PHIMatch objects for detected PHI.
        """
        matches = []
        exclude_fields = set(f.lower() for f in (exclude_fields or []))

        for field_name, value in record.items():
            if field_name.lower() in exclude_fields:
                continue

            field_matches = self._scan_field(field_name, value)
            matches.extend(field_matches)

        return matches

    def scan_batch(
        self,
        records: list[dict[str, Any]],
        exclude_fields: list[str] | None = None,
        sample_size: int | None = None,
    ) -> dict[str, Any]:
        """
        Scan a batch of records for PHI.

        Args:
            records: List of records to scan.
            exclude_fields: Fields to skip.
            sample_size: Number of records to sample (None for all).

        Returns:
            Summary of PHI detection results.
        """
        import random

        if sample_size and len(records) > sample_size:
            records = random.sample(records, sample_size)

        all_matches = []
        records_with_phi = 0

        for record in records:
            matches = self.scan_record(record, exclude_fields)
            if matches:
                records_with_phi += 1
                all_matches.extend(matches)

        # Summarize by PHI type
        by_type: dict[str, int] = {}
        by_field: dict[str, int] = {}

        for match in all_matches:
            by_type[match.phi_type.value] = by_type.get(match.phi_type.value, 0) + 1
            by_field[match.field_name] = by_field.get(match.field_name, 0) + 1

        result = {
            "records_scanned": len(records),
            "records_with_phi": records_with_phi,
            "phi_detection_rate": round(records_with_phi / len(records) * 100, 2) if records else 0,
            "total_matches": len(all_matches),
            "by_type": by_type,
            "by_field": by_field,
        }

        self._logger.info("PHI scan complete", **result)

        return result

    def _scan_field(
        self,
        field_name: str,
        value: Any,
    ) -> list[PHIMatch]:
        """Scan a single field for PHI."""
        matches = []

        if value is None:
            return matches

        # Convert to string for pattern matching
        str_value = str(value)
        field_lower = field_name.lower()

        # Check field name for PHI indicators
        if self.sensitivity in ["medium", "high"]:
            for phi_type, field_names in self.PHI_FIELD_NAMES.items():
                if any(fn in field_lower for fn in field_names):
                    matches.append(PHIMatch(
                        phi_type=phi_type,
                        field_name=field_name,
                        value_preview=self._redact_value(str_value),
                        confidence=0.8 if self.sensitivity == "high" else 0.6,
                        pattern_matched="field_name",
                    ))

        # Check patterns
        for phi_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, str_value, re.IGNORECASE):
                    matches.append(PHIMatch(
                        phi_type=phi_type,
                        field_name=field_name,
                        value_preview=self._redact_value(str_value),
                        confidence=0.9,
                        pattern_matched=pattern[:50],
                    ))
                    break  # One match per type is enough

        # High sensitivity: check for name-like patterns
        if self.sensitivity == "high" and not matches:
            if self._looks_like_name(str_value):
                matches.append(PHIMatch(
                    phi_type=PHIType.NAME,
                    field_name=field_name,
                    value_preview=self._redact_value(str_value),
                    confidence=0.5,
                    pattern_matched="name_heuristic",
                ))

        return matches

    @staticmethod
    def _redact_value(value: str, visible_chars: int = 4) -> str:
        """Redact a value for safe display."""
        if len(value) <= visible_chars:
            return "*" * len(value)
        return value[:visible_chars] + "*" * (len(value) - visible_chars)

    @staticmethod
    def _looks_like_name(value: str) -> bool:
        """Heuristic check if value looks like a name."""
        if not value or len(value) < 2 or len(value) > 100:
            return False

        # Check for two or more capitalized words
        words = value.split()
        if len(words) >= 2:
            capitalized = sum(1 for w in words if w and w[0].isupper())
            if capitalized >= 2:
                # Not a name if it has numbers
                if not any(c.isdigit() for c in value):
                    return True

        return False

    def is_safe_to_log(
        self,
        record: dict[str, Any],
        allowed_fields: list[str] | None = None,
    ) -> bool:
        """
        Check if a record is safe to log (no PHI detected).

        Args:
            record: Record to check.
            allowed_fields: Fields known to be safe.

        Returns:
            True if safe to log, False if PHI detected.
        """
        matches = self.scan_record(record, exclude_fields=allowed_fields)
        return len(matches) == 0

    def sanitize_for_logging(
        self,
        record: dict[str, Any],
        exclude_fields: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create a sanitized copy of record for logging.

        Args:
            record: Original record.
            exclude_fields: Additional fields to exclude.

        Returns:
            Sanitized copy with PHI fields redacted.
        """
        matches = self.scan_record(record, exclude_fields)
        phi_fields = {m.field_name for m in matches}

        sanitized = {}
        for field, value in record.items():
            if field in phi_fields:
                sanitized[field] = "[REDACTED]"
            else:
                sanitized[field] = value

        return sanitized
