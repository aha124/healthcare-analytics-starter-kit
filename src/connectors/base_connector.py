"""Abstract base class for EMR and data source connectors."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Generator

from pydantic import BaseModel, Field

from config.logging_config import get_logger

logger = get_logger(__name__)


class ConnectionStatus(str, Enum):
    """Connection status enumeration."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    AUTHENTICATING = "authenticating"
    RATE_LIMITED = "rate_limited"


class ConnectorConfig(BaseModel):
    """Base configuration for all connectors."""

    name: str = Field(..., description="Unique name for this connector instance")
    enabled: bool = Field(default=True, description="Whether connector is enabled")
    retry_attempts: int = Field(default=3, ge=0, description="Number of retry attempts")
    retry_delay: float = Field(default=1.0, ge=0, description="Delay between retries in seconds")
    timeout: float = Field(default=30.0, ge=0, description="Connection timeout in seconds")
    batch_size: int = Field(default=100, ge=1, description="Batch size for data retrieval")


@dataclass
class ConnectorMetrics:
    """Metrics tracking for connector operations."""

    records_fetched: int = 0
    records_failed: int = 0
    api_calls: int = 0
    errors: list[str] = field(default_factory=list)
    last_fetch_time: datetime | None = None
    last_error_time: datetime | None = None
    average_response_time_ms: float = 0.0


class BaseConnector(ABC):
    """
    Abstract base class for all EMR and data source connectors.

    This class defines the interface that all connectors must implement,
    ensuring consistent behavior across different data sources.

    Attributes:
        config: Connector configuration.
        status: Current connection status.
        metrics: Performance and error metrics.

    Example:
        >>> class MyConnector(BaseConnector):
        ...     def connect(self) -> bool:
        ...         # Implementation
        ...         pass
        ...     # ... other methods
    """

    def __init__(self, config: ConnectorConfig):
        """
        Initialize the connector.

        Args:
            config: Connector configuration.
        """
        self.config = config
        self.status = ConnectionStatus.DISCONNECTED
        self.metrics = ConnectorMetrics()
        self._logger = get_logger(f"{__name__}.{config.name}")

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise.

        Raises:
            ConnectionError: If connection fails after all retry attempts.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Close the connection to the data source.

        Should be idempotent - safe to call multiple times.
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the connection is alive and working.

        Returns:
            True if connection is healthy, False otherwise.
        """
        pass

    @abstractmethod
    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch patient demographics data.

        Args:
            since: Only fetch records modified since this datetime.
            patient_ids: Optional list of specific patient IDs to fetch.

        Yields:
            Dictionary containing patient demographic data.

        Raises:
            ConnectionError: If not connected.
            DataFetchError: If data retrieval fails.
        """
        pass

    @abstractmethod
    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch encounter/visit data.

        Args:
            since: Only fetch records modified since this datetime.
            patient_ids: Optional list of patient IDs to filter by.

        Yields:
            Dictionary containing encounter data.
        """
        pass

    @abstractmethod
    def fetch_diagnoses(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch diagnosis data.

        Args:
            since: Only fetch records modified since this datetime.
            encounter_ids: Optional list of encounter IDs to filter by.

        Yields:
            Dictionary containing diagnosis data.
        """
        pass

    @abstractmethod
    def fetch_procedures(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch procedure data.

        Args:
            since: Only fetch records modified since this datetime.
            encounter_ids: Optional list of encounter IDs to filter by.

        Yields:
            Dictionary containing procedure data.
        """
        pass

    @abstractmethod
    def fetch_lab_results(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch laboratory results.

        Args:
            since: Only fetch records modified since this datetime.
            patient_ids: Optional list of patient IDs to filter by.

        Yields:
            Dictionary containing lab result data.
        """
        pass

    @abstractmethod
    def fetch_vitals(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch vital signs data.

        Args:
            since: Only fetch records modified since this datetime.
            patient_ids: Optional list of patient IDs to filter by.

        Yields:
            Dictionary containing vital signs data.
        """
        pass

    @abstractmethod
    def fetch_medications(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch medication data.

        Args:
            since: Only fetch records modified since this datetime.
            patient_ids: Optional list of patient IDs to filter by.

        Yields:
            Dictionary containing medication data.
        """
        pass

    def get_metrics(self) -> ConnectorMetrics:
        """
        Get current connector metrics.

        Returns:
            ConnectorMetrics object with current statistics.
        """
        return self.metrics

    def reset_metrics(self) -> None:
        """Reset all connector metrics to initial values."""
        self.metrics = ConnectorMetrics()

    def _record_success(self, records: int, response_time_ms: float) -> None:
        """
        Record a successful operation.

        Args:
            records: Number of records fetched.
            response_time_ms: Response time in milliseconds.
        """
        self.metrics.records_fetched += records
        self.metrics.api_calls += 1
        self.metrics.last_fetch_time = datetime.now()

        # Update rolling average response time
        total_calls = self.metrics.api_calls
        prev_avg = self.metrics.average_response_time_ms
        self.metrics.average_response_time_ms = (
            (prev_avg * (total_calls - 1) + response_time_ms) / total_calls
        )

    def _record_error(self, error_message: str) -> None:
        """
        Record an error.

        Args:
            error_message: Description of the error.
        """
        self.metrics.records_failed += 1
        self.metrics.errors.append(error_message)
        self.metrics.last_error_time = datetime.now()

        # Keep only last 100 errors
        if len(self.metrics.errors) > 100:
            self.metrics.errors = self.metrics.errors[-100:]

        self._logger.error("Connector error", error=error_message)

    def __enter__(self) -> "BaseConnector":
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.disconnect()


class DataFetchError(Exception):
    """Exception raised when data fetching fails."""

    def __init__(
        self,
        message: str,
        connector_name: str,
        resource_type: str,
        original_error: Exception | None = None,
    ):
        """
        Initialize DataFetchError.

        Args:
            message: Error description.
            connector_name: Name of the connector that failed.
            resource_type: Type of resource being fetched.
            original_error: Original exception if available.
        """
        self.connector_name = connector_name
        self.resource_type = resource_type
        self.original_error = original_error
        super().__init__(f"[{connector_name}] Failed to fetch {resource_type}: {message}")


class AuthenticationError(Exception):
    """Exception raised when authentication fails."""

    def __init__(self, message: str, connector_name: str):
        """
        Initialize AuthenticationError.

        Args:
            message: Error description.
            connector_name: Name of the connector that failed.
        """
        self.connector_name = connector_name
        super().__init__(f"[{connector_name}] Authentication failed: {message}")
