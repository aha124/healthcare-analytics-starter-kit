# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-01-29

### Added
- Initial release
- EMR connectors: FHIR R4, HL7 v2.x, CSV, direct database
- PostgreSQL dimensional model with staging, dimensional, and metrics layers
- 4 Grafana dashboards: Executive Summary, Patient Flow, Quality Metrics, Operational KPIs
- Docker Compose stack for local development
- PHI detection and log sanitization utilities
- Field-level encryption helpers
- HIPAA-conscious audit logging
- Comprehensive EMR integration guide for Epic, Cerner, MEDITECH
- Synthetic sample data (500 patients, 2000 encounters)
- Full test suite with pytest

### Security
- Automatic PHI redaction in logs
- Environment-based configuration (no hardcoded secrets)
- Parameterized SQL queries throughout
