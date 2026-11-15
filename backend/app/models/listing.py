"""What a listing carries beyond its own row: the category template
(specification parameters, certificate types) and the seller's answers.

Templates are admin-managed and keyed on the product category, the same
way KYB document types are keyed on the country. They are never deleted
(listings reference them): set ``active = false`` to retire one.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime

#: ``category`` value of a certificate type that applies to every category.
ALL_CATEGORIES = "*"

SPEC_VALUE_TYPES = ("number", "text")
SPEC_OPERATORS = ("MIN", "MAX", "EQ")
CERT_VISIBILITIES = ("internal", "downloadable")


class SpecParameter(Base):
    """One row of a category's specification template, e.g. Rice → moisture,
    in %, stated as a maximum."""

    __tablename__ = "spec_parameters"
    __table_args__ = (
        Index("uq_spec_parameters_category_code", "category", "code", unique=True),
        CheckConstraint("value_type IN ('number', 'text')", name="ck_spec_parameters_value_type"),
        CheckConstraint("default_operator IN ('MIN', 'MAX', 'EQ')", name="ck_spec_parameters_default_operator"),
        CheckConstraint("code = lower(code)", name="ck_spec_parameters_code_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_type: Mapped[str] = mapped_column(String(10), nullable=False, default="number", server_default="number")
    # One unit per parameter, so two listings' values can be compared.
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    default_operator: Mapped[str] = mapped_column(String(3), nullable=False, default="MAX", server_default="MAX")
    # Suggested test method shown as the field's placeholder.
    test_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductSpec(Base):
    """A seller's value for one template parameter on one listing."""

    __tablename__ = "product_specs"
    __table_args__ = (
        Index("uq_product_specs_product_parameter", "product_id", "parameter_id", unique=True),
        CheckConstraint("operator IN ('MIN', 'MAX', 'EQ')", name="ck_product_specs_operator"),
        CheckConstraint(
            "(value_number IS NULL) <> (value_text IS NULL)", name="ck_product_specs_one_value"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE", name="fk_product_specs_product_id"), nullable=False
    )
    parameter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("spec_parameters.id", ondelete="RESTRICT", name="fk_product_specs_parameter_id"),
        nullable=False,
    )
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(precision=14, scale=4), nullable=True)
    value_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    operator: Mapped[str] = mapped_column(String(3), nullable=False)
    test_method: Mapped[str | None] = mapped_column(String(100), nullable=True)


class CertificateType(Base):
    """A document a listing can carry (COA, test report, product certificate).
    ``category`` is a product category, or ``*`` for every category."""

    __tablename__ = "certificate_types"
    __table_args__ = (
        Index("uq_certificate_types_category_code", "category", "code", unique=True),
        CheckConstraint("code = lower(code)", name="ck_certificate_types_code_lowercase"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default=ALL_CATEGORIES)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    help_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ProductCertificate(Base):
    """A certificate file on a listing. Internal until an admin marks it
    downloadable; only then can a verified buyer fetch it."""

    __tablename__ = "product_certificates"
    __table_args__ = (
        Index("uq_product_certificates_product_type", "product_id", "certificate_type_id", unique=True),
        CheckConstraint("visibility IN ('internal', 'downloadable')", name="ck_product_certificates_visibility"),
        CheckConstraint("size_bytes > 0", name="ck_product_certificates_size"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE", name="fk_product_certificates_product_id"), nullable=False
    )
    certificate_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("certificate_types.id", ondelete="RESTRICT", name="fk_product_certificates_certificate_type_id"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(300), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    visibility: Mapped[str] = mapped_column(String(15), nullable=False, default="internal", server_default="internal")
    visibility_set_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("admin_users.id", ondelete="SET NULL", name="fk_product_certificates_visibility_set_by"),
        nullable=True,
    )
    visibility_set_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_product_certificates_uploaded_by_user_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())


class CertificateDownload(Base):
    """One buyer download of a listing certificate (append-only)."""

    __tablename__ = "certificate_downloads"
    __table_args__ = (
        Index("ix_certificate_downloads_certificate", "certificate_id", text("downloaded_at DESC")),
        Index("ix_certificate_downloads_buyer", "buyer_business_id", text("downloaded_at DESC")),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    certificate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("product_certificates.id", ondelete="CASCADE", name="fk_certificate_downloads_certificate_id"),
        nullable=False,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("products.id", ondelete="CASCADE", name="fk_certificate_downloads_product_id"), nullable=False
    )
    buyer_business_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("businesses.id", ondelete="CASCADE", name="fk_certificate_downloads_buyer_business_id"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL", name="fk_certificate_downloads_user_id"), nullable=True
    )
    downloaded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
