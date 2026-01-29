"""CSV/Flat file connector for EMR data ingestion."""

import csv
import glob
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

import pandas as pd
from pydantic import Field

from config.logging_config import get_logger
from src.connectors.base_connector import (
    BaseConnector,
    ConnectionStatus,
    ConnectorConfig,
    DataFetchError,
)

logger = get_logger(__name__)


class CSVConfig(ConnectorConfig):
    """Configuration for CSV file connector."""

    import_path: Path = Field(..., description="Directory for incoming CSV files")
    archive_path: Path | None = Field(default=None, description="Directory for processed files")
    error_path: Path | None = Field(default=None, description="Directory for failed files")
    delimiter: str = Field(default=",", description="CSV delimiter")
    encoding: str = Field(default="utf-8", description="File encoding")
    has_header: bool = Field(default=True, description="Whether files have header row")
    skip_rows: int = Field(default=0, description="Number of rows to skip")
    date_format: str = Field(default="%Y-%m-%d", description="Date format string")
    datetime_format: str = Field(default="%Y-%m-%d %H:%M:%S", description="Datetime format")
    archive_processed: bool = Field(default=True, description="Archive processed files")
    file_patterns: dict[str, str] = Field(
        default={
            "patients": "patient*.csv",
            "encounters": "encounter*.csv",
            "diagnoses": "diagnos*.csv",
            "procedures": "procedure*.csv",
            "lab_results": "lab*.csv",
            "vitals": "vital*.csv",
            "medications": "medication*.csv",
        },
        description="File patterns for each data type",
    )
    column_mappings: dict[str, dict[str, str]] = Field(
        default={},
        description="Column name mappings for each data type",
    )


class CSVConnector(BaseConnector):
    """
    CSV/Flat file connector for EMR data ingestion.

    This connector is designed for:
    - MEDITECH CSV exports
    - Generic flat file exports from any EMR
    - Manual data imports
    - SFTP-delivered files

    Features:
    - Configurable column mappings
    - Automatic file archiving after processing
    - Error file quarantine
    - Support for various delimiters and encodings

    Example:
        >>> config = CSVConfig(
        ...     name="meditech_csv",
        ...     import_path=Path("/data/imports"),
        ...     archive_path=Path("/data/archives"),
        ...     column_mappings={
        ...         "patients": {
        ...             "PATIENT_MRN": "mrn",
        ...             "FIRST_NM": "first_name",
        ...             "LAST_NM": "last_name",
        ...         }
        ...     }
        ... )
        >>> with CSVConnector(config) as connector:
        ...     for patient in connector.fetch_patients():
        ...         print(patient)
    """

    # Default column mappings for common EMR exports
    DEFAULT_PATIENT_COLUMNS = {
        "patient_id": "source_id",
        "mrn": "mrn",
        "medical_record_number": "mrn",
        "first_name": "first_name",
        "last_name": "last_name",
        "date_of_birth": "date_of_birth",
        "dob": "date_of_birth",
        "birth_date": "date_of_birth",
        "gender": "gender",
        "sex": "gender",
        "address": "address_line1",
        "address_line_1": "address_line1",
        "city": "city",
        "state": "state",
        "zip": "postal_code",
        "zip_code": "postal_code",
        "postal_code": "postal_code",
        "phone": "phone",
        "phone_number": "phone",
        "email": "email",
        "email_address": "email",
        "ssn": "ssn",
        "social_security": "ssn",
    }

    DEFAULT_ENCOUNTER_COLUMNS = {
        "encounter_id": "source_id",
        "visit_id": "source_id",
        "patient_id": "patient_id",
        "patient_mrn": "patient_id",
        "encounter_type": "encounter_type",
        "visit_type": "encounter_type",
        "class": "encounter_type",
        "admission_date": "admission_date",
        "admit_date": "admission_date",
        "arrival_date": "admission_date",
        "discharge_date": "discharge_date",
        "departure_date": "discharge_date",
        "location": "location",
        "department": "location",
        "unit": "location",
        "provider": "attending_provider",
        "attending_physician": "attending_provider",
        "status": "status",
    }

    DEFAULT_DIAGNOSIS_COLUMNS = {
        "diagnosis_id": "source_id",
        "patient_id": "patient_id",
        "encounter_id": "encounter_id",
        "visit_id": "encounter_id",
        "code": "code",
        "icd_code": "code",
        "diagnosis_code": "code",
        "icd10_code": "code",
        "description": "description",
        "diagnosis_description": "description",
        "type": "diagnosis_type",
        "diagnosis_type": "diagnosis_type",
        "onset_date": "onset_date",
        "diagnosis_date": "onset_date",
    }

    DEFAULT_LAB_COLUMNS = {
        "result_id": "source_id",
        "lab_id": "source_id",
        "patient_id": "patient_id",
        "encounter_id": "encounter_id",
        "test_code": "code",
        "loinc_code": "code",
        "order_code": "code",
        "test_name": "description",
        "result_name": "description",
        "result_value": "value",
        "value": "value",
        "numeric_value": "value",
        "result_unit": "value_unit",
        "unit": "value_unit",
        "units": "value_unit",
        "reference_low": "reference_range_low",
        "ref_range_low": "reference_range_low",
        "reference_high": "reference_range_high",
        "ref_range_high": "reference_range_high",
        "abnormal_flag": "interpretation",
        "flag": "interpretation",
        "result_date": "effective_date",
        "collection_date": "effective_date",
        "test_date": "effective_date",
    }

    def __init__(self, config: CSVConfig):
        """
        Initialize CSV connector.

        Args:
            config: CSV connector configuration.
        """
        super().__init__(config)
        self.config: CSVConfig = config
        self._processed_files: list[str] = []

    def connect(self) -> bool:
        """
        Validate import path and create necessary directories.

        Returns:
            True if paths are valid and accessible.
        """
        self._logger.info("Initializing CSV connector", import_path=str(self.config.import_path))

        try:
            # Validate import path
            if not self.config.import_path.exists():
                raise FileNotFoundError(f"Import path does not exist: {self.config.import_path}")

            # Create archive and error paths if specified
            if self.config.archive_path:
                self.config.archive_path.mkdir(parents=True, exist_ok=True)
            if self.config.error_path:
                self.config.error_path.mkdir(parents=True, exist_ok=True)

            self.status = ConnectionStatus.CONNECTED
            self._logger.info("CSV connector initialized successfully")
            return True

        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self._record_error(str(e))
            return False

    def disconnect(self) -> None:
        """Cleanup and archive processed files."""
        self._logger.info("CSV connector disconnecting", processed_files=len(self._processed_files))

        if self.config.archive_processed and self.config.archive_path:
            for filepath in self._processed_files:
                try:
                    self._archive_file(filepath)
                except Exception as e:
                    self._logger.warning("Failed to archive file", filepath=filepath, error=str(e))

        self._processed_files = []
        self.status = ConnectionStatus.DISCONNECTED

    def test_connection(self) -> bool:
        """Test if import path is accessible."""
        return self.config.import_path.exists() and self.config.import_path.is_dir()

    def _archive_file(self, filepath: str) -> None:
        """Move processed file to archive directory."""
        if not self.config.archive_path:
            return

        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{timestamp}_{filename}"
        archive_path = self.config.archive_path / archive_name

        shutil.move(filepath, archive_path)
        self._logger.debug("Archived file", source=filepath, destination=str(archive_path))

    def _quarantine_file(self, filepath: str, error: str) -> None:
        """Move failed file to error directory."""
        if not self.config.error_path:
            return

        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        error_name = f"{timestamp}_{filename}"
        error_path = self.config.error_path / error_name

        shutil.move(filepath, error_path)

        # Write error info
        error_info_path = self.config.error_path / f"{error_name}.error"
        with open(error_info_path, "w") as f:
            f.write(f"Original file: {filepath}\n")
            f.write(f"Error time: {datetime.now().isoformat()}\n")
            f.write(f"Error: {error}\n")

        self._logger.warning("Quarantined file", source=filepath, error=error)

    def _get_column_mapping(self, data_type: str) -> dict[str, str]:
        """Get column mapping for a data type."""
        # Check custom mappings first
        if data_type in self.config.column_mappings:
            return self.config.column_mappings[data_type]

        # Fall back to defaults
        defaults = {
            "patients": self.DEFAULT_PATIENT_COLUMNS,
            "encounters": self.DEFAULT_ENCOUNTER_COLUMNS,
            "diagnoses": self.DEFAULT_DIAGNOSIS_COLUMNS,
            "lab_results": self.DEFAULT_LAB_COLUMNS,
            "vitals": self.DEFAULT_LAB_COLUMNS,  # Same structure
        }
        return defaults.get(data_type, {})

    def _normalize_columns(self, df: pd.DataFrame, data_type: str) -> pd.DataFrame:
        """
        Normalize column names using mapping.

        Args:
            df: Input DataFrame.
            data_type: Type of data for mapping lookup.

        Returns:
            DataFrame with normalized column names.
        """
        mapping = self._get_column_mapping(data_type)

        # Normalize source column names (lowercase, strip, replace spaces)
        df.columns = df.columns.str.lower().str.strip().str.replace(" ", "_")

        # Apply mapping
        rename_map = {}
        for col in df.columns:
            if col in mapping:
                rename_map[col] = mapping[col]

        if rename_map:
            df = df.rename(columns=rename_map)

        return df

    def _parse_dates(self, df: pd.DataFrame, date_columns: list[str]) -> pd.DataFrame:
        """Parse date columns to datetime."""
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(
                    df[col],
                    format=self.config.date_format,
                    errors="coerce",
                )
        return df

    def _read_csv_files(
        self,
        pattern: str,
        data_type: str,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Read CSV files matching pattern and yield normalized records.

        Args:
            pattern: File glob pattern.
            data_type: Type of data for column mapping.

        Yields:
            Normalized record dictionaries.
        """
        file_pattern = str(self.config.import_path / pattern)
        files = glob.glob(file_pattern)

        if not files:
            self._logger.info("No files found", pattern=file_pattern)
            return

        for filepath in sorted(files):
            self._logger.info("Processing file", filepath=filepath)

            try:
                # Read CSV
                df = pd.read_csv(
                    filepath,
                    delimiter=self.config.delimiter,
                    encoding=self.config.encoding,
                    header=0 if self.config.has_header else None,
                    skiprows=self.config.skip_rows,
                    low_memory=False,
                )

                # Normalize columns
                df = self._normalize_columns(df, data_type)

                # Add source file info
                df["_source_file"] = os.path.basename(filepath)
                df["_import_timestamp"] = datetime.now()

                # Convert to records
                records = df.to_dict("records")

                for record in records:
                    # Clean up NaN values
                    cleaned = {
                        k: (None if pd.isna(v) else v) for k, v in record.items()
                    }
                    yield cleaned

                self._processed_files.append(filepath)
                self._record_success(len(records), 0)

            except Exception as e:
                self._record_error(f"Failed to process {filepath}: {e}")
                self._quarantine_file(filepath, str(e))

    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch patient data from CSV files."""
        pattern = self.config.file_patterns.get("patients", "patient*.csv")

        for record in self._read_csv_files(pattern, "patients"):
            # Apply filters
            if patient_ids and record.get("mrn") not in patient_ids:
                continue
            yield record

    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch encounter data from CSV files."""
        pattern = self.config.file_patterns.get("encounters", "encounter*.csv")

        for record in self._read_csv_files(pattern, "encounters"):
            if patient_ids and record.get("patient_id") not in patient_ids:
                continue
            yield record

    def fetch_diagnoses(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch diagnosis data from CSV files."""
        pattern = self.config.file_patterns.get("diagnoses", "diagnos*.csv")

        for record in self._read_csv_files(pattern, "diagnoses"):
            if encounter_ids and record.get("encounter_id") not in encounter_ids:
                continue
            yield record

    def fetch_procedures(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch procedure data from CSV files."""
        pattern = self.config.file_patterns.get("procedures", "procedure*.csv")

        for record in self._read_csv_files(pattern, "procedures"):
            if encounter_ids and record.get("encounter_id") not in encounter_ids:
                continue
            yield record

    def fetch_lab_results(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch lab result data from CSV files."""
        pattern = self.config.file_patterns.get("lab_results", "lab*.csv")

        for record in self._read_csv_files(pattern, "lab_results"):
            if patient_ids and record.get("patient_id") not in patient_ids:
                continue
            yield record

    def fetch_vitals(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch vital signs data from CSV files."""
        pattern = self.config.file_patterns.get("vitals", "vital*.csv")

        for record in self._read_csv_files(pattern, "vitals"):
            if patient_ids and record.get("patient_id") not in patient_ids:
                continue
            yield record

    def fetch_medications(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch medication data from CSV files."""
        pattern = self.config.file_patterns.get("medications", "medication*.csv")

        for record in self._read_csv_files(pattern, "medications"):
            if patient_ids and record.get("patient_id") not in patient_ids:
                continue
            yield record

    def preview_file(
        self,
        filepath: str,
        num_rows: int = 5,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """
        Preview a CSV file without processing it.

        Args:
            filepath: Path to the CSV file.
            num_rows: Number of rows to preview.

        Returns:
            Tuple of (column names, sample records).
        """
        df = pd.read_csv(
            filepath,
            delimiter=self.config.delimiter,
            encoding=self.config.encoding,
            header=0 if self.config.has_header else None,
            skiprows=self.config.skip_rows,
            nrows=num_rows,
        )

        return list(df.columns), df.to_dict("records")
