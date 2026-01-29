"""Environment-based configuration settings for Healthcare Analytics Starter Kit."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    model_config = SettingsConfigDict(env_prefix="POSTGRES_")

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    db: str = Field(default="healthcare_analytics", alias="POSTGRES_DB")
    user: str = Field(default="hask_user", description="Database user")
    password: SecretStr = Field(
        default=SecretStr("changeme_in_production"),
        description="Database password",
    )
    sslmode: str = Field(default="prefer", description="SSL mode")
    pool_size: int = Field(default=10, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=20, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")

    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string."""
        return (
            f"postgresql+psycopg2://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}?sslmode={self.sslmode}"
        )

    @property
    def async_connection_string(self) -> str:
        """Generate async SQLAlchemy connection string."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class FHIRSettings(BaseSettings):
    """FHIR API connector configuration."""

    model_config = SettingsConfigDict(env_prefix="FHIR_")

    base_url: str = Field(
        default="",
        description="FHIR server base URL",
    )
    client_id: str = Field(default="", description="OAuth2 client ID")
    client_secret: SecretStr = Field(
        default=SecretStr(""),
        description="OAuth2 client secret",
    )
    token_url: str = Field(default="", description="OAuth2 token endpoint")
    scopes: str = Field(
        default="patient/*.read",
        description="OAuth2 scopes (comma-separated)",
    )
    timeout: int = Field(default=30, description="Request timeout in seconds")
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    @property
    def scope_list(self) -> list[str]:
        """Parse scopes string into list."""
        return [s.strip() for s in self.scopes.split(",") if s.strip()]


class EpicSettings(BaseSettings):
    """Epic-specific FHIR configuration."""

    model_config = SettingsConfigDict(env_prefix="EPIC_")

    private_key_path: Path | None = Field(
        default=None,
        description="Path to Epic private key PEM file",
    )
    client_id: str = Field(default="", description="Epic client ID")
    token_url: str = Field(
        default="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        description="Epic token endpoint",
    )


class CernerSettings(BaseSettings):
    """Cerner/Oracle Health configuration."""

    model_config = SettingsConfigDict(env_prefix="CERNER_")

    system_account_id: str = Field(default="", description="System account ID")
    secret: SecretStr = Field(default=SecretStr(""), description="Cerner secret")
    base_url: str = Field(default="", description="Cerner FHIR base URL")


class HL7Settings(BaseSettings):
    """HL7 v2.x listener configuration."""

    model_config = SettingsConfigDict(env_prefix="HL7_")

    listener_host: str = Field(default="0.0.0.0", description="HL7 listener host")
    listener_port: int = Field(default=2575, description="HL7 listener port")
    mllp_timeout: int = Field(default=30, description="MLLP timeout in seconds")


class CSVSettings(BaseSettings):
    """CSV file ingestion configuration."""

    model_config = SettingsConfigDict(env_prefix="CSV_")

    import_path: Path = Field(
        default=Path("/data/imports"),
        description="Directory for incoming CSV files",
    )
    archive_path: Path = Field(
        default=Path("/data/archives"),
        description="Directory for processed CSV files",
    )
    error_path: Path = Field(
        default=Path("/data/errors"),
        description="Directory for failed CSV files",
    )
    file_pattern: str = Field(default="*.csv", description="File pattern to match")


class EMRReplicaSettings(BaseSettings):
    """Direct EMR database read replica configuration."""

    model_config = SettingsConfigDict(env_prefix="EMR_REPLICA_")

    host: str = Field(default="", description="EMR replica host")
    port: int = Field(default=1433, description="EMR replica port")
    db: str = Field(default="", alias="EMR_REPLICA_DB")
    user: str = Field(default="", description="EMR replica user")
    password: SecretStr = Field(default=SecretStr(""), description="EMR replica password")
    driver: str = Field(default="mssql+pyodbc", description="SQLAlchemy driver")

    @property
    def connection_string(self) -> str:
        """Generate connection string for EMR replica."""
        if not self.host:
            return ""
        return (
            f"{self.driver}://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.db}"
        )


class SecuritySettings(BaseSettings):
    """Security and encryption configuration."""

    encryption_key: SecretStr = Field(
        default=SecretStr(""),
        alias="ENCRYPTION_KEY",
        description="Fernet encryption key for field-level encryption",
    )
    audit_log_path: Path = Field(
        default=Path("/var/log/healthcare-analytics/audit.log"),
        alias="AUDIT_LOG_PATH",
    )
    audit_log_level: str = Field(default="INFO", alias="AUDIT_LOG_LEVEL")
    phi_scan_sensitivity: Literal["low", "medium", "high"] = Field(
        default="high",
        alias="PHI_SCAN_SENSITIVITY",
    )


class PipelineSettings(BaseSettings):
    """Data pipeline configuration."""

    model_config = SettingsConfigDict(env_prefix="PIPELINE_")

    batch_size: int = Field(default=1000, description="Batch size for data processing")
    max_workers: int = Field(default=4, description="Maximum parallel workers")
    retry_attempts: int = Field(default=3, description="Number of retry attempts")
    retry_delay: int = Field(default=60, description="Delay between retries (seconds)")
    staging_retention_days: int = Field(
        default=30,
        alias="STAGING_RETENTION_DAYS",
    )
    audit_retention_days: int = Field(
        default=2555,
        alias="AUDIT_RETENTION_DAYS",
    )


class Settings(BaseSettings):
    """Main application settings aggregating all configuration sections."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: Literal["json", "text"] = Field(default="json", alias="LOG_FORMAT")
    log_file: Path | None = Field(default=None, alias="LOG_FILE")

    # Grafana
    grafana_port: int = Field(default=3000, alias="GRAFANA_PORT")
    grafana_admin_user: str = Field(default="admin", alias="GRAFANA_ADMIN_USER")
    grafana_admin_password: SecretStr = Field(
        default=SecretStr("admin"),
        alias="GRAFANA_ADMIN_PASSWORD",
    )

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    fhir: FHIRSettings = Field(default_factory=FHIRSettings)
    epic: EpicSettings = Field(default_factory=EpicSettings)
    cerner: CernerSettings = Field(default_factory=CernerSettings)
    hl7: HL7Settings = Field(default_factory=HL7Settings)
    csv: CSVSettings = Field(default_factory=CSVSettings)
    emr_replica: EMRReplicaSettings = Field(default_factory=EMRReplicaSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)

    @field_validator("environment", mode="before")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate and normalize environment value."""
        return v.lower() if isinstance(v, str) else v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings: Application configuration settings.

    Example:
        >>> settings = get_settings()
        >>> print(settings.database.host)
        localhost
    """
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Useful for testing."""
    get_settings.cache_clear()
