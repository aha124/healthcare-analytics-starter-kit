"""Field-level encryption utilities for PHI protection."""

import base64
import hashlib
import os
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from config.logging_config import get_logger
from config.settings import get_settings

logger = get_logger(__name__)


class FieldEncryption:
    """
    Field-level encryption for PHI and sensitive data.

    This class provides Fernet-based symmetric encryption for
    protecting sensitive fields at rest. It's designed for:
    - Encrypting specific PHI fields (SSN, MRN, etc.)
    - Supporting key rotation
    - Providing deterministic hashing for matching

    IMPORTANT: Store encryption keys securely (e.g., AWS KMS, HashiCorp Vault).
    Never commit encryption keys to version control.

    Example:
        >>> encryption = FieldEncryption()
        >>> encrypted = encryption.encrypt("123-45-6789")
        >>> decrypted = encryption.decrypt(encrypted)
        >>> assert decrypted == "123-45-6789"
    """

    def __init__(self, key: str | bytes | None = None):
        """
        Initialize field encryption.

        Args:
            key: Fernet key or password. If not provided, uses ENCRYPTION_KEY
                 from settings. Can be a Fernet key (base64) or a password
                 that will be derived into a key.
        """
        self._logger = get_logger(__name__)

        if key is None:
            settings = get_settings()
            key = settings.security.encryption_key.get_secret_value()

        if not key:
            self._logger.warning("No encryption key configured - encryption disabled")
            self._fernet = None
            return

        # Determine if this is a Fernet key or a password
        if isinstance(key, str):
            try:
                # Try to use as Fernet key directly
                self._fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except Exception:
                # Derive key from password
                self._fernet = Fernet(self._derive_key(key))
        else:
            self._fernet = Fernet(key)

    @staticmethod
    def _derive_key(password: str, salt: bytes | None = None) -> bytes:
        """
        Derive a Fernet key from a password.

        Args:
            password: Password to derive key from.
            salt: Optional salt (uses fixed salt if not provided).

        Returns:
            Base64-encoded Fernet key.
        """
        # Use a fixed salt for deterministic key derivation
        # In production, consider using a proper salt management system
        if salt is None:
            salt = b"healthcare_analytics_salt_v1"

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded Fernet key string.

        Example:
            >>> key = FieldEncryption.generate_key()
            >>> print(key)  # Save this securely!
        """
        return Fernet.generate_key().decode()

    def encrypt(self, plaintext: str | None) -> str | None:
        """
        Encrypt a string value.

        Args:
            plaintext: Value to encrypt.

        Returns:
            Base64-encoded encrypted value, or None if input is None.
        """
        if plaintext is None:
            return None

        if self._fernet is None:
            self._logger.warning("Encryption disabled - returning plaintext")
            return plaintext

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            self._logger.error("Encryption failed", error=str(e))
            raise

    def decrypt(self, ciphertext: str | None) -> str | None:
        """
        Decrypt an encrypted value.

        Args:
            ciphertext: Base64-encoded encrypted value.

        Returns:
            Decrypted plaintext, or None if input is None.

        Raises:
            InvalidToken: If decryption fails (wrong key or corrupted data).
        """
        if ciphertext is None:
            return None

        if self._fernet is None:
            self._logger.warning("Encryption disabled - returning ciphertext")
            return ciphertext

        try:
            decoded = base64.urlsafe_b64decode(ciphertext.encode())
            decrypted = self._fernet.decrypt(decoded)
            return decrypted.decode()
        except InvalidToken:
            self._logger.error("Decryption failed - invalid token or key")
            raise
        except Exception as e:
            self._logger.error("Decryption failed", error=str(e))
            raise

    def encrypt_dict(
        self,
        data: dict[str, Any],
        fields: list[str],
    ) -> dict[str, Any]:
        """
        Encrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing data.
            fields: List of field names to encrypt.

        Returns:
            New dictionary with specified fields encrypted.
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field] is not None:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict(
        self,
        data: dict[str, Any],
        fields: list[str],
    ) -> dict[str, Any]:
        """
        Decrypt specific fields in a dictionary.

        Args:
            data: Dictionary containing encrypted data.
            fields: List of field names to decrypt.

        Returns:
            New dictionary with specified fields decrypted.
        """
        result = data.copy()
        for field in fields:
            if field in result and result[field] is not None:
                result[field] = self.decrypt(str(result[field]))
        return result

    @staticmethod
    def hash_for_matching(value: str | None, salt: str = "") -> str | None:
        """
        Create a deterministic hash for matching without decryption.

        This is useful for creating lookup keys for encrypted values
        (e.g., finding patients by SSN without decrypting all SSNs).

        Args:
            value: Value to hash.
            salt: Optional salt for the hash.

        Returns:
            SHA-256 hash of the value, or None if input is None.
        """
        if value is None:
            return None

        salted = f"{salt}:{value}"
        return hashlib.sha256(salted.encode()).hexdigest()


# Convenience functions for simple use cases


@lru_cache(maxsize=1)
def _get_default_encryption() -> FieldEncryption:
    """Get cached default encryption instance."""
    return FieldEncryption()


def encrypt_field(value: str | None) -> str | None:
    """
    Encrypt a field value using default encryption.

    Args:
        value: Value to encrypt.

    Returns:
        Encrypted value.

    Example:
        >>> encrypted = encrypt_field("123-45-6789")
    """
    return _get_default_encryption().encrypt(value)


def decrypt_field(value: str | None) -> str | None:
    """
    Decrypt a field value using default encryption.

    Args:
        value: Encrypted value.

    Returns:
        Decrypted value.

    Example:
        >>> decrypted = decrypt_field(encrypted_ssn)
    """
    return _get_default_encryption().decrypt(value)


def hash_phi(value: str | None) -> str | None:
    """
    Create a hash of PHI for matching purposes.

    Args:
        value: PHI value to hash.

    Returns:
        Deterministic hash of the value.
    """
    return FieldEncryption.hash_for_matching(value, salt="phi_match")


# PHI fields that should typically be encrypted
PHI_FIELDS_TO_ENCRYPT = [
    "ssn",
    "social_security_number",
    "mrn",
    "medical_record_number",
    "account_number",
    "insurance_id",
    "drivers_license",
]


def encrypt_phi_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Encrypt all common PHI fields in a dictionary.

    Args:
        data: Dictionary potentially containing PHI.

    Returns:
        Dictionary with PHI fields encrypted.
    """
    encryption = _get_default_encryption()
    return encryption.encrypt_dict(data, PHI_FIELDS_TO_ENCRYPT)


def decrypt_phi_fields(data: dict[str, Any]) -> dict[str, Any]:
    """
    Decrypt all common PHI fields in a dictionary.

    Args:
        data: Dictionary with encrypted PHI.

    Returns:
        Dictionary with PHI fields decrypted.
    """
    encryption = _get_default_encryption()
    return encryption.decrypt_dict(data, PHI_FIELDS_TO_ENCRYPT)
