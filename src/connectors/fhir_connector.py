"""FHIR R4 API connector for EMR integration."""

import time
from datetime import datetime
from typing import Any, Generator

import httpx
from pydantic import Field, SecretStr

from config.logging_config import get_logger
from src.connectors.base_connector import (
    AuthenticationError,
    BaseConnector,
    ConnectionStatus,
    ConnectorConfig,
    DataFetchError,
)

logger = get_logger(__name__)


class FHIRConfig(ConnectorConfig):
    """Configuration for FHIR R4 API connector."""

    base_url: str = Field(..., description="FHIR server base URL")
    client_id: str = Field(default="", description="OAuth2 client ID")
    client_secret: SecretStr = Field(default=SecretStr(""), description="OAuth2 client secret")
    token_url: str = Field(default="", description="OAuth2 token endpoint")
    scopes: list[str] = Field(
        default=["patient/*.read", "encounter/*.read", "observation/*.read"],
        description="OAuth2 scopes",
    )
    use_backend_services: bool = Field(
        default=False,
        description="Use SMART Backend Services (JWT auth)",
    )
    private_key_path: str | None = Field(
        default=None,
        description="Path to private key for JWT auth",
    )
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")
    page_size: int = Field(default=100, ge=1, le=1000, description="Results per page")


class FHIRConnector(BaseConnector):
    """
    FHIR R4 API connector for Epic, Cerner, and other FHIR-enabled EMRs.

    This connector supports:
    - OAuth2 client credentials flow
    - SMART Backend Services (JWT-based auth for Epic)
    - Pagination via FHIR bundles
    - Standard FHIR R4 resources

    Example:
        >>> config = FHIRConfig(
        ...     name="epic_fhir",
        ...     base_url="https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4",
        ...     client_id="your_client_id",
        ...     client_secret=SecretStr("your_secret"),
        ...     token_url="https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token",
        ... )
        >>> with FHIRConnector(config) as connector:
        ...     for patient in connector.fetch_patients():
        ...         print(patient)
    """

    def __init__(self, config: FHIRConfig):
        """
        Initialize FHIR connector.

        Args:
            config: FHIR connector configuration.
        """
        super().__init__(config)
        self.config: FHIRConfig = config
        self._client: httpx.Client | None = None
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    def connect(self) -> bool:
        """
        Establish connection and authenticate with FHIR server.

        Returns:
            True if connection and authentication successful.

        Raises:
            AuthenticationError: If authentication fails.
        """
        self._logger.info("Connecting to FHIR server", base_url=self.config.base_url)
        self.status = ConnectionStatus.AUTHENTICATING

        try:
            self._client = httpx.Client(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )

            # Authenticate if credentials provided
            if self.config.client_id:
                self._authenticate()

            self.status = ConnectionStatus.CONNECTED
            self._logger.info("Successfully connected to FHIR server")
            return True

        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self._record_error(str(e))
            raise AuthenticationError(str(e), self.config.name)

    def _authenticate(self) -> None:
        """
        Authenticate with the FHIR server.

        Supports OAuth2 client credentials and SMART Backend Services.

        Raises:
            AuthenticationError: If authentication fails.
        """
        if self.config.use_backend_services:
            self._authenticate_backend_services()
        else:
            self._authenticate_client_credentials()

    def _authenticate_client_credentials(self) -> None:
        """Authenticate using OAuth2 client credentials flow."""
        if not self.config.token_url:
            raise AuthenticationError("Token URL required for OAuth2", self.config.name)

        self._logger.debug("Authenticating with client credentials")

        response = httpx.post(
            self.config.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret.get_secret_value(),
                "scope": " ".join(self.config.scopes),
            },
            timeout=self.config.timeout,
        )

        if response.status_code != 200:
            raise AuthenticationError(
                f"OAuth2 authentication failed: {response.text}",
                self.config.name,
            )

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = datetime.now().replace(
            second=datetime.now().second + expires_in - 60  # Refresh 60s before expiry
        )

        self._logger.debug("Successfully obtained access token")

    def _authenticate_backend_services(self) -> None:
        """
        Authenticate using SMART Backend Services (JWT).

        This is the preferred method for Epic integrations.
        """
        import jwt
        from cryptography.hazmat.primitives import serialization

        if not self.config.private_key_path:
            raise AuthenticationError(
                "Private key path required for Backend Services auth",
                self.config.name,
            )

        self._logger.debug("Authenticating with SMART Backend Services")

        # Load private key
        with open(self.config.private_key_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
            )

        # Create JWT assertion
        now = int(time.time())
        claims = {
            "iss": self.config.client_id,
            "sub": self.config.client_id,
            "aud": self.config.token_url,
            "jti": f"{now}-{id(self)}",
            "exp": now + 300,  # 5 minute expiry
        }

        assertion = jwt.encode(claims, private_key, algorithm="RS384")

        # Exchange JWT for access token
        response = httpx.post(
            self.config.token_url,
            data={
                "grant_type": "client_credentials",
                "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
                "client_assertion": assertion,
                "scope": " ".join(self.config.scopes),
            },
            timeout=self.config.timeout,
        )

        if response.status_code != 200:
            raise AuthenticationError(
                f"Backend Services authentication failed: {response.text}",
                self.config.name,
            )

        token_data = response.json()
        self._access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        self._token_expires_at = datetime.now().replace(
            second=datetime.now().second + expires_in - 60
        )

    def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token, refreshing if needed."""
        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            self._logger.debug("Access token expired, re-authenticating")
            self._authenticate()

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers including authorization."""
        headers = {
            "Accept": "application/fhir+json",
            "Content-Type": "application/fhir+json",
        }
        if self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return headers

    def disconnect(self) -> None:
        """Close the HTTP client connection."""
        if self._client:
            self._client.close()
            self._client = None
        self._access_token = None
        self._token_expires_at = None
        self.status = ConnectionStatus.DISCONNECTED
        self._logger.info("Disconnected from FHIR server")

    def test_connection(self) -> bool:
        """
        Test connection by fetching server capability statement.

        Returns:
            True if connection is healthy.
        """
        if not self._client:
            return False

        try:
            self._ensure_authenticated()
            response = self._client.get("/metadata", headers=self._get_headers())
            return response.status_code == 200
        except Exception as e:
            self._logger.warning("Connection test failed", error=str(e))
            return False

    def _fetch_resource(
        self,
        resource_type: str,
        params: dict[str, Any] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """
        Fetch FHIR resources with pagination.

        Args:
            resource_type: FHIR resource type (Patient, Encounter, etc.).
            params: Query parameters.

        Yields:
            Individual resource dictionaries.
        """
        if not self._client:
            raise DataFetchError(
                "Not connected",
                self.config.name,
                resource_type,
            )

        self._ensure_authenticated()

        params = params or {}
        params["_count"] = self.config.page_size

        url = f"/{resource_type}"
        headers = self._get_headers()

        while url:
            start_time = time.time()

            try:
                response = self._client.get(url, params=params, headers=headers)
                response_time_ms = (time.time() - start_time) * 1000

                if response.status_code == 429:
                    # Rate limited - wait and retry
                    retry_after = int(response.headers.get("Retry-After", 60))
                    self._logger.warning(
                        "Rate limited, waiting",
                        retry_after_seconds=retry_after,
                    )
                    self.status = ConnectionStatus.RATE_LIMITED
                    time.sleep(retry_after)
                    self.status = ConnectionStatus.CONNECTED
                    continue

                if response.status_code != 200:
                    raise DataFetchError(
                        f"HTTP {response.status_code}: {response.text}",
                        self.config.name,
                        resource_type,
                    )

                bundle = response.json()

                # Process entries
                entries = bundle.get("entry", [])
                for entry in entries:
                    resource = entry.get("resource", {})
                    yield self._normalize_resource(resource_type, resource)

                self._record_success(len(entries), response_time_ms)

                # Get next page URL
                url = None
                params = None  # Clear params for next page (URL is complete)
                for link in bundle.get("link", []):
                    if link.get("relation") == "next":
                        url = link.get("url")
                        break

            except httpx.RequestError as e:
                self._record_error(str(e))
                raise DataFetchError(
                    str(e),
                    self.config.name,
                    resource_type,
                    original_error=e,
                )

    def _normalize_resource(
        self,
        resource_type: str,
        resource: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize FHIR resource to standard format.

        Args:
            resource_type: Type of FHIR resource.
            resource: Raw FHIR resource.

        Returns:
            Normalized dictionary.
        """
        normalizers = {
            "Patient": self._normalize_patient,
            "Encounter": self._normalize_encounter,
            "Condition": self._normalize_condition,
            "Procedure": self._normalize_procedure,
            "Observation": self._normalize_observation,
            "MedicationRequest": self._normalize_medication,
        }

        normalizer = normalizers.get(resource_type)
        if normalizer:
            return normalizer(resource)
        return resource

    def _normalize_patient(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize Patient resource."""
        name = resource.get("name", [{}])[0]
        address = resource.get("address", [{}])[0]
        telecom = {t.get("system"): t.get("value") for t in resource.get("telecom", [])}

        return {
            "source_id": resource.get("id"),
            "mrn": self._get_identifier(resource, "MR"),
            "ssn": self._get_identifier(resource, "SS"),
            "first_name": " ".join(name.get("given", [])),
            "last_name": name.get("family", ""),
            "date_of_birth": resource.get("birthDate"),
            "gender": resource.get("gender"),
            "address_line1": " ".join(address.get("line", [])),
            "city": address.get("city"),
            "state": address.get("state"),
            "postal_code": address.get("postalCode"),
            "phone": telecom.get("phone"),
            "email": telecom.get("email"),
            "deceased": resource.get("deceasedBoolean", False),
            "deceased_date": resource.get("deceasedDateTime"),
            "language": resource.get("communication", [{}])[0]
            .get("language", {})
            .get("coding", [{}])[0]
            .get("code"),
            "marital_status": resource.get("maritalStatus", {})
            .get("coding", [{}])[0]
            .get("code"),
            "race": self._get_extension_value(
                resource, "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
            ),
            "ethnicity": self._get_extension_value(
                resource, "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"
            ),
            "_raw": resource,
        }

    def _normalize_encounter(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize Encounter resource."""
        period = resource.get("period", {})
        location = resource.get("location", [{}])[0].get("location", {})

        return {
            "source_id": resource.get("id"),
            "patient_id": self._get_reference_id(resource.get("subject", {})),
            "encounter_type": resource.get("class", {}).get("code"),
            "status": resource.get("status"),
            "admission_date": period.get("start"),
            "discharge_date": period.get("end"),
            "location": location.get("display"),
            "location_id": self._get_reference_id(location),
            "service_provider": resource.get("serviceProvider", {}).get("display"),
            "reason_code": self._get_first_coding(resource.get("reasonCode", [{}])[0]),
            "discharge_disposition": self._get_first_coding(
                resource.get("hospitalization", {}).get("dischargeDisposition", {})
            ),
            "admit_source": self._get_first_coding(
                resource.get("hospitalization", {}).get("admitSource", {})
            ),
            "_raw": resource,
        }

    def _normalize_condition(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize Condition resource (diagnoses)."""
        return {
            "source_id": resource.get("id"),
            "patient_id": self._get_reference_id(resource.get("subject", {})),
            "encounter_id": self._get_reference_id(resource.get("encounter", {})),
            "code": self._get_first_coding(resource.get("code", {})),
            "code_system": self._get_coding_system(resource.get("code", {})),
            "description": resource.get("code", {}).get("text"),
            "clinical_status": self._get_first_coding(
                resource.get("clinicalStatus", {})
            ),
            "verification_status": self._get_first_coding(
                resource.get("verificationStatus", {})
            ),
            "category": self._get_first_coding(
                resource.get("category", [{}])[0]
            ),
            "onset_date": resource.get("onsetDateTime"),
            "abatement_date": resource.get("abatementDateTime"),
            "recorded_date": resource.get("recordedDate"),
            "_raw": resource,
        }

    def _normalize_procedure(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize Procedure resource."""
        return {
            "source_id": resource.get("id"),
            "patient_id": self._get_reference_id(resource.get("subject", {})),
            "encounter_id": self._get_reference_id(resource.get("encounter", {})),
            "code": self._get_first_coding(resource.get("code", {})),
            "code_system": self._get_coding_system(resource.get("code", {})),
            "description": resource.get("code", {}).get("text"),
            "status": resource.get("status"),
            "performed_date": resource.get("performedDateTime")
            or resource.get("performedPeriod", {}).get("start"),
            "performer": self._get_reference_id(
                resource.get("performer", [{}])[0].get("actor", {})
            ),
            "location": self._get_reference_id(resource.get("location", {})),
            "_raw": resource,
        }

    def _normalize_observation(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize Observation resource (labs and vitals)."""
        value = None
        value_unit = None
        value_string = None

        if "valueQuantity" in resource:
            value = resource["valueQuantity"].get("value")
            value_unit = resource["valueQuantity"].get("unit")
        elif "valueString" in resource:
            value_string = resource["valueString"]
        elif "valueCodeableConcept" in resource:
            value_string = self._get_first_coding(resource["valueCodeableConcept"])

        return {
            "source_id": resource.get("id"),
            "patient_id": self._get_reference_id(resource.get("subject", {})),
            "encounter_id": self._get_reference_id(resource.get("encounter", {})),
            "code": self._get_first_coding(resource.get("code", {})),
            "code_system": self._get_coding_system(resource.get("code", {})),
            "description": resource.get("code", {}).get("text"),
            "category": self._get_first_coding(
                resource.get("category", [{}])[0]
            ),
            "value": value,
            "value_unit": value_unit,
            "value_string": value_string,
            "effective_date": resource.get("effectiveDateTime")
            or resource.get("effectivePeriod", {}).get("start"),
            "issued": resource.get("issued"),
            "status": resource.get("status"),
            "interpretation": self._get_first_coding(
                resource.get("interpretation", [{}])[0]
            ),
            "reference_range_low": resource.get("referenceRange", [{}])[0]
            .get("low", {})
            .get("value"),
            "reference_range_high": resource.get("referenceRange", [{}])[0]
            .get("high", {})
            .get("value"),
            "_raw": resource,
        }

    def _normalize_medication(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Normalize MedicationRequest resource."""
        return {
            "source_id": resource.get("id"),
            "patient_id": self._get_reference_id(resource.get("subject", {})),
            "encounter_id": self._get_reference_id(resource.get("encounter", {})),
            "medication_code": self._get_first_coding(
                resource.get("medicationCodeableConcept", {})
            ),
            "medication_name": resource.get("medicationCodeableConcept", {}).get("text"),
            "status": resource.get("status"),
            "intent": resource.get("intent"),
            "authored_on": resource.get("authoredOn"),
            "requester": self._get_reference_id(resource.get("requester", {})),
            "dosage_instruction": resource.get("dosageInstruction", [{}])[0].get("text"),
            "route": self._get_first_coding(
                resource.get("dosageInstruction", [{}])[0].get("route", {})
            ),
            "_raw": resource,
        }

    @staticmethod
    def _get_identifier(resource: dict[str, Any], type_code: str) -> str | None:
        """Extract identifier by type code."""
        for identifier in resource.get("identifier", []):
            id_type = identifier.get("type", {}).get("coding", [{}])[0].get("code")
            if id_type == type_code:
                return identifier.get("value")
        return None

    @staticmethod
    def _get_reference_id(reference: dict[str, Any]) -> str | None:
        """Extract ID from FHIR reference."""
        ref = reference.get("reference", "")
        if "/" in ref:
            return ref.split("/")[-1]
        return ref or None

    @staticmethod
    def _get_first_coding(codeable_concept: dict[str, Any]) -> str | None:
        """Get first code from CodeableConcept."""
        codings = codeable_concept.get("coding", [])
        if codings:
            return codings[0].get("code")
        return None

    @staticmethod
    def _get_coding_system(codeable_concept: dict[str, Any]) -> str | None:
        """Get coding system from CodeableConcept."""
        codings = codeable_concept.get("coding", [])
        if codings:
            return codings[0].get("system")
        return None

    @staticmethod
    def _get_extension_value(resource: dict[str, Any], url: str) -> str | None:
        """Get value from extension by URL."""
        for ext in resource.get("extension", []):
            if ext.get("url") == url:
                # Handle nested extensions (common in US Core race/ethnicity)
                for nested in ext.get("extension", []):
                    if nested.get("url") == "ombCategory":
                        return nested.get("valueCoding", {}).get("code")
                return ext.get("valueString") or ext.get("valueCode")
        return None

    def fetch_patients(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch patient demographics from FHIR server."""
        params: dict[str, Any] = {}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if patient_ids:
            params["_id"] = ",".join(patient_ids)

        yield from self._fetch_resource("Patient", params)

    def fetch_encounters(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch encounters from FHIR server."""
        params: dict[str, Any] = {}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if patient_ids:
            params["patient"] = ",".join(patient_ids)

        yield from self._fetch_resource("Encounter", params)

    def fetch_diagnoses(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch diagnoses (Conditions) from FHIR server."""
        params: dict[str, Any] = {}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if encounter_ids:
            params["encounter"] = ",".join(encounter_ids)

        yield from self._fetch_resource("Condition", params)

    def fetch_procedures(
        self,
        since: datetime | None = None,
        encounter_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch procedures from FHIR server."""
        params: dict[str, Any] = {}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if encounter_ids:
            params["encounter"] = ",".join(encounter_ids)

        yield from self._fetch_resource("Procedure", params)

    def fetch_lab_results(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch lab results from FHIR server."""
        params: dict[str, Any] = {"category": "laboratory"}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if patient_ids:
            params["patient"] = ",".join(patient_ids)

        yield from self._fetch_resource("Observation", params)

    def fetch_vitals(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch vital signs from FHIR server."""
        params: dict[str, Any] = {"category": "vital-signs"}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if patient_ids:
            params["patient"] = ",".join(patient_ids)

        yield from self._fetch_resource("Observation", params)

    def fetch_medications(
        self,
        since: datetime | None = None,
        patient_ids: list[str] | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Fetch medication requests from FHIR server."""
        params: dict[str, Any] = {}
        if since:
            params["_lastUpdated"] = f"ge{since.isoformat()}"
        if patient_ids:
            params["patient"] = ",".join(patient_ids)

        yield from self._fetch_resource("MedicationRequest", params)
