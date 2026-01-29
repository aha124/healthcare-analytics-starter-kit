"""Logging configuration for Healthcare Analytics Starter Kit."""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, Processor

# Custom processors for healthcare-specific logging


def add_timestamp(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO 8601 timestamp to log events."""
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def add_service_context(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service context for healthcare analytics."""
    event_dict["service"] = "healthcare-analytics-starter-kit"
    return event_dict


def sanitize_phi(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Sanitize potential PHI from log messages.

    This processor redacts common PHI patterns to prevent accidental logging
    of protected health information.
    """
    sensitive_keys = {
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

    def redact_value(key: str, value: Any) -> Any:
        """Redact sensitive values."""
        if isinstance(value, dict):
            return {k: redact_value(k, v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact_value(key, item) for item in value]
        if key.lower() in sensitive_keys:
            return "[REDACTED]"
        return value

    for key in list(event_dict.keys()):
        event_dict[key] = redact_value(key, event_dict[key])

    return event_dict


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: Path | None = None,
    sanitize_logs: bool = True,
) -> None:
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Output format ('json' or 'text').
        log_file: Optional path to log file.
        sanitize_logs: Whether to sanitize potential PHI from logs.

    Example:
        >>> setup_logging(log_level="DEBUG", log_format="text")
        >>> logger = get_logger("my_module")
        >>> logger.info("Starting process", component="connector")
    """
    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_timestamp,
        add_service_context,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Add PHI sanitization if enabled
    if sanitize_logs:
        processors.append(sanitize_phi)

    # Add format-specific processor
    if log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=sys.stdout.isatty(),
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper()),
        handlers=_get_handlers(log_file),
    )

    # Set levels for noisy libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if log_level.upper() == "DEBUG" else logging.WARNING
    )


def _get_handlers(log_file: Path | None) -> list[logging.Handler]:
    """
    Get logging handlers based on configuration.

    Args:
        log_file: Optional path to log file.

    Returns:
        List of configured logging handlers.
    """
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        handlers.append(file_handler)

    return handlers


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the calling module).

    Returns:
        Configured structlog bound logger.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started", patient_count=100)
    """
    return structlog.get_logger(name)


class AuditLogger:
    """
    Specialized logger for HIPAA audit trail requirements.

    This logger creates audit records that comply with HIPAA requirements
    for tracking access to protected health information.
    """

    def __init__(self, audit_log_path: Path | None = None):
        """
        Initialize audit logger.

        Args:
            audit_log_path: Path to audit log file.
        """
        self.logger = get_logger("audit")
        self.audit_log_path = audit_log_path

        if audit_log_path:
            audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_access(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        success: bool = True,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a data access event.

        Args:
            user_id: Identifier of the user/system performing the action.
            action: Type of action (read, write, delete, export).
            resource_type: Type of resource accessed (patient, encounter, etc.).
            resource_id: Identifier of the specific resource (redacted in logs).
            success: Whether the action was successful.
            details: Additional context about the access.
        """
        audit_record = {
            "audit_type": "data_access",
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": "[REDACTED]" if resource_id else None,
            "success": success,
            "details": details or {},
        }

        if success:
            self.logger.info("Data access", **audit_record)
        else:
            self.logger.warning("Data access failed", **audit_record)

    def log_authentication(
        self,
        user_id: str,
        auth_method: str,
        success: bool,
        ip_address: str | None = None,
        failure_reason: str | None = None,
    ) -> None:
        """
        Log an authentication event.

        Args:
            user_id: Identifier of the user attempting authentication.
            auth_method: Method of authentication (password, oauth, api_key).
            success: Whether authentication was successful.
            ip_address: IP address of the authentication attempt.
            failure_reason: Reason for authentication failure if applicable.
        """
        audit_record = {
            "audit_type": "authentication",
            "user_id": user_id,
            "auth_method": auth_method,
            "success": success,
            "ip_address": ip_address,
        }

        if not success and failure_reason:
            audit_record["failure_reason"] = failure_reason

        log_method = self.logger.info if success else self.logger.warning
        log_method("Authentication attempt", **audit_record)

    def log_export(
        self,
        user_id: str,
        export_type: str,
        record_count: int,
        destination: str,
        success: bool = True,
    ) -> None:
        """
        Log a data export event.

        Args:
            user_id: Identifier of the user performing the export.
            export_type: Type of export (csv, pdf, api).
            record_count: Number of records exported.
            destination: Destination of the export (redacted).
            success: Whether the export was successful.
        """
        audit_record = {
            "audit_type": "data_export",
            "user_id": user_id,
            "export_type": export_type,
            "record_count": record_count,
            "destination": "[REDACTED]",
            "success": success,
        }

        self.logger.info("Data export", **audit_record)

    def log_system_event(
        self,
        event_type: str,
        component: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Log a system event.

        Args:
            event_type: Type of system event (startup, shutdown, config_change).
            component: System component generating the event.
            details: Additional context about the event.
        """
        audit_record = {
            "audit_type": "system_event",
            "event_type": event_type,
            "component": component,
            "details": details or {},
        }

        self.logger.info("System event", **audit_record)
