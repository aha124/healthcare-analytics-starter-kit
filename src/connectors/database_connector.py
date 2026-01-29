"""Direct database connector for EMR read replica access."""

from datetime import datetime
from typing import Any, Generator

from pydantic import Field, SecretStr
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from config.logging_config import get_logger
from src.connectors.base_connector import (
    AuthenticationError,
    BaseConnector,
    ConnectionStatus,
    ConnectorConfig,
    DataFetchError,
)

logger = get_logger(__name__)


class DatabaseConfig(ConnectorConfig):
    """Configuration for direct database connector."""

    driver: str = Field(
        default="postgresql+psycopg2",
        description="SQLAlchemy database driver",
    )
    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: SecretStr = Field(..., description="Database password")
    schema: str | None = Field(default=None, description="Database schema")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Maximum pool overflow")
    pool_timeout: int = Field(default=30, description="Pool timeout in seconds")
    ssl_mode: str | None = Field(default=None, description="SSL mode")
    ssl_cert_path: str | None = Field(default=None, description="Path to SSL certificate")

    # Query configuration
    patient_query: str | None = Field(default=None, description="Custom patient query")
    encounter_query: str | None = Field(default=None, description="Custom encounter query")
    diagnosis_query: str | None = Field(default=None, description="Custom diagnosis query")
    procedure_query: str | None = Field(default=None, description="Custom procedure query")
    lab_query: str | None = Field(default=None, description="Custom lab results query")
    vitals_query: str | None = Field(default=None, description="Custom vitals query")
    medication_query: str | None = Field(default=None, description="Custom medication query")

    # Table names (if not using custom queries)
    patient_table: str = Field(default="patients", description="Patient table name")
    encounter_table: str = Field(default="encounters", description="Encounter table name")
    diagnosis_table: str = Field(default="diagnoses", description="Diagnosis table name")
    procedure_table: str = Field(default="procedures", description="Procedure table name")
    lab_table: str = Field(default="lab_results", description="Lab results table name")
    vitals_table: str = Field(default="vitals", description="Vitals table name")
    medication_table: str = Field(default="medications", description="Medication table name")

    @property
    def connection_string(self) -> str:
        """Generate SQLAlchemy connection string."""
        base = (
            f"{self.driver}://{self.username}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.database}"
        )

        params = []
        if self.ssl_mode:
            params.append(f"sslmode={self.ssl_mode}")

        if params:
            base += "?" + "&".join(params)

        return base


class DatabaseConnector(BaseConnector):
    """
    Direct database connector for EMR read replicas.

    This connector provides direct SQL access to EMR databases,
    typically read replicas to avoid impacting production systems.

    IMPORTANT SECURITY CONSIDERATIONS:
    - Only connect to read replicas, never production databases
    - Use read-only database credentials
    - Implement network-level access controls
    - Log all queries for audit purposes

    Supported databases:
    - PostgreSQL (default)
    - Microsoft SQL Server (for Epic Clarity, Cerner)
    - Oracle (for some EMR systems)
    - MySQL/MariaDB

    Example:
        >>> config = DatabaseConfig(
        ...     name="epic_clarity",
        ...     driver="mssql+pyodbc",
        ...     host="clarity-replica.example.com",
        ...     port=1433,
        ...     database="CLARITY",
        ...     username="readonly_user",
        ...     password=SecretStr("secure_password"),
        ...     patient_query="SELECT * FROM PATIENT WHERE UPDATE_DATE > :since",
        ... )
        >>> with DatabaseConnector(config) as connector:
        ...     for patient in connector.fetch_patients():
        ...         print(patient)
    """

    def __init__(self, config: DatabaseConfig):
        """
        Initialize database connector.

        Args:
            config: Database connector configuration.
        """
        super().__init__(config)
        self.config: DatabaseConfig = config
        self._engine: Engine | None = None
        self._metadata: MetaData | None = None

    def connect(self) -> bool:
        """
        Establish database connection.

        Returns:
            True if connection successful.

        Raises:
            AuthenticationError: If connection fails.
        """
        self._logger.info(
            "Connecting to database",
            host=self.config.host,
            database=self.config.database,
            driver=self.config.driver,
        )
        self.status = ConnectionStatus.AUTHENTICATING

        try:
            # Create engine with connection pooling
            self._engine = create_engine(
                self.config.connection_string,
                poolclass=QueuePool,
                pool_size=self.config.pool_size,
                max_overflow=self.config.max_overflow,
                pool_timeout=self.config.pool_timeout,
                pool_pre_ping=True,  # Verify connections before use
            )

            # Test connection
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            # Load metadata
            self._metadata = MetaData()
            if self.config.schema:
                self._metadata = MetaData(schema=self.config.schema)

            self.status = ConnectionStatus.CONNECTED
            self._logger.info("Successfully connected to database")
            return True

        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self._record_error(str(e))
            raise AuthenticationError(str(e), self.config.name)

    def disconnect(self) -> None:
        """Close database connection and dispose of engine."""
        if self._engine:
            self._engine.dispose()
            self._engine = None
        self._metadata = None
        self.status = ConnectionStatus.DISCONNECTED
        self._logger.info("Disconnected from database")

    def test_connection(self) -> bool:
        """Test if database connection is healthy."""
        if not self._engine:
            return False

        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self._logger.warning("Connection test failed", error=str(e))
            return False

    def get_table_list(self) -> list[str]:
        """
        Get list of available tables.

        Returns:
            List of table names.
        """
        if not self._engine:
            raise ConnectionError("Not connected to database")

        inspector = inspect(self._engine)
        return inspector.get_table_names(schema=self.config.schema)

    def get_table_columns(self, table_name: str) -> list[dict[str, Any]]:
        """
        Get column information for a table.

        Args:
            table_name: Name of the table.

        Returns:
            List of column information dictionaries.
        """
        if not self._engine:
            raise ConnectionError("Not connected to database")

        inspector = inspect(self._engine)
        return inspector.get_columns(table_name, schema=self.config.schema)

    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Execute a SQL query and yield results.

        Args:
            query: SQL query string.
            params: Query parameters.

        Yields:
            Result rows as dictionaries.

        Note:
            All queries are logged for audit purposes.
        """
        if not self._engine:
            raise ConnectionError("Not connected to database")

        self._logger.info(
            "Executing query",
            query_preview=query[:100] + "..." if len(query) > 100 else query,
            params=list(params.keys()) if params else [],
        )

        try:
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                columns = result.keys()

                row_count = 0
                for row in result:
                    row_count += 1
                    yield dict(zip(columns, row))

                self._record_success(row_count, 0)

        except Exception as e:
            self._record_error(str(e))
            raise DataFetchError(
                str(e),
                self.config.name,
                "query",
                original_error=e,
            )

    def _fetch_from_table(
        self,
        table_name: str,
        custom_query: str | None = None,
        since: datetime | None = None,
        filter_column: str | None = None,
        filter_values: list[str] | None = None,
        timestamp_column: str = "updated_at",
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch records from a table with optional filtering.

        Args:
            table_name: Name of the table.
            custom_query: Optional custom SQL query.
            since: Only fetch records modified since this datetime.
            filter_column: Column to filter on.
            filter_values: Values to filter for.
            timestamp_column: Column containing update timestamp.

        Yields:
            Record dictionaries.
        """
        if custom_query:
            # Use custom query with parameters
            params: dict[str, Any] = {}
            if since:
                params["since"] = since
            if filter_values:
                params["filter_values"] = tuple(filter_values)

            yield from self.execute_query(custom_query, params)
        else:
            # Build dynamic query
            if not self._engine or not self._metadata:
                raise ConnectionError("Not connected to database")

            try:
                table = Table(
                    table_name,
                    self._metadata,
                    autoload_with=self._engine,
                )
            except Exception as e:
                self._logger.warning(
                    "Table not found",
                    table=table_name,
                    error=str(e),
                )
                return

            query = select(table)

            # Add filters
            if since and timestamp_column in table.c:
                query = query.where(table.c[timestamp_column] >= since)

            if filter_values and filter_column and filter_column in table.c:
                query = query.where(table.c[filter_column].in_(filter_values))

            with self._engine.connect() as conn:
                result = conn.execute(query)
                columns = result.keys()

                row_count = 0
                for row in result:
                    row_count += 1
                    yield dict(zip(columns, row))

                self._record_success(row_count, 0)

    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch patient records from database."""
        yield from self._fetch_from_table(
            self.config.patient_table,
            self.config.patient_query,
            since=since,
            filter_column="patient_id",
            filter_values=patient_ids,
        )

    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch encounter records from database."""
        yield from self._fetch_from_table(
            self.config.encounter_table,
            self.config.encounter_query,
            since=since,
            filter_column="patient_id",
            filter_values=patient_ids,
        )

    def fetch_diagnoses(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch diagnosis records from database."""
        yield from self._fetch_from_table(
            self.config.diagnosis_table,
            self.config.diagnosis_query,
            since=since,
            filter_column="encounter_id",
            filter_values=encounter_ids,
        )

    def fetch_procedures(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch procedure records from database."""
        yield from self._fetch_from_table(
            self.config.procedure_table,
            self.config.procedure_query,
            since=since,
            filter_column="encounter_id",
            filter_values=encounter_ids,
        )

    def fetch_lab_results(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch lab result records from database."""
        yield from self._fetch_from_table(
            self.config.lab_table,
            self.config.lab_query,
            since=since,
            filter_column="patient_id",
            filter_values=patient_ids,
        )

    def fetch_vitals(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch vital sign records from database."""
        yield from self._fetch_from_table(
            self.config.vitals_table,
            self.config.vitals_query,
            since=since,
            filter_column="patient_id",
            filter_values=patient_ids,
        )

    def fetch_medications(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch medication records from database."""
        yield from self._fetch_from_table(
            self.config.medication_table,
            self.config.medication_query,
            since=since,
            filter_column="patient_id",
            filter_values=patient_ids,
        )


# Common query templates for popular EMR systems


class EpicClarityQueries:
    """Common query templates for Epic Clarity database."""

    PATIENTS = """
    SELECT
        PAT_ID as source_id,
        PAT_MRN_ID as mrn,
        PAT_FIRST_NAME as first_name,
        PAT_LAST_NAME as last_name,
        BIRTH_DATE as date_of_birth,
        SEX_C as gender,
        ADD_LINE_1 as address_line1,
        CITY as city,
        STATE_C as state,
        ZIP as postal_code,
        HOME_PHONE as phone,
        EMAIL_ADDRESS as email,
        UPDATE_DATE as updated_at
    FROM PATIENT
    WHERE UPDATE_DATE > :since
    """

    ENCOUNTERS = """
    SELECT
        PAT_ENC_CSN_ID as source_id,
        PAT_ID as patient_id,
        ENC_TYPE_C as encounter_type,
        HOSP_ADMSN_TIME as admission_date,
        HOSP_DISCH_TIME as discharge_date,
        DEPARTMENT_ID as location,
        VISIT_PROV_ID as attending_provider,
        UPDATE_DATE as updated_at
    FROM PAT_ENC
    WHERE UPDATE_DATE > :since
    """


class CernerMillenniumQueries:
    """Common query templates for Cerner Millennium database."""

    PATIENTS = """
    SELECT
        person_id as source_id,
        alias as mrn,
        name_first as first_name,
        name_last as last_name,
        birth_dt_tm as date_of_birth,
        sex_cd as gender,
        street_addr as address_line1,
        city as city,
        state as state,
        zipcode as postal_code,
        phone_num as phone,
        updt_dt_tm as updated_at
    FROM PERSON p
    JOIN PERSON_ALIAS pa ON p.person_id = pa.person_id
    JOIN ADDRESS a ON p.person_id = a.parent_entity_id
    WHERE p.updt_dt_tm > :since
    AND pa.alias_pool_cd = (SELECT code_value FROM CODE_VALUE WHERE CDF_MEANING = 'MRN')
    """
