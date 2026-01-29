# Healthcare Analytics Starter Kit

A production-ready, EMR-agnostic analytics platform for healthcare organizations. Built with Python, PostgreSQL, and Grafana.

## Overview

The Healthcare Analytics Starter Kit provides everything you need to stand up a modern healthcare analytics infrastructure:

- **EMR-Agnostic Connectors**: Connect to Epic, Cerner, MEDITECH, or any EMR via FHIR R4, HL7 v2.x, CSV, or direct database
- **Healthcare Data Models**: Pre-built transforms for patients, encounters, diagnoses, procedures, labs, vitals, and medications
- **Star Schema Warehouse**: Optimized dimensional model with staging, dimensions, and facts
- **Executive Dashboards**: Four Grafana dashboards ready for deployment
- **HIPAA-Conscious Design**: PHI scanning, audit logging, and field-level encryption built-in

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
│   Epic      │   Cerner    │  MEDITECH   │    CSV      │   Direct    │
│   (FHIR)    │   (FHIR)    │   (HL7)     │   Files     │   Database  │
└──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┴──────┬──────┘
       │             │             │             │             │
       └─────────────┴──────┬──────┴─────────────┴─────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      CONNECTOR LAYER                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │    FHIR     │ │    HL7      │ │    CSV      │ │  Database   │   │
│  │  Connector  │ │  Connector  │ │  Connector  │ │  Connector  │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TRANSFORM LAYER                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ Patients │ │Encounters│ │Diagnoses │ │   Labs   │ │  Vitals  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA WAREHOUSE                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │    STAGING      │  │   DIMENSIONAL   │  │     METRICS     │     │
│  │  Raw data from  │  │   Star schema   │  │   Aggregated    │     │
│  │    sources      │→ │   for analysis  │→ │     KPIs        │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GRAFANA DASHBOARDS                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  Executive  │ │   Patient   │ │   Quality   │ │ Operational │   │
│  │   Summary   │ │    Flow     │ │   Metrics   │ │    KPIs     │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/healthcare-analytics-starter-kit.git
cd healthcare-analytics-starter-kit

# Copy environment template
cp .env.example .env

# Edit .env with your settings
vim .env

# Start infrastructure (PostgreSQL + Grafana)
docker-compose up -d

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database schema
python -m scripts.init_database

# Load sample data (optional, for testing)
python -m scripts.load_sample_data

# Run the daily refresh pipeline
python -m pipelines.scheduled_tasks daily_refresh
```

### Access Grafana

Open http://localhost:3000 in your browser:
- Username: `admin`
- Password: Set in your `.env` file (default: `admin`)

Four dashboards are pre-configured:
1. **Executive Summary** - High-level KPIs for leadership
2. **Patient Flow** - Census, ED throughput, admissions/discharges
3. **Quality Metrics** - Readmissions, HAIs, core measures
4. **Operational KPIs** - LOS, occupancy, bed turns

## Project Structure

```
healthcare-analytics-starter-kit/
├── config/                     # Configuration management
│   ├── settings.py            # Environment-based settings
│   └── logging_config.py      # Structured logging setup
├── src/
│   ├── connectors/            # Data source connectors
│   │   ├── fhir_connector.py  # FHIR R4 API (Epic, Cerner)
│   │   ├── hl7_connector.py   # HL7 v2.x messages
│   │   ├── csv_connector.py   # CSV file import
│   │   └── database_connector.py  # Direct DB queries
│   ├── transforms/            # Data transformation
│   │   ├── patient_demographics.py
│   │   ├── encounters.py
│   │   ├── diagnoses.py
│   │   ├── procedures.py
│   │   ├── lab_results.py
│   │   ├── vitals.py
│   │   └── medications.py
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── staging.py         # Raw data tables
│   │   ├── dimensional.py     # Star schema
│   │   └── metrics.py         # Pre-computed metrics
│   ├── loaders/               # Data loading
│   │   ├── postgres_loader.py # Bulk upsert operations
│   │   └── incremental_loader.py  # Watermark tracking
│   ├── quality/               # Data quality
│   │   ├── validators.py      # Record validation
│   │   ├── phi_scanner.py     # PHI detection
│   │   └── audit_logger.py    # HIPAA audit trail
│   └── utils/                 # Utilities
│       ├── encryption.py      # Field-level encryption
│       └── date_utils.py      # Healthcare date helpers
├── sql/
│   ├── schema/                # DDL scripts
│   ├── views/                 # Materialized views
│   └── seed/                  # Sample data
├── grafana/
│   ├── provisioning/          # Auto-provisioning
│   └── dashboards/            # Dashboard JSON
├── pipelines/                 # ETL orchestration
│   ├── daily_refresh.py       # Main ETL pipeline
│   └── scheduled_tasks.py     # Cron-ready tasks
├── tests/                     # Test suite
├── docs/                      # Documentation
├── examples/                  # Integration examples
├── docker-compose.yml         # Infrastructure
├── requirements.txt           # Python dependencies
└── setup.py                   # Package setup
```

## EMR Integration

### Epic (FHIR R4)

```python
from src.connectors import FHIRConnector

connector = FHIRConnector(
    base_url="https://your-epic-instance.com/api/FHIR/R4",
    auth_method="smart_backend",
    client_id="your-client-id",
    private_key_path="/path/to/private-key.pem",
)

for patient in connector.fetch_patients(since=yesterday):
    print(patient["mrn"])
```

### Cerner (FHIR R4)

```python
from src.connectors import FHIRConnector

connector = FHIRConnector(
    base_url="https://fhir-open.cerner.com/r4/your-tenant",
    auth_method="oauth2",
    client_id="your-client-id",
    client_secret="your-client-secret",
    token_url="https://authorization.cerner.com/tenants/your-tenant/protocols/oauth2/profiles/smart-v1/token",
)
```

### MEDITECH (HL7 v2.x)

```python
from src.connectors import HL7Connector

connector = HL7Connector(
    message_directory="/path/to/hl7/messages",
)

for encounter in connector.fetch_encounters():
    print(encounter["source_encounter_id"])
```

### CSV Import

```python
from src.connectors import CSVConnector

connector = CSVConnector(
    data_directory="/path/to/csv/exports",
)
```

See [docs/EMR_INTEGRATION_GUIDE.md](docs/EMR_INTEGRATION_GUIDE.md) for detailed setup instructions.

## Configuration

All settings are managed via environment variables. Copy `.env.example` to `.env`:

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=healthcare_analytics
POSTGRES_USER=hask_user
POSTGRES_PASSWORD=change_me_in_production

# FHIR API (Epic/Cerner)
FHIR_BASE_URL=https://your-emr.com/api/FHIR/R4
FHIR_AUTH_METHOD=smart_backend
FHIR_CLIENT_ID=your-client-id

# Security
ENCRYPTION_KEY=your-32-byte-key-here
LOG_LEVEL=INFO
SANITIZE_LOGS=true
```

## Scheduled Tasks

Configure cron jobs for automated data refresh:

```cron
# Daily refresh at 2 AM
0 2 * * * /path/to/venv/bin/python -m pipelines.scheduled_tasks daily_refresh

# Hourly metrics update
0 * * * * /path/to/venv/bin/python -m pipelines.scheduled_tasks hourly_metrics

# Monthly aggregations on 1st at 4 AM
0 4 1 * * /path/to/venv/bin/python -m pipelines.scheduled_tasks monthly_aggregations
```

## Security

This starter kit includes HIPAA-conscious design patterns:

- **PHI Scanning**: Automatic detection of sensitive data in logs and outputs
- **Audit Logging**: Comprehensive audit trail for data access
- **Field Encryption**: Encrypt sensitive fields at rest
- **Log Sanitization**: Automatic redaction of PHI from logs

See [docs/SECURITY.md](docs/SECURITY.md) for detailed security guidance.

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_transforms.py
```

## Documentation

- [EMR Integration Guide](docs/EMR_INTEGRATION_GUIDE.md) - Connect to Epic, Cerner, MEDITECH
- [Security Guide](docs/SECURITY.md) - HIPAA compliance and security best practices
- [Customization Guide](docs/CUSTOMIZATION.md) - Extend and customize the platform

## License

MIT License - See [LICENSE](LICENSE) for details.

---

Built with care for healthcare organizations.
