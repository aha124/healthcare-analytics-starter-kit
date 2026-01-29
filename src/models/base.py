"""SQLAlchemy base model and mixins for Healthcare Analytics."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    # Enable automatic table name generation
    @classmethod
    def __tablename__(cls) -> str:
        """Generate table name from class name."""
        # Convert CamelCase to snake_case
        name = cls.__name__
        result = [name[0].lower()]
        for char in name[1:]:
            if char.isupper():
                result.append("_")
            result.append(char.lower())
        return "".join(result)

    def to_dict(self) -> dict[str, Any]:
        """Convert model to dictionary."""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def __repr__(self) -> str:
        """String representation of model."""
        pk_cols = [col.name for col in self.__table__.primary_key.columns]
        pk_vals = [getattr(self, col) for col in pk_cols]
        pk_str = ", ".join(f"{k}={v}" for k, v in zip(pk_cols, pk_vals))
        return f"<{self.__class__.__name__}({pk_str})>"


class TimestampMixin:
    """Mixin for automatic timestamp tracking."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AuditMixin(TimestampMixin):
    """Mixin for audit trail tracking."""

    created_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    source_system: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Source system identifier",
    )
    source_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Original ID from source system",
    )
    batch_id: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="ETL batch identifier",
    )


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""

    is_deleted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deleted_by: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )


class EncryptedFieldMixin:
    """
    Mixin indicating model contains encrypted fields.

    Fields that may contain PHI should be encrypted at rest.
    Use the encryption utilities in src/utils/encryption.py.
    """

    # Encrypted fields should be stored as strings (base64 encoded)
    # and decrypted on access using application-level encryption.
    #
    # Example usage in a model:
    #
    # class Patient(Base, EncryptedFieldMixin):
    #     ssn_encrypted: Mapped[str | None] = mapped_column(String(500))
    #
    #     @property
    #     def ssn(self) -> str | None:
    #         from src.utils.encryption import decrypt_field
    #         return decrypt_field(self.ssn_encrypted)
    #
    #     @ssn.setter
    #     def ssn(self, value: str | None) -> None:
    #         from src.utils.encryption import encrypt_field
    #         self.ssn_encrypted = encrypt_field(value)

    pass
