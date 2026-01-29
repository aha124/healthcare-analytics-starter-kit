"""HIPAA-compliant audit logging for healthcare analytics."""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from config.logging_config import get_logger

logger = get_logger(__name__)


class AuditEventType(str, Enum):
    """Types of auditable events."""

    # Data access events
    DATA_READ = "data_read"
    DATA_WRITE = "data_write"
    DATA_DELETE = "data_delete"
    DATA_EXPORT = "data_export"
    DATA_QUERY = "data_query"

    # Authentication events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    SESSION_TIMEOUT = "session_timeout"

    # Authorization events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    PERMISSION_CHANGE = "permission_change"

    # System events
    CONFIG_CHANGE = "config_change"
    PIPELINE_START = "pipeline_start"
    PIPELINE_COMPLETE = "pipeline_complete"
    PIPELINE_ERROR = "pipeline_error"

    # Security events
    ENCRYPTION_EVENT = "encryption_event"
    PHI_ACCESS = "phi_access"
    SECURITY_ALERT = "security_alert"


@dataclass
class AuditEvent:
    """Structured audit event record."""

    event_type: AuditEventType
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Who
    user_id: str | None = None
    user_name: str | None = None
    user_role: str | None = None
    ip_address: str | None = None
    session_id: str | None = None

    # What
    action: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None  # Will be hashed/redacted for PHI
    record_count: int | None = None

    # Where
    source_system: str | None = None
    component: str | None = None
    environment: str | None = None

    # Result
    success: bool = True
    error_code: str | None = None
    error_message: str | None = None

    # Additional context
    details: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["event_type"] = self.event_type.value
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """
    HIPAA-compliant audit logger for healthcare analytics.

    This logger creates audit records that support:
    - HIPAA audit trail requirements
    - Access logging for PHI
    - Security event monitoring
    - Compliance reporting

    Audit logs capture:
    - Who accessed the data (user identification)
    - What was accessed (resource type/ID - redacted)
    - When it was accessed (timestamp)
    - How it was accessed (action type)
    - Success/failure status

    Example:
        >>> audit = AuditLogger("/var/log/audit")
        >>> audit.log_data_access(
        ...     user_id="user123",
        ...     action="read",
        ...     resource_type="patient",
        ...     record_count=100,
        ... )
    """

    def __init__(
        self,
        log_path: str | Path | None = None,
        console_output: bool = True,
        rotate_daily: bool = True,
    ):
        """
        Initialize the audit logger.

        Args:
            log_path: Directory for audit log files.
            console_output: Also output to console logger.
            rotate_daily: Create new file each day.
        """
        self.log_path = Path(log_path) if log_path else None
        self.console_output = console_output
        self.rotate_daily = rotate_daily
        self._logger = get_logger("audit")
        self._current_file: Path | None = None
        self._file_handle: Any = None

        if self.log_path:
            self.log_path.mkdir(parents=True, exist_ok=True)

    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.

        Args:
            event: AuditEvent to log.
        """
        # Ensure sensitive data is redacted
        if event.resource_id:
            event.resource_id = self._hash_id(event.resource_id)

        # Write to file
        if self.log_path:
            self._write_to_file(event)

        # Write to structured logger
        if self.console_output:
            self._logger.info(
                "Audit event",
                event_type=event.event_type.value,
                user_id=event.user_id,
                action=event.action,
                resource_type=event.resource_type,
                success=event.success,
            )

    def log_data_access(
        self,
        user_id: str,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        record_count: int | None = None,
        success: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Log a data access event.

        Args:
            user_id: User performing the access.
            action: Type of access (read, write, delete).
            resource_type: Type of resource accessed.
            resource_id: ID of resource (will be hashed).
            record_count: Number of records accessed.
            success: Whether access was successful.
            **kwargs: Additional context.
        """
        event_type = {
            "read": AuditEventType.DATA_READ,
            "write": AuditEventType.DATA_WRITE,
            "delete": AuditEventType.DATA_DELETE,
            "export": AuditEventType.DATA_EXPORT,
            "query": AuditEventType.DATA_QUERY,
        }.get(action.lower(), AuditEventType.DATA_READ)

        event = AuditEvent(
            event_type=event_type,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            record_count=record_count,
            success=success,
            details=kwargs,
        )
        self.log_event(event)

    def log_authentication(
        self,
        user_id: str,
        success: bool,
        ip_address: str | None = None,
        method: str | None = None,
        error_message: str | None = None,
    ) -> None:
        """
        Log an authentication event.

        Args:
            user_id: User attempting authentication.
            success: Whether authentication succeeded.
            ip_address: Client IP address.
            method: Authentication method used.
            error_message: Error message if failed.
        """
        event = AuditEvent(
            event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILURE,
            user_id=user_id,
            ip_address=ip_address,
            success=success,
            error_message=error_message,
            details={"method": method} if method else {},
        )
        self.log_event(event)

    def log_authorization(
        self,
        user_id: str,
        resource_type: str,
        action: str,
        granted: bool,
        required_permission: str | None = None,
    ) -> None:
        """
        Log an authorization decision.

        Args:
            user_id: User requesting access.
            resource_type: Type of resource.
            action: Requested action.
            granted: Whether access was granted.
            required_permission: Permission that was checked.
        """
        event = AuditEvent(
            event_type=AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED,
            user_id=user_id,
            resource_type=resource_type,
            action=action,
            success=granted,
            details={"required_permission": required_permission},
        )
        self.log_event(event)

    def log_pipeline_event(
        self,
        pipeline_name: str,
        event_type: str,
        records_processed: int | None = None,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Log a pipeline execution event.

        Args:
            pipeline_name: Name of the pipeline.
            event_type: start, complete, or error.
            records_processed: Number of records processed.
            error_message: Error message if failed.
            **kwargs: Additional context.
        """
        audit_type = {
            "start": AuditEventType.PIPELINE_START,
            "complete": AuditEventType.PIPELINE_COMPLETE,
            "error": AuditEventType.PIPELINE_ERROR,
        }.get(event_type.lower(), AuditEventType.PIPELINE_START)

        event = AuditEvent(
            event_type=audit_type,
            component=pipeline_name,
            record_count=records_processed,
            success=event_type.lower() != "error",
            error_message=error_message,
            details=kwargs,
        )
        self.log_event(event)

    def log_phi_access(
        self,
        user_id: str,
        patient_id: str,
        access_reason: str,
        data_elements: list[str] | None = None,
    ) -> None:
        """
        Log access to PHI (Protected Health Information).

        Args:
            user_id: User accessing PHI.
            patient_id: Patient whose data was accessed (will be hashed).
            access_reason: Reason for access (treatment, operations, etc.).
            data_elements: Types of data accessed.
        """
        event = AuditEvent(
            event_type=AuditEventType.PHI_ACCESS,
            user_id=user_id,
            resource_type="patient",
            resource_id=patient_id,
            action="phi_access",
            details={
                "access_reason": access_reason,
                "data_elements": data_elements or [],
            },
        )
        self.log_event(event)

    def log_export(
        self,
        user_id: str,
        export_type: str,
        record_count: int,
        destination: str,
        includes_phi: bool = False,
    ) -> None:
        """
        Log a data export event.

        Args:
            user_id: User performing export.
            export_type: Type of export (csv, pdf, api).
            record_count: Number of records exported.
            destination: Export destination (redacted in logs).
            includes_phi: Whether export includes PHI.
        """
        event = AuditEvent(
            event_type=AuditEventType.DATA_EXPORT,
            user_id=user_id,
            action="export",
            record_count=record_count,
            details={
                "export_type": export_type,
                "destination": "[REDACTED]",
                "includes_phi": includes_phi,
            },
        )
        self.log_event(event)

    def _write_to_file(self, event: AuditEvent) -> None:
        """Write event to audit log file."""
        if not self.log_path:
            return

        # Determine filename
        if self.rotate_daily:
            filename = f"audit_{event.timestamp.strftime('%Y%m%d')}.jsonl"
        else:
            filename = "audit.jsonl"

        filepath = self.log_path / filename

        # Write as JSON lines
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    @staticmethod
    def _hash_id(resource_id: str) -> str:
        """Hash a resource ID for audit logging."""
        import hashlib

        return hashlib.sha256(f"audit_{resource_id}".encode()).hexdigest()[:16]

    def query_audit_log(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: str | None = None,
        event_type: AuditEventType | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        Query audit log records.

        Args:
            start_date: Start of date range.
            end_date: End of date range.
            user_id: Filter by user.
            event_type: Filter by event type.
            limit: Maximum records to return.

        Returns:
            List of matching audit records.
        """
        if not self.log_path:
            return []

        results = []

        # Find relevant files
        for filepath in sorted(self.log_path.glob("audit_*.jsonl"), reverse=True):
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        timestamp = datetime.fromisoformat(record["timestamp"])

                        # Apply filters
                        if start_date and timestamp < start_date:
                            continue
                        if end_date and timestamp > end_date:
                            continue
                        if user_id and record.get("user_id") != user_id:
                            continue
                        if event_type and record.get("event_type") != event_type.value:
                            continue

                        results.append(record)

                        if len(results) >= limit:
                            return results

                    except (json.JSONDecodeError, KeyError):
                        continue

        return results
