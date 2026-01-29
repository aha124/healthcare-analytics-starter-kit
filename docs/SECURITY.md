# Security Guide

This guide covers security best practices for deploying the Healthcare Analytics Starter Kit in compliance with HIPAA and healthcare data protection requirements.

## Table of Contents

1. [Overview](#overview)
2. [PHI Protection](#phi-protection)
3. [Encryption](#encryption)
4. [Access Control](#access-control)
5. [Audit Logging](#audit-logging)
6. [Network Security](#network-security)
7. [Deployment Checklist](#deployment-checklist)

---

## Overview

The Healthcare Analytics Starter Kit is designed with HIPAA Technical Safeguards in mind:

| HIPAA Requirement | Implementation |
|-------------------|----------------|
| Access Control | Role-based access via PostgreSQL and Grafana |
| Audit Controls | Comprehensive audit logging |
| Integrity Controls | Data validation and checksums |
| Transmission Security | TLS encryption |
| Encryption | Field-level and at-rest encryption |

**Important**: This starter kit provides tools and patterns for HIPAA compliance, but achieving compliance requires proper configuration, policies, and organizational controls beyond software.

---

## PHI Protection

### Automatic PHI Detection

The `PHIScanner` class automatically detects potential Protected Health Information:

```python
from src.quality.phi_scanner import PHIScanner

scanner = PHIScanner(sensitivity="high")

# Scan any data structure
data = {
    "notes": "Patient SSN: 123-45-6789",
    "contact": "Call at 555-123-4567",
}

findings = scanner.scan_record(data)
for finding in findings:
    print(f"PHI found: {finding.phi_type} in field {finding.field_path}")
```

### PHI Types Detected

| Type | Pattern Examples |
|------|------------------|
| SSN | 123-45-6789, 123456789 |
| Phone | 555-123-4567, (555) 123-4567 |
| Email | user@example.com |
| MRN | MRN: 12345678 |
| Date of Birth | DOB: 01/15/1980 |
| Names | Sensitive field names |
| Addresses | Street address patterns |

### Log Sanitization

Automatic PHI redaction in logs is enabled by default:

```python
from config import setup_logging

# PHI is automatically redacted from logs
setup_logging(
    log_level="INFO",
    sanitize_logs=True,  # Default: True
)

# This will log: "Processing patient: [REDACTED]"
logger.info("Processing patient", patient_name="John Doe")
```

### Sensitive Field Configuration

Configure which fields are considered sensitive:

```python
# In config/logging_config.py
SENSITIVE_KEYS = {
    "ssn",
    "social_security",
    "mrn",
    "medical_record_number",
    "patient_id",
    "dob",
    "date_of_birth",
    "phone",
    "email",
    "address",
    "name",
    "patient_name",
    "first_name",
    "last_name",
}
```

---

## Encryption

### Field-Level Encryption

Encrypt sensitive fields before storage:

```python
from src.utils.encryption import FieldEncryption

# Initialize with a secure key
encryption = FieldEncryption(key=settings.encryption_key)

# Encrypt sensitive data
encrypted_ssn = encryption.encrypt("123-45-6789")
encrypted_dob = encryption.encrypt("1980-01-15")

# Decrypt when needed
original_ssn = encryption.decrypt(encrypted_ssn)
```

### Key Management

```bash
# Generate a secure encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Store in environment variable (never in code)
export ENCRYPTION_KEY="your-generated-key-here"
```

**Key Management Best Practices**:

1. **Never hardcode keys** in source code
2. **Rotate keys periodically** (quarterly recommended)
3. **Use secrets management** (AWS Secrets Manager, HashiCorp Vault)
4. **Separate keys** per environment (dev/staging/prod)

### Deterministic Hashing

For matching records without exposing PHI:

```python
from src.utils.encryption import FieldEncryption

encryption = FieldEncryption()

# Create deterministic hash for matching
hash1 = encryption.hash_for_matching("john.doe@example.com")
hash2 = encryption.hash_for_matching("john.doe@example.com")

# Same input = same hash (for matching)
assert hash1 == hash2

# Original value cannot be recovered from hash
```

### Database Encryption

Enable PostgreSQL encryption at rest:

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:14
    environment:
      # Enable data checksums
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      # Use encrypted volume
      - encrypted_pgdata:/var/lib/postgresql/data
```

---

## Access Control

### Database Users

Create separate database users with minimal privileges:

```sql
-- Read-only analytics user
CREATE USER analytics_reader WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE healthcare_analytics TO analytics_reader;
GRANT USAGE ON SCHEMA staging, dim, fact, metrics TO analytics_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA staging, dim, fact, metrics TO analytics_reader;

-- ETL service account
CREATE USER etl_service WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE healthcare_analytics TO etl_service;
GRANT ALL PRIVILEGES ON SCHEMA staging TO etl_service;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA staging TO etl_service;

-- Admin user (for schema changes only)
CREATE USER admin_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE healthcare_analytics TO admin_user;
```

### Grafana Authentication

Configure Grafana authentication:

```ini
# grafana/grafana.ini
[auth]
disable_login_form = false

[auth.ldap]
enabled = true
config_file = /etc/grafana/ldap.toml

[auth.generic_oauth]
enabled = true
name = "Your SSO"
client_id = "your-client-id"
client_secret = "your-client-secret"
scopes = "openid profile email"
auth_url = "https://your-idp.com/oauth/authorize"
token_url = "https://your-idp.com/oauth/token"
```

### Row-Level Security

Implement row-level security for multi-tenant deployments:

```sql
-- Enable RLS on sensitive tables
ALTER TABLE staging.patients ENABLE ROW LEVEL SECURITY;

-- Create policy for facility-based access
CREATE POLICY facility_access ON staging.patients
    FOR ALL
    USING (facility_id = current_setting('app.current_facility'));

-- Set facility context in application
SET app.current_facility = 'FAC-001';
```

---

## Audit Logging

### Audit Logger Usage

```python
from src.quality.audit_logger import AuditLogger

audit = AuditLogger()

# Log data access
audit.log_access(
    user_id="analyst@hospital.org",
    action="read",
    resource_type="patient",
    resource_id="PAT-12345",
    success=True,
)

# Log authentication
audit.log_authentication(
    user_id="analyst@hospital.org",
    auth_method="oauth",
    success=True,
    ip_address="192.168.1.100",
)

# Log data exports
audit.log_export(
    user_id="analyst@hospital.org",
    export_type="csv",
    record_count=1500,
    destination="secure-sftp",
)
```

### Audit Log Format

Audit logs are structured JSON for easy parsing:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "audit_type": "data_access",
  "user_id": "analyst@hospital.org",
  "action": "read",
  "resource_type": "patient",
  "resource_id": "[REDACTED]",
  "success": true,
  "service": "healthcare-analytics-starter-kit"
}
```

### Audit Retention

Configure audit log retention:

```python
# Keep audit logs for 7 years (HIPAA requirement: 6 years)
AUDIT_RETENTION_DAYS = 2555

# Archive to long-term storage
audit = AuditLogger(
    archive_path="/secure/audit/archive",
    retention_days=AUDIT_RETENTION_DAYS,
)
```

### Database Audit

Enable PostgreSQL statement logging:

```sql
-- In postgresql.conf
log_statement = 'mod'  -- Log INSERT, UPDATE, DELETE
log_min_duration_statement = 0  -- Log all queries
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

---

## Network Security

### TLS Configuration

Enable TLS for all connections:

```yaml
# docker-compose.yml
services:
  postgres:
    environment:
      POSTGRES_SSL: "on"
    volumes:
      - ./certs/server.crt:/var/lib/postgresql/server.crt
      - ./certs/server.key:/var/lib/postgresql/server.key

  grafana:
    environment:
      GF_SERVER_PROTOCOL: https
      GF_SERVER_CERT_FILE: /etc/grafana/certs/grafana.crt
      GF_SERVER_CERT_KEY: /etc/grafana/certs/grafana.key
```

### Database Connection Security

```python
# config/settings.py
class DatabaseSettings(BaseSettings):
    ssl_mode: str = "require"  # Options: disable, allow, prefer, require, verify-ca, verify-full
    ssl_cert: str | None = None
    ssl_key: str | None = None
    ssl_root_cert: str | None = None
```

### Firewall Rules

Recommended firewall configuration:

```bash
# Allow only necessary ports
# PostgreSQL: Internal only
iptables -A INPUT -p tcp --dport 5432 -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -p tcp --dport 5432 -j DROP

# Grafana: HTTPS only
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 3000 -j DROP  # Block HTTP

# HL7 MLLP: Internal only
iptables -A INPUT -p tcp --dport 2575 -s 10.0.0.0/8 -j ACCEPT
```

---

## Deployment Checklist

### Pre-Deployment

- [ ] Generate unique encryption keys for production
- [ ] Configure TLS certificates
- [ ] Set up database users with minimal privileges
- [ ] Enable audit logging
- [ ] Configure log sanitization
- [ ] Review and restrict network access
- [ ] Set up secrets management
- [ ] Configure backup encryption

### Environment Configuration

- [ ] `ENCRYPTION_KEY` is set and secure
- [ ] `POSTGRES_PASSWORD` is strong and unique
- [ ] `GRAFANA_ADMIN_PASSWORD` is changed from default
- [ ] `SANITIZE_LOGS=true`
- [ ] `LOG_LEVEL=INFO` (not DEBUG in production)
- [ ] TLS enabled for all connections

### Access Control

- [ ] Database users have minimal required privileges
- [ ] Grafana authentication configured (LDAP/OAuth)
- [ ] Row-level security enabled if multi-tenant
- [ ] API authentication configured for FHIR connectors

### Monitoring

- [ ] Audit logs being collected
- [ ] Failed authentication alerts configured
- [ ] Unusual data access patterns monitored
- [ ] Log retention policy implemented

### Backup & Recovery

- [ ] Database backups encrypted
- [ ] Backup access restricted
- [ ] Recovery procedures tested
- [ ] Audit log backups separate from data

### Documentation

- [ ] Security policies documented
- [ ] Incident response plan in place
- [ ] User access procedures documented
- [ ] Key rotation procedures documented

---

## Incident Response

### Data Breach Response

1. **Contain**: Immediately restrict access to affected systems
2. **Assess**: Determine scope of exposed data
3. **Notify**: Follow HIPAA breach notification requirements
4. **Remediate**: Fix vulnerability and restore systems
5. **Document**: Maintain detailed incident log

### HIPAA Breach Notification

- **60-day rule**: Notify HHS within 60 days of discovery
- **500+ records**: Media notification required
- **Document**: Maintain breach log for 6 years

### Contact

For security concerns related to this starter kit:
- Open a private security advisory on GitHub
- Email: security@your-organization.com

---

*This guide provides security patterns and recommendations. Consult with your compliance and security teams for organization-specific requirements.*
