# Customization Guide

This guide explains how to extend and customize the Healthcare Analytics Starter Kit for your organization's specific needs.

## Table of Contents

1. [Adding a New Data Source](#adding-a-new-data-source)
2. [Creating Custom Transforms](#creating-custom-transforms)
3. [Adding New Metrics](#adding-new-metrics)
4. [Custom Dashboards](#custom-dashboards)
5. [Extending the Data Model](#extending-the-data-model)
6. [Custom Validation Rules](#custom-validation-rules)

---

## Adding a New Data Source

### Step 1: Create a New Connector

Create a new connector in `src/connectors/`:

```python
# src/connectors/custom_connector.py
"""Custom connector for Your EMR System."""

from datetime import datetime
from typing import Any, Generator

from src.connectors.base_connector import BaseConnector
from config import get_logger

logger = get_logger(__name__)


class CustomConnector(BaseConnector):
    """Connector for Your Custom EMR System."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        **kwargs,
    ):
        """
        Initialize the custom connector.

        Args:
            api_url: Base URL for the API.
            api_key: API authentication key.
        """
        self.api_url = api_url
        self.api_key = api_key
        self.session = self._create_session()

    def _create_session(self):
        """Create authenticated session."""
        import httpx
        return httpx.Client(
            base_url=self.api_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch patients from the custom system."""
        params = {}
        if since:
            params["modified_since"] = since.isoformat()
        if patient_ids:
            params["ids"] = ",".join(patient_ids)

        response = self.session.get("/patients", params=params)
        response.raise_for_status()

        for patient in response.json()["data"]:
            yield self._normalize_patient(patient)

    def _normalize_patient(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Normalize patient data to standard format."""
        return {
            "source_patient_id": raw["id"],
            "mrn": raw.get("medical_record_number"),
            "first_name": raw.get("first_name"),
            "last_name": raw.get("last_name"),
            "date_of_birth": raw.get("birth_date"),
            "gender": raw.get("sex"),
            # Map other fields...
        }

    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch encounters from the custom system."""
        # Implement similar to fetch_patients
        pass

    # Implement other fetch methods as needed...
```

### Step 2: Add Configuration

Add configuration options in `config/settings.py`:

```python
class CustomEMRSettings(BaseSettings):
    """Settings for Custom EMR connector."""

    enabled: bool = False
    api_url: str = ""
    api_key: SecretStr | None = None

    model_config = SettingsConfigDict(env_prefix="CUSTOM_EMR_")


class Settings(BaseSettings):
    # ... existing settings ...
    custom_emr: CustomEMRSettings = CustomEMRSettings()
```

### Step 3: Register the Connector

Update `src/connectors/__init__.py`:

```python
from src.connectors.custom_connector import CustomConnector

__all__ = [
    # ... existing exports ...
    "CustomConnector",
]
```

### Step 4: Update the Pipeline

Add the connector to `pipelines/daily_refresh.py`:

```python
def _process_custom_emr_source(self) -> None:
    """Process data from Custom EMR."""
    if not settings.custom_emr.enabled:
        return

    logger.info("Processing Custom EMR source")
    connector = CustomConnector(
        api_url=settings.custom_emr.api_url,
        api_key=settings.custom_emr.api_key.get_secret_value(),
    )

    # Process patients, encounters, etc.
    patient_count = self._extract_transform_load(
        connector=connector,
        resource_type="patients",
        transform=self.patient_transform,
        table_name="staging.patients",
    )
    self.stats["records_loaded"]["custom_patients"] = patient_count
```

---

## Creating Custom Transforms

### Step 1: Create the Transform Class

Create a new transform in `src/transforms/`:

```python
# src/transforms/custom_data.py
"""Transform for custom healthcare data type."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from config import get_logger

logger = get_logger(__name__)


class CustomDataModel(BaseModel):
    """Pydantic model for custom data type."""

    source_record_id: str
    source_patient_id: str
    record_datetime: datetime | None = None
    custom_field_1: str | None = None
    custom_field_2: float | None = None
    custom_category: str | None = None

    # Computed fields
    is_flagged: bool = False

    @field_validator("custom_category", mode="before")
    @classmethod
    def normalize_category(cls, v: Any) -> str | None:
        """Normalize category values."""
        if v is None:
            return None
        category_map = {
            "A": "category_a",
            "B": "category_b",
            "C": "category_c",
        }
        return category_map.get(str(v).upper(), "unknown")


class CustomDataTransform:
    """Transform raw custom data to standardized format."""

    def transform(self, raw_data: dict[str, Any]) -> CustomDataModel | None:
        """
        Transform a raw record.

        Args:
            raw_data: Raw data dictionary from source.

        Returns:
            Transformed model or None if invalid.
        """
        try:
            # Extract and normalize fields
            record = {
                "source_record_id": raw_data.get("id") or raw_data.get("record_id"),
                "source_patient_id": raw_data.get("patient_id"),
                "record_datetime": self._parse_datetime(raw_data.get("datetime")),
                "custom_field_1": raw_data.get("field1"),
                "custom_field_2": self._parse_numeric(raw_data.get("field2")),
                "custom_category": raw_data.get("category"),
            }

            # Compute derived fields
            record["is_flagged"] = self._check_flag_condition(record)

            return CustomDataModel(**record)

        except Exception as e:
            logger.warning(
                "Transform failed for custom data",
                error=str(e),
                record_id=raw_data.get("id"),
            )
            return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse datetime from various formats."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        # Add custom parsing logic
        return None

    def _parse_numeric(self, value: Any) -> float | None:
        """Parse numeric value."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    def _check_flag_condition(self, record: dict) -> bool:
        """Check if record should be flagged."""
        # Custom business logic
        if record.get("custom_field_2") and record["custom_field_2"] > 100:
            return True
        return False
```

### Step 2: Add Database Model

Add the staging table in `src/models/staging.py`:

```python
class StagingCustomData(Base, AuditMixin):
    """Custom data staging table."""

    __tablename__ = "custom_data"
    __table_args__ = {"schema": "staging"}

    id = Column(BigInteger, primary_key=True)
    source_record_id = Column(String(100), unique=True, nullable=False)
    source_patient_id = Column(String(100), nullable=False)
    record_datetime = Column(DateTime(timezone=True))
    custom_field_1 = Column(String(255))
    custom_field_2 = Column(Numeric(10, 2))
    custom_category = Column(String(50))
    is_flagged = Column(Boolean, default=False)
```

### Step 3: Create Schema Migration

Add DDL in `sql/schema/`:

```sql
-- sql/schema/04_custom_tables.sql

CREATE TABLE IF NOT EXISTS staging.custom_data (
    id BIGSERIAL PRIMARY KEY,
    source_record_id VARCHAR(100) UNIQUE NOT NULL,
    source_patient_id VARCHAR(100) NOT NULL,
    record_datetime TIMESTAMP WITH TIME ZONE,
    custom_field_1 VARCHAR(255),
    custom_field_2 NUMERIC(10, 2),
    custom_category VARCHAR(50),
    is_flagged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_custom_data_patient ON staging.custom_data(source_patient_id);
CREATE INDEX idx_custom_data_datetime ON staging.custom_data(record_datetime);
```

---

## Adding New Metrics

### Step 1: Define the Metric Table

Add to `src/models/metrics.py`:

```python
class CustomMetricDaily(Base):
    """Daily custom metric aggregation."""

    __tablename__ = "custom_metric_daily"
    __table_args__ = {"schema": "metrics"}

    id = Column(BigInteger, primary_key=True)
    metric_date = Column(Date, nullable=False, unique=True)
    total_count = Column(Integer, default=0)
    flagged_count = Column(Integer, default=0)
    flagged_rate = Column(Numeric(5, 2))
    avg_value = Column(Numeric(10, 2))
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
```

### Step 2: Create the Metric View

Add SQL view in `sql/views/`:

```sql
-- sql/views/custom_metrics.sql

CREATE OR REPLACE VIEW vw_custom_metrics_daily AS
SELECT
    record_datetime::DATE as metric_date,
    COUNT(*) as total_count,
    COUNT(CASE WHEN is_flagged THEN 1 END) as flagged_count,
    ROUND(
        COUNT(CASE WHEN is_flagged THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0),
        2
    ) as flagged_rate,
    ROUND(AVG(custom_field_2), 2) as avg_value
FROM staging.custom_data
WHERE record_datetime >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY record_datetime::DATE
ORDER BY metric_date DESC;
```

### Step 3: Add Metric Computation

Update `pipelines/scheduled_tasks.py`:

```python
def run_custom_metrics(session: Session | None = None) -> dict[str, Any]:
    """Compute custom metrics."""
    if session is None:
        session = get_session()

    logger.info("Computing custom metrics")

    session.execute(text("""
        INSERT INTO metrics.custom_metric_daily (
            metric_date, total_count, flagged_count, flagged_rate, avg_value
        )
        SELECT
            record_datetime::DATE,
            COUNT(*),
            COUNT(CASE WHEN is_flagged THEN 1 END),
            ROUND(COUNT(CASE WHEN is_flagged THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2),
            ROUND(AVG(custom_field_2), 2)
        FROM staging.custom_data
        WHERE record_datetime >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY record_datetime::DATE
        ON CONFLICT (metric_date) DO UPDATE SET
            total_count = EXCLUDED.total_count,
            flagged_count = EXCLUDED.flagged_count,
            flagged_rate = EXCLUDED.flagged_rate,
            avg_value = EXCLUDED.avg_value,
            updated_at = CURRENT_TIMESTAMP
    """))

    session.commit()
    return {"status": "success"}
```

---

## Custom Dashboards

### Step 1: Create Dashboard JSON

Create a new dashboard in `grafana/dashboards/`:

```json
{
  "title": "Custom Metrics Dashboard",
  "uid": "custom-metrics",
  "panels": [
    {
      "id": 1,
      "title": "Daily Flagged Rate",
      "type": "timeseries",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "targets": [
        {
          "rawSql": "SELECT metric_date as time, flagged_rate FROM metrics.custom_metric_daily ORDER BY metric_date",
          "format": "time_series"
        }
      ]
    },
    {
      "id": 2,
      "title": "Total Count",
      "type": "stat",
      "gridPos": { "h": 4, "w": 6, "x": 12, "y": 0 },
      "targets": [
        {
          "rawSql": "SELECT SUM(total_count) FROM metrics.custom_metric_daily WHERE metric_date >= CURRENT_DATE - INTERVAL '7 days'",
          "format": "table"
        }
      ]
    }
  ]
}
```

### Step 2: Configure Auto-Provisioning

The dashboard will be automatically loaded if placed in the `grafana/dashboards/` directory.

### Step 3: Add Variables (Optional)

Add template variables for filtering:

```json
{
  "templating": {
    "list": [
      {
        "name": "category",
        "type": "query",
        "query": "SELECT DISTINCT custom_category FROM staging.custom_data",
        "multi": true
      }
    ]
  }
}
```

---

## Extending the Data Model

### Adding Columns to Existing Tables

1. Create migration SQL:

```sql
-- sql/migrations/001_add_custom_column.sql
ALTER TABLE staging.patients
ADD COLUMN IF NOT EXISTS custom_identifier VARCHAR(100);

CREATE INDEX IF NOT EXISTS idx_patients_custom_id
ON staging.patients(custom_identifier);
```

2. Update the SQLAlchemy model:

```python
# In src/models/staging.py
class StagingPatient(Base, AuditMixin):
    # ... existing columns ...
    custom_identifier = Column(String(100))
```

3. Update the transform:

```python
# In src/transforms/patient_demographics.py
class PatientModel(BaseModel):
    # ... existing fields ...
    custom_identifier: str | None = None
```

### Adding New Dimension Tables

1. Create the model:

```python
# src/models/dimensional.py
class DimLocation(Base):
    """Location dimension table."""

    __tablename__ = "locations"
    __table_args__ = {"schema": "dim"}

    location_key = Column(BigInteger, primary_key=True)
    location_code = Column(String(50), unique=True)
    location_name = Column(String(255))
    location_type = Column(String(50))  # unit, department, facility
    parent_location_key = Column(BigInteger, ForeignKey("dim.locations.location_key"))
    capacity = Column(Integer)
    is_active = Column(Boolean, default=True)
```

2. Create DDL script:

```sql
-- sql/schema/05_location_dimension.sql
CREATE TABLE IF NOT EXISTS dim.locations (
    location_key BIGSERIAL PRIMARY KEY,
    location_code VARCHAR(50) UNIQUE NOT NULL,
    location_name VARCHAR(255),
    location_type VARCHAR(50),
    parent_location_key BIGINT REFERENCES dim.locations(location_key),
    capacity INTEGER,
    is_active BOOLEAN DEFAULT TRUE
);
```

---

## Custom Validation Rules

### Adding Domain-Specific Validators

Extend `src/quality/validators.py`:

```python
class HealthcareValidator(DataValidator):
    """Extended validator with healthcare-specific rules."""

    def validate_diagnosis_code(self, code: str) -> ValidationResult:
        """Validate ICD-10 diagnosis code format."""
        errors = []
        warnings = []

        # Basic format check
        if not re.match(r'^[A-Z][0-9]{2}(\.[0-9A-Z]{0,4})?$', code):
            errors.append(f"Invalid ICD-10 format: {code}")

        # Check for deprecated codes
        if code in self.DEPRECATED_CODES:
            warnings.append(f"Deprecated ICD-10 code: {code}")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_npi(self, npi: str) -> ValidationResult:
        """Validate National Provider Identifier."""
        errors = []

        if not npi or len(npi) != 10:
            errors.append("NPI must be 10 digits")
            return ValidationResult(is_valid=False, errors=errors)

        # Luhn algorithm check
        if not self._luhn_check(npi):
            errors.append("Invalid NPI checksum")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
        )

    def _luhn_check(self, number: str) -> bool:
        """Verify Luhn checksum."""
        digits = [int(d) for d in number]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(divmod(d * 2, 10))
        return checksum % 10 == 0
```

### Using Custom Validators

```python
from src.quality.validators import HealthcareValidator

validator = HealthcareValidator()

# Validate diagnosis
result = validator.validate_diagnosis_code("J18.9")
if not result.is_valid:
    print(f"Invalid diagnosis: {result.errors}")

# Validate provider NPI
result = validator.validate_npi("1234567893")
if result.warnings:
    print(f"Warnings: {result.warnings}")
```

---

## Best Practices

1. **Keep transforms idempotent**: Running the same data through transforms multiple times should produce the same result.

2. **Use feature flags**: Add configuration options to enable/disable new features:
   ```python
   if settings.features.enable_custom_metrics:
       run_custom_metrics()
   ```

3. **Write tests**: Add tests for new connectors, transforms, and validators:
   ```python
   def test_custom_transform():
       transform = CustomDataTransform()
       result = transform.transform({"id": "123", "patient_id": "P1"})
       assert result.source_record_id == "123"
   ```

4. **Document changes**: Update relevant documentation when adding features.

5. **Version your schema**: Use numbered migration files for database changes.
