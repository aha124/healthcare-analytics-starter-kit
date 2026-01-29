"""HL7 v2.x message parser and connector."""

import re
import socket
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator

from pydantic import Field

from config.logging_config import get_logger
from src.connectors.base_connector import (
    BaseConnector,
    ConnectionStatus,
    ConnectorConfig,
    DataFetchError,
)

logger = get_logger(__name__)

# HL7 MLLP framing characters
MLLP_START = b"\x0b"  # VT (vertical tab)
MLLP_END = b"\x1c\x0d"  # FS + CR


class HL7Config(ConnectorConfig):
    """Configuration for HL7 v2.x connector."""

    host: str = Field(default="0.0.0.0", description="HL7 listener host")
    port: int = Field(default=2575, description="HL7 listener port")
    mllp_timeout: int = Field(default=30, description="MLLP timeout in seconds")
    segment_separator: str = Field(default="\r", description="Segment separator")
    field_separator: str = Field(default="|", description="Field separator")
    component_separator: str = Field(default="^", description="Component separator")
    subcomponent_separator: str = Field(default="&", description="Subcomponent separator")
    repetition_separator: str = Field(default="~", description="Repetition separator")
    escape_character: str = Field(default="\\", description="Escape character")
    file_path: str | None = Field(default=None, description="Path to HL7 message files")


@dataclass
class HL7Segment:
    """Represents an HL7 segment."""

    segment_id: str
    fields: list[list[list[str]]]

    def get_field(
        self,
        index: int,
        component: int = 0,
        subcomponent: int = 0,
        repetition: int = 0,
    ) -> str | None:
        """
        Get a field value from the segment.

        Args:
            index: Field index (1-based, as in HL7 spec).
            component: Component index (0-based).
            subcomponent: Subcomponent index (0-based).
            repetition: Repetition index (0-based).

        Returns:
            Field value or None if not found.
        """
        try:
            # Adjust for 1-based indexing in HL7
            field_idx = index - 1 if index > 0 else 0
            if field_idx >= len(self.fields):
                return None

            field_value = self.fields[field_idx]
            if repetition >= len(field_value):
                return None

            rep_value = field_value[repetition]
            if component >= len(rep_value):
                return None

            return rep_value[component] or None

        except (IndexError, TypeError):
            return None


@dataclass
class HL7Message:
    """
    Represents a parsed HL7 v2.x message.

    Attributes:
        raw: Original message string.
        segments: List of parsed segments.
        message_type: Message type (e.g., 'ADT^A01').
        message_control_id: Unique message identifier.
        sending_application: Sending application name.
        receiving_application: Receiving application name.
        timestamp: Message timestamp.
    """

    raw: str
    segments: list[HL7Segment] = field(default_factory=list)
    message_type: str = ""
    message_control_id: str = ""
    sending_application: str = ""
    receiving_application: str = ""
    timestamp: datetime | None = None

    def get_segment(self, segment_id: str, index: int = 0) -> HL7Segment | None:
        """
        Get a segment by ID.

        Args:
            segment_id: Segment identifier (e.g., 'PID', 'OBX').
            index: Index if multiple segments with same ID (0-based).

        Returns:
            HL7Segment or None if not found.
        """
        matches = [s for s in self.segments if s.segment_id == segment_id]
        if index < len(matches):
            return matches[index]
        return None

    def get_all_segments(self, segment_id: str) -> list[HL7Segment]:
        """Get all segments with the given ID."""
        return [s for s in self.segments if s.segment_id == segment_id]


class HL7Parser:
    """
    Parser for HL7 v2.x messages.

    Supports common message types including:
    - ADT (Admit/Discharge/Transfer)
    - ORM (Orders)
    - ORU (Results)
    - MDM (Medical Documents)
    """

    def __init__(self, config: HL7Config):
        """
        Initialize the HL7 parser.

        Args:
            config: HL7 configuration.
        """
        self.config = config

    def parse(self, message: str) -> HL7Message:
        """
        Parse an HL7 message string.

        Args:
            message: Raw HL7 message string.

        Returns:
            Parsed HL7Message object.
        """
        # Clean up message
        message = message.strip()

        # Detect encoding characters from MSH segment
        if not message.startswith("MSH"):
            raise ValueError("Invalid HL7 message: must start with MSH segment")

        # Extract encoding characters from MSH-1 and MSH-2
        field_sep = message[3]
        encoding_chars = message[4:8]

        if len(encoding_chars) >= 4:
            component_sep = encoding_chars[0]
            repetition_sep = encoding_chars[1]
            escape_char = encoding_chars[2]
            subcomponent_sep = encoding_chars[3]
        else:
            # Use defaults
            component_sep = self.config.component_separator
            repetition_sep = self.config.repetition_separator
            escape_char = self.config.escape_character
            subcomponent_sep = self.config.subcomponent_separator

        # Split message into segments
        segment_strings = re.split(r"[\r\n]+", message)
        segments: list[HL7Segment] = []

        for seg_str in segment_strings:
            if not seg_str.strip():
                continue

            segment = self._parse_segment(
                seg_str,
                field_sep,
                component_sep,
                repetition_sep,
                subcomponent_sep,
            )
            segments.append(segment)

        # Build message object
        hl7_message = HL7Message(raw=message, segments=segments)

        # Extract header information
        msh = hl7_message.get_segment("MSH")
        if msh:
            hl7_message.sending_application = msh.get_field(3) or ""
            hl7_message.receiving_application = msh.get_field(5) or ""
            hl7_message.message_type = f"{msh.get_field(9, 0) or ''}"
            trigger = msh.get_field(9, 1)
            if trigger:
                hl7_message.message_type = f"{hl7_message.message_type}^{trigger}"
            hl7_message.message_control_id = msh.get_field(10) or ""

            # Parse timestamp
            ts_str = msh.get_field(7)
            if ts_str:
                hl7_message.timestamp = self._parse_timestamp(ts_str)

        return hl7_message

    def _parse_segment(
        self,
        segment_str: str,
        field_sep: str,
        component_sep: str,
        repetition_sep: str,
        subcomponent_sep: str,
    ) -> HL7Segment:
        """Parse a single segment string."""
        parts = segment_str.split(field_sep)
        segment_id = parts[0]

        # For MSH segment, field separator is MSH-1
        if segment_id == "MSH":
            # Insert field separator as MSH-1
            parts = [segment_id, field_sep] + parts[1:]

        fields: list[list[list[str]]] = []
        for part in parts[1:]:  # Skip segment ID
            repetitions: list[list[str]] = []
            for rep in part.split(repetition_sep):
                components = rep.split(component_sep)
                # We're not parsing subcomponents for simplicity
                repetitions.append(components)
            fields.append(repetitions)

        return HL7Segment(segment_id=segment_id, fields=fields)

    @staticmethod
    def _parse_timestamp(ts_str: str) -> datetime | None:
        """Parse HL7 timestamp format."""
        formats = [
            "%Y%m%d%H%M%S.%f",
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
        ]

        # Remove timezone if present
        ts_str = re.sub(r"[+-]\d{4}$", "", ts_str)

        for fmt in formats:
            try:
                return datetime.strptime(ts_str[: len(fmt.replace("%", ""))], fmt)
            except ValueError:
                continue
        return None


class HL7Connector(BaseConnector):
    """
    HL7 v2.x connector for processing HL7 message feeds.

    This connector can:
    - Listen for HL7 messages over MLLP (TCP)
    - Process HL7 message files from a directory
    - Parse ADT, ORM, ORU, and other common message types

    Example:
        >>> config = HL7Config(
        ...     name="hl7_feed",
        ...     file_path="/data/hl7_messages",
        ... )
        >>> connector = HL7Connector(config)
        >>> for message in connector.process_file("adt_message.hl7"):
        ...     print(message.message_type)
    """

    def __init__(self, config: HL7Config):
        """
        Initialize HL7 connector.

        Args:
            config: HL7 connector configuration.
        """
        super().__init__(config)
        self.config: HL7Config = config
        self.parser = HL7Parser(config)
        self._socket: socket.socket | None = None
        self._messages: list[HL7Message] = []

    def connect(self) -> bool:
        """
        Initialize the HL7 connector.

        For file-based processing, this validates the file path.
        For socket-based, this sets up the listener.

        Returns:
            True if initialization successful.
        """
        self._logger.info("Initializing HL7 connector", mode="file" if self.config.file_path else "socket")

        try:
            if self.config.file_path:
                # File-based mode - just validate path
                import os

                if not os.path.exists(self.config.file_path):
                    raise FileNotFoundError(f"HL7 file path not found: {self.config.file_path}")
            else:
                # Socket-based mode
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._socket.settimeout(self.config.mllp_timeout)
                self._socket.bind((self.config.host, self.config.port))
                self._socket.listen(5)
                self._logger.info("HL7 listener started", host=self.config.host, port=self.config.port)

            self.status = ConnectionStatus.CONNECTED
            return True

        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self._record_error(str(e))
            return False

    def disconnect(self) -> None:
        """Close the HL7 connector."""
        if self._socket:
            self._socket.close()
            self._socket = None
        self.status = ConnectionStatus.DISCONNECTED
        self._logger.info("HL7 connector disconnected")

    def test_connection(self) -> bool:
        """Test if the connector is operational."""
        return self.status == ConnectionStatus.CONNECTED

    def process_file(self, filepath: str) -> Generator[HL7Message, None, None]:
        """
        Process an HL7 message file.

        Args:
            filepath: Path to the HL7 file.

        Yields:
            Parsed HL7Message objects.
        """
        self._logger.info("Processing HL7 file", filepath=filepath)

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        # Split on MSH segments to handle multiple messages in one file
        messages = re.split(r"(?=MSH\|)", content)

        for msg_str in messages:
            if not msg_str.strip():
                continue

            try:
                message = self.parser.parse(msg_str)
                self._messages.append(message)
                yield message
            except Exception as e:
                self._record_error(f"Failed to parse message: {e}")

    def process_directory(self, pattern: str = "*.hl7") -> Generator[HL7Message, None, None]:
        """
        Process all HL7 files in the configured directory.

        Args:
            pattern: Glob pattern for file matching.

        Yields:
            Parsed HL7Message objects.
        """
        import glob
        import os

        if not self.config.file_path:
            raise ValueError("File path not configured")

        file_pattern = os.path.join(self.config.file_path, pattern)
        files = glob.glob(file_pattern)

        self._logger.info("Processing HL7 files", pattern=file_pattern, count=len(files))

        for filepath in sorted(files):
            yield from self.process_file(filepath)

    def receive_message(self, timeout: float | None = None) -> HL7Message | None:
        """
        Receive an HL7 message over MLLP.

        Args:
            timeout: Socket timeout in seconds.

        Returns:
            Parsed HL7Message or None if timeout.
        """
        if not self._socket:
            raise ConnectionError("Socket not initialized")

        if timeout:
            self._socket.settimeout(timeout)

        try:
            conn, addr = self._socket.accept()
            self._logger.debug("Connection from", address=addr)

            with conn:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk

                    # Check for MLLP end
                    if MLLP_END in data:
                        break

                # Strip MLLP framing
                if data.startswith(MLLP_START):
                    data = data[1:]
                if data.endswith(MLLP_END):
                    data = data[:-2]

                message_str = data.decode("utf-8", errors="replace")
                message = self.parser.parse(message_str)

                # Send ACK
                ack = self._create_ack(message)
                conn.sendall(MLLP_START + ack.encode() + MLLP_END)

                self._messages.append(message)
                return message

        except socket.timeout:
            return None
        except Exception as e:
            self._record_error(str(e))
            return None

    def _create_ack(self, message: HL7Message) -> str:
        """Create an ACK message for the received message."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return (
            f"MSH|^~\\&|HASK|HASK|{message.sending_application}|"
            f"{message.sending_application}|{timestamp}||ACK^{message.message_type}|"
            f"{message.message_control_id}|P|2.5\r"
            f"MSA|AA|{message.message_control_id}\r"
        )

    def extract_patient_from_message(self, message: HL7Message) -> dict[str, Any] | None:
        """
        Extract patient data from an HL7 message.

        Args:
            message: Parsed HL7 message.

        Returns:
            Patient data dictionary or None if not found.
        """
        pid = message.get_segment("PID")
        if not pid:
            return None

        return {
            "source_id": pid.get_field(3, 0),  # Patient ID
            "mrn": pid.get_field(3, 0),
            "first_name": pid.get_field(5, 1),  # Given name
            "last_name": pid.get_field(5, 0),  # Family name
            "date_of_birth": self.parser._parse_timestamp(pid.get_field(7) or ""),
            "gender": self._map_gender(pid.get_field(8)),
            "address_line1": pid.get_field(11, 0),  # Street
            "city": pid.get_field(11, 2),
            "state": pid.get_field(11, 3),
            "postal_code": pid.get_field(11, 4),
            "phone": pid.get_field(13, 0),
            "ssn": pid.get_field(19),
            "race": pid.get_field(10, 0),
            "ethnicity": pid.get_field(22, 0),
            "_raw": message.raw,
        }

    def extract_encounter_from_message(self, message: HL7Message) -> dict[str, Any] | None:
        """
        Extract encounter data from an HL7 message.

        Args:
            message: Parsed HL7 message.

        Returns:
            Encounter data dictionary or None if not found.
        """
        pv1 = message.get_segment("PV1")
        pid = message.get_segment("PID")

        if not pv1:
            return None

        evn = message.get_segment("EVN")
        admit_time = None
        if evn:
            admit_time = self.parser._parse_timestamp(evn.get_field(2) or "")

        return {
            "source_id": pv1.get_field(19) or pv1.get_field(5),  # Visit number
            "patient_id": pid.get_field(3, 0) if pid else None,
            "encounter_type": self._map_patient_class(pv1.get_field(2)),
            "status": "active" if message.message_type.endswith("A01") else "finished",
            "admission_date": admit_time or pv1.get_field(44),
            "discharge_date": pv1.get_field(45),
            "location": pv1.get_field(3, 0),  # Point of care
            "attending_provider": pv1.get_field(7, 0),
            "admit_source": pv1.get_field(14),
            "discharge_disposition": pv1.get_field(36),
            "_raw": message.raw,
        }

    def extract_diagnoses_from_message(self, message: HL7Message) -> list[dict[str, Any]]:
        """
        Extract diagnosis data from an HL7 message.

        Args:
            message: Parsed HL7 message.

        Returns:
            List of diagnosis dictionaries.
        """
        diagnoses = []
        pid = message.get_segment("PID")
        pv1 = message.get_segment("PV1")

        for dg1 in message.get_all_segments("DG1"):
            diagnoses.append({
                "source_id": dg1.get_field(1),  # Set ID
                "patient_id": pid.get_field(3, 0) if pid else None,
                "encounter_id": pv1.get_field(19) if pv1 else None,
                "code": dg1.get_field(3, 0),  # Diagnosis code
                "code_system": dg1.get_field(3, 2),  # Coding system
                "description": dg1.get_field(3, 1),  # Description
                "diagnosis_type": dg1.get_field(6),  # Diagnosis type
                "onset_date": self.parser._parse_timestamp(dg1.get_field(5) or ""),
                "_raw": message.raw,
            })

        return diagnoses

    def extract_observations_from_message(self, message: HL7Message) -> list[dict[str, Any]]:
        """
        Extract observation (lab/vitals) data from an HL7 message.

        Args:
            message: Parsed HL7 message.

        Returns:
            List of observation dictionaries.
        """
        observations = []
        pid = message.get_segment("PID")
        pv1 = message.get_segment("PV1")
        obr = message.get_segment("OBR")

        for obx in message.get_all_segments("OBX"):
            value_type = obx.get_field(2)
            value = obx.get_field(5, 0)

            # Parse numeric values
            numeric_value = None
            if value_type in ("NM", "SN"):
                try:
                    numeric_value = float(value) if value else None
                except ValueError:
                    pass

            observations.append({
                "source_id": obx.get_field(1),  # Set ID
                "patient_id": pid.get_field(3, 0) if pid else None,
                "encounter_id": pv1.get_field(19) if pv1 else None,
                "code": obx.get_field(3, 0),  # Observation identifier
                "code_system": obx.get_field(3, 2),
                "description": obx.get_field(3, 1),
                "value": numeric_value,
                "value_string": value if not numeric_value else None,
                "value_unit": obx.get_field(6, 0),
                "reference_range": obx.get_field(7),
                "interpretation": obx.get_field(8, 0),
                "status": obx.get_field(11),
                "effective_date": self.parser._parse_timestamp(obx.get_field(14) or "")
                or (
                    self.parser._parse_timestamp(obr.get_field(7) or "")
                    if obr
                    else None
                ),
                "_raw": message.raw,
            })

        return observations

    @staticmethod
    def _map_gender(hl7_gender: str | None) -> str | None:
        """Map HL7 gender code to standard value."""
        mapping = {
            "M": "male",
            "F": "female",
            "O": "other",
            "U": "unknown",
            "A": "other",
            "N": "unknown",
        }
        return mapping.get(hl7_gender or "", None)

    @staticmethod
    def _map_patient_class(hl7_class: str | None) -> str | None:
        """Map HL7 patient class to encounter type."""
        mapping = {
            "I": "inpatient",
            "O": "outpatient",
            "E": "emergency",
            "P": "preadmit",
            "R": "recurring",
            "B": "obstetrics",
            "C": "commercial",
            "N": "not_applicable",
            "U": "unknown",
        }
        return mapping.get(hl7_class or "", "unknown")

    # BaseConnector abstract method implementations

    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch patients from processed messages."""
        for msg in self._messages:
            if msg.message_type.startswith("ADT"):
                patient = self.extract_patient_from_message(msg)
                if patient:
                    # Filter by timestamp if specified
                    if since and msg.timestamp and msg.timestamp < since:
                        continue
                    # Filter by patient ID if specified
                    if patient_ids and patient.get("mrn") not in patient_ids:
                        continue
                    yield patient

    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch encounters from processed messages."""
        for msg in self._messages:
            if msg.message_type.startswith("ADT"):
                encounter = self.extract_encounter_from_message(msg)
                if encounter:
                    if since and msg.timestamp and msg.timestamp < since:
                        continue
                    if patient_ids and encounter.get("patient_id") not in patient_ids:
                        continue
                    yield encounter

    def fetch_diagnoses(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch diagnoses from processed messages."""
        for msg in self._messages:
            diagnoses = self.extract_diagnoses_from_message(msg)
            for dx in diagnoses:
                if since and msg.timestamp and msg.timestamp < since:
                    continue
                if encounter_ids and dx.get("encounter_id") not in encounter_ids:
                    continue
                yield dx

    def fetch_procedures(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch procedures - not implemented for HL7."""
        return
        yield  # Make this a generator

    def fetch_lab_results(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch lab results from ORU messages."""
        for msg in self._messages:
            if msg.message_type.startswith("ORU"):
                observations = self.extract_observations_from_message(msg)
                for obs in observations:
                    if since and msg.timestamp and msg.timestamp < since:
                        continue
                    if patient_ids and obs.get("patient_id") not in patient_ids:
                        continue
                    yield obs

    def fetch_vitals(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch vitals - processed same as lab results for HL7."""
        yield from self.fetch_lab_results(since, patient_ids)

    def fetch_medications(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch medications - not implemented for basic HL7."""
        return
        yield  # Make this a generator
