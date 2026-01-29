# EMR Integration Guide

This guide provides detailed instructions for connecting the Healthcare Analytics Starter Kit to major Electronic Medical Record (EMR) systems.

## Table of Contents

1. [Epic Integration](#epic-integration)
2. [Cerner Integration](#cerner-integration)
3. [MEDITECH Integration](#meditech-integration)
4. [Generic FHIR Integration](#generic-fhir-integration)
5. [Direct Database Connection](#direct-database-connection)
6. [CSV/Flat File Import](#csvflat-file-import)
7. [Troubleshooting](#troubleshooting)

---

## Epic Integration

Epic supports FHIR R4 APIs through their App Orchard marketplace. There are two main integration patterns:

### Option 1: SMART Backend Services (Recommended)

This is Epic's preferred method for backend-to-backend integrations. Uses JWT-based authentication without user interaction.

#### Prerequisites

1. **App Orchard Registration**: Register your application at [App Orchard](https://appmarket.epic.com/)
2. **Client Credentials**: Obtain your `client_id` from Epic
3. **RSA Key Pair**: Generate a 2048-bit RSA key pair for JWT signing

#### Generate RSA Keys

```bash
# Generate private key
openssl genrsa -out epic_private_key.pem 2048

# Generate public key
openssl rsa -in epic_private_key.pem -pubout -out epic_public_key.pem
```

Upload the public key to your App Orchard application configuration.

#### Configuration

```bash
# .env file
FHIR_ENABLED=true
FHIR_BASE_URL=https://your-epic-instance.com/api/FHIR/R4
FHIR_AUTH_METHOD=smart_backend
FHIR_CLIENT_ID=your-app-orchard-client-id
FHIR_PRIVATE_KEY_PATH=/path/to/epic_private_key.pem
FHIR_TOKEN_URL=https://your-epic-instance.com/oauth2/token
```

#### Usage

```python
from src.connectors import FHIRConnector
from datetime import datetime, timedelta

# Initialize connector
connector = FHIRConnector(
    base_url="https://your-epic-instance.com/api/FHIR/R4",
    auth_method="smart_backend",
    client_id="your-client-id",
    private_key_path="/path/to/epic_private_key.pem",
    token_url="https://your-epic-instance.com/oauth2/token",
)

# Fetch patients updated in the last 24 hours
yesterday = datetime.utcnow() - timedelta(days=1)
for patient in connector.fetch_patients(since=yesterday):
    print(f"Patient: {patient['mrn']} - {patient['last_name']}")

# Fetch encounters for specific patients
patient_ids = ["E12345", "E67890"]
for encounter in connector.fetch_encounters(patient_ids=patient_ids):
    print(f"Encounter: {encounter['source_encounter_id']}")
```

#### Available FHIR Resources

| Resource | Epic Support | Notes |
|----------|--------------|-------|
| Patient | Full | Demographics, identifiers |
| Encounter | Full | Visits, admissions |
| Condition | Full | Diagnoses |
| Procedure | Full | Surgical/clinical procedures |
| Observation | Full | Labs, vitals, assessments |
| MedicationRequest | Full | Medication orders |
| DiagnosticReport | Full | Lab reports, imaging |
| AllergyIntolerance | Full | Allergies |

### Option 2: OAuth 2.0 Client Credentials

For organizations that haven't implemented SMART Backend Services:

```python
connector = FHIRConnector(
    base_url="https://your-epic-instance.com/api/FHIR/R4",
    auth_method="oauth2",
    client_id="your-client-id",
    client_secret="your-client-secret",
    token_url="https://your-epic-instance.com/oauth2/token",
)
```

### Epic-Specific Considerations

1. **Rate Limits**: Epic typically allows 10-20 requests/second. The connector handles rate limiting automatically.

2. **Pagination**: Epic returns max 100 resources per page. The connector handles pagination automatically.

3. **Custom Extensions**: Epic uses extensions for some data:
   ```python
   # The connector extracts common extensions automatically:
   # - Race/ethnicity (US Core extensions)
   # - Primary care provider
   # - Patient preferences
   ```

4. **MyChart Flag**: Exclude MyChart-blocked patients:
   ```python
   connector = FHIRConnector(
       # ...
       exclude_mychart_blocked=True,
   )
   ```

---

## Cerner Integration

Cerner (now Oracle Health) provides FHIR R4 APIs through their code.cerner.com platform.

### Prerequisites

1. **Developer Account**: Register at [code.cerner.com](https://code.cerner.com/)
2. **Application Registration**: Create a new application
3. **OAuth Credentials**: Obtain client_id and client_secret

### Configuration

```bash
# .env file
FHIR_ENABLED=true
FHIR_BASE_URL=https://fhir-ehr.cerner.com/r4/your-tenant-id
FHIR_AUTH_METHOD=oauth2
FHIR_CLIENT_ID=your-cerner-client-id
FHIR_CLIENT_SECRET=your-cerner-client-secret
FHIR_TOKEN_URL=https://authorization.cerner.com/tenants/your-tenant-id/protocols/oauth2/profiles/smart-v1/token
```

### Usage

```python
from src.connectors import FHIRConnector

connector = FHIRConnector(
    base_url="https://fhir-ehr.cerner.com/r4/your-tenant-id",
    auth_method="oauth2",
    client_id="your-client-id",
    client_secret="your-client-secret",
    token_url="https://authorization.cerner.com/tenants/your-tenant-id/protocols/oauth2/profiles/smart-v1/token",
)

# Fetch all patients
for patient in connector.fetch_patients():
    print(f"Patient: {patient['mrn']}")
```

### Cerner-Specific Considerations

1. **Tenant IDs**: Each Cerner environment has a unique tenant ID. Development and production use different IDs.

2. **Sandbox Testing**: Use Cerner's sandbox for development:
   ```python
   # Sandbox URL
   base_url = "https://fhir-open.cerner.com/r4/ec2458f2-1e24-41c8-b71b-0e701af7583d"
   ```

3. **Resource Availability**: Some resources may require additional permissions:
   - Patient: Base access
   - Encounter: Requires `system/Encounter.read`
   - Condition: Requires `system/Condition.read`

4. **MillenniumPersonId**: Cerner uses internal IDs; map to MRN using identifiers:
   ```python
   # The connector automatically extracts MRN from identifiers
   mrn = patient.get("mrn")  # Extracted from identifier where type="MR"
   ```

---

## MEDITECH Integration

MEDITECH systems typically provide data via HL7 v2.x messages or flat file exports.

### Option 1: HL7 v2.x Message Interface

#### Prerequisites

1. **Interface Engine**: MEDITECH Data Repository (DR) or Cloverleaf/Rhapsody
2. **MLLP Connection**: Network connectivity for HL7 messages
3. **Message Types**: Configure ADT, ORU, ORM messages

#### Configuration

```bash
# .env file
HL7_ENABLED=true
HL7_MESSAGE_DIRECTORY=/path/to/hl7/messages
# Or for MLLP listener:
HL7_MLLP_HOST=0.0.0.0
HL7_MLLP_PORT=2575
```

#### Usage with File Directory

```python
from src.connectors import HL7Connector
from pathlib import Path

connector = HL7Connector(
    message_directory=Path("/data/hl7/incoming"),
)

# Process patient messages (ADT)
for patient in connector.fetch_patients():
    print(f"Patient: {patient['mrn']} from message {patient['_message_id']}")

# Process lab results (ORU)
for lab in connector.fetch_lab_results():
    print(f"Lab: {lab['test_code']} = {lab['result_value']}")
```

#### Supported HL7 Message Types

| Message Type | Trigger Events | Data Extracted |
|--------------|----------------|----------------|
| ADT (Patient) | A01, A02, A03, A04, A08 | Demographics, visit info |
| ORU (Results) | R01 | Lab results, vital signs |
| ORM (Orders) | O01 | Medication orders, procedures |
| DFT (Charges) | P03 | Billing/charge data |

### Option 2: MEDITECH Flat File Export

Configure MEDITECH to export data to CSV/flat files:

```python
from src.connectors import CSVConnector
from pathlib import Path

connector = CSVConnector(
    data_directory=Path("/data/meditech/exports"),
    file_patterns={
        "patients": "PAT_EXPORT_*.txt",
        "encounters": "ENC_EXPORT_*.txt",
        "diagnoses": "DX_EXPORT_*.txt",
    },
    delimiter="|",  # MEDITECH typically uses pipe delimiter
    encoding="cp1252",  # Windows encoding
)
```

### MEDITECH-Specific Considerations

1. **Character Encoding**: MEDITECH often uses Windows-1252 encoding:
   ```python
   connector = CSVConnector(encoding="cp1252")
   ```

2. **Date Formats**: MEDITECH may use YYYYMMDD format:
   ```python
   # The DateUtils class handles this automatically
   from src.utils.date_utils import parse_date
   parsed = parse_date("20240115")  # Returns date(2024, 1, 15)
   ```

3. **Field Mapping**: MEDITECH field names may differ:
   ```python
   # Custom field mapping
   connector = CSVConnector(
       field_mapping={
           "PT_MRN": "mrn",
           "PT_LNAME": "last_name",
           "PT_FNAME": "first_name",
       }
   )
   ```

---

## Generic FHIR Integration

For any FHIR R4-compliant system:

### Basic Setup

```python
from src.connectors import FHIRConnector

# No authentication (rare in production)
connector = FHIRConnector(
    base_url="https://fhir.example.com/r4",
    auth_method="none",
)

# Basic authentication
connector = FHIRConnector(
    base_url="https://fhir.example.com/r4",
    auth_method="basic",
    username="api_user",
    password="api_password",
)

# Bearer token
connector = FHIRConnector(
    base_url="https://fhir.example.com/r4",
    auth_method="bearer",
    access_token="your-access-token",
)

# OAuth 2.0
connector = FHIRConnector(
    base_url="https://fhir.example.com/r4",
    auth_method="oauth2",
    client_id="your-client-id",
    client_secret="your-client-secret",
    token_url="https://auth.example.com/oauth/token",
)
```

### Custom Resource Mapping

Override the default FHIR resource normalization:

```python
from src.connectors import FHIRConnector

class CustomFHIRConnector(FHIRConnector):
    def _normalize_patient(self, resource):
        # Custom normalization logic
        base = super()._normalize_patient(resource)

        # Add custom fields
        base["custom_field"] = resource.get("extension", [{}])[0].get("valueString")

        return base
```

---

## Direct Database Connection

For direct SQL access to EMR databases (requires appropriate permissions):

### Configuration

```bash
# .env file
SOURCE_DB_HOST=emr-database.internal
SOURCE_DB_PORT=1433
SOURCE_DB_NAME=EMR_PROD
SOURCE_DB_USER=analytics_reader
SOURCE_DB_PASSWORD=secure_password
SOURCE_DB_DRIVER=mssql+pyodbc
```

### Usage

```python
from src.connectors import DatabaseConnector

connector = DatabaseConnector(
    connection_string="mssql+pyodbc://user:pass@server/database?driver=ODBC+Driver+17+for+SQL+Server"
)

# Custom SQL queries
patients_sql = """
    SELECT
        PatientID as source_patient_id,
        MRN as mrn,
        FirstName as first_name,
        LastName as last_name,
        DOB as date_of_birth,
        Sex as gender
    FROM dbo.Patient
    WHERE ModifiedDate >= :since
"""

for patient in connector.fetch_with_query(patients_sql, since=yesterday):
    print(patient)
```

### Security Considerations

1. **Read-Only Access**: Always use read-only database credentials
2. **Network Isolation**: Use VPN or private network connections
3. **Query Optimization**: Index-aware queries to avoid EMR performance impact
4. **Audit Trail**: Ensure database access is logged

---

## CSV/Flat File Import

For batch imports from any source:

### Configuration

```bash
# .env file
CSV_ENABLED=true
CSV_DATA_DIRECTORY=/data/imports
CSV_ARCHIVE_DIRECTORY=/data/imports/archive
```

### Usage

```python
from src.connectors import CSVConnector
from pathlib import Path

connector = CSVConnector(
    data_directory=Path("/data/imports"),
    archive_after_processing=True,
)

# Standard CSV
for patient in connector.fetch_patients():
    print(patient)

# Custom file patterns
connector = CSVConnector(
    data_directory=Path("/data/imports"),
    file_patterns={
        "patients": "demographics_*.csv",
        "encounters": "visits_*.csv",
    },
)
```

### Expected CSV Formats

#### patients.csv
```csv
source_patient_id,mrn,first_name,last_name,date_of_birth,gender,address_line1,address_city,address_state,address_zip
PAT001,MRN-001,John,Smith,1980-05-15,M,123 Main St,Springfield,IL,62701
```

#### encounters.csv
```csv
source_encounter_id,source_patient_id,encounter_type,admit_datetime,discharge_datetime,primary_diagnosis_code
ENC001,PAT001,inpatient,2024-01-15 10:30:00,2024-01-18 14:00:00,J18.9
```

---

## Troubleshooting

### Common Issues

#### 1. Authentication Failures

**Epic SMART Backend Services**
```
Error: JWT validation failed
```
- Verify public key is uploaded to App Orchard
- Check client_id matches App Orchard registration
- Ensure token URL is correct for your Epic version

**Cerner OAuth**
```
Error: invalid_client
```
- Verify client_id and client_secret
- Check tenant ID in URLs
- Ensure application is approved for your environment

#### 2. Rate Limiting

```
Error: 429 Too Many Requests
```
The connector handles rate limiting automatically, but you can adjust:
```python
connector = FHIRConnector(
    requests_per_second=5,  # Reduce from default
    retry_after_429=True,
)
```

#### 3. Timeout Errors

```
Error: Connection timeout
```
Increase timeout settings:
```python
connector = FHIRConnector(
    timeout_seconds=60,  # Default is 30
)
```

#### 4. SSL Certificate Issues

```
Error: SSL certificate verify failed
```
For development only (never in production):
```python
connector = FHIRConnector(
    verify_ssl=False,  # ONLY for development
)
```

For production, install the CA certificate:
```bash
pip install certifi
export SSL_CERT_FILE=/path/to/ca-bundle.crt
```

### Logging

Enable debug logging for troubleshooting:

```python
from config import setup_logging

setup_logging(log_level="DEBUG", log_format="text")
```

This will show:
- API request/response details
- Authentication flow
- Data transformation steps

### Support Resources

- **Epic**: App Orchard support portal
- **Cerner**: code.cerner.com forums
- **MEDITECH**: Your MEDITECH administrator
- **This Kit**: Open an issue on GitHub
