"""Admin-managed catalog: which documents does each country require?

Seeded through the admin console. New or edited rows apply to draft and
rejected businesses immediately; verified businesses are grandfathered —
an admin filter surfaces who's missing a newly-mandatory doc.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CHAR, Boolean, CheckConstraint, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime


class BusinessDocumentRequirement(Base):
    """One row per (country, document type) KYB cares about.

    ``slug`` is the machine key (``gstin``, ``iec``) — a user's upload is
    linked back to this row via ``business_documents.required_doc_type_id``.
    ``display_name`` is what the user sees on their Documents tab.

    Soft-delete via ``is_active = false`` so existing uploads keep their
    FK target; a partial unique index allows re-using a slug after retirement.
    """

    __tablename__ = "business_document_requirements"
    __table_args__ = (
        CheckConstraint("length(country_code) = 2", name="ck_bdr_country_code"),
        # Case-insensitive uniqueness while active. Partial so retired rows
        # don't block re-adding the same (country, slug) later.
        Index(
            "ux_bdr_country_slug_active",
            "country_code",
            "slug",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_bdr_country_active", "country_code", "is_active"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # ISO 3166-1 alpha-2. Validated at the Pydantic layer against the real list.
    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    # Lowercase slug — regex enforced at the Pydantic layer so the check
    # stays portable between SQLite and Postgres.
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    help_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Admin email (no admins table yet). Switches to admin_id FK once the
    # RBAC schema lands — admin_actions carries the same pattern.
    created_by: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now(), onupdate=func.now()
    )
