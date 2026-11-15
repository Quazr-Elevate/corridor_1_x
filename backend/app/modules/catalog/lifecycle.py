"""Listing status: the one place a listing changes state.

    draft ──submit──▶ under_review ──approve──▶ published ◀──resume── paused
      ▲                 │    │                     │  └────pause────────▲
      └────withdraw─────┘    └──reject──▶ rejected ◀──reject (take down)┘
                                             │
                                             └──submit──▶ under_review

A status is never set from a request body: the router calls an action, the
action calls :func:`transition`.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from app.core.errors import Conflict
from app.models.product import ListingStatus, Product

S = ListingStatus

_ALLOWED: dict[str, frozenset[str]] = {
    S.draft: frozenset({S.under_review}),
    S.rejected: frozenset({S.under_review}),
    S.under_review: frozenset({S.draft, S.published, S.rejected}),
    S.published: frozenset({S.paused, S.rejected}),
    S.paused: frozenset({S.published, S.rejected}),
}

_LABEL = {
    S.draft: "a draft",
    S.under_review: "with the reviewer",
    S.published: "published",
    S.rejected: "rejected",
    S.paused: "paused",
}


def transition(
    product: Product,
    to: str,
    *,
    now: datetime,
    admin_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> None:
    """Move ``product`` to ``to`` and stamp the review trail, or raise
    :class:`Conflict` when the move isn't allowed from where it is."""
    current = product.status
    if to not in _ALLOWED.get(current, frozenset()):
        raise Conflict(f"This listing is {_LABEL.get(current, current)}, so that isn't possible right now.")
    product.status = to
    if to == S.under_review:
        product.submitted_at = now
        product.rejection_reason = None
    elif to == S.published and current == S.under_review:
        product.published_at = now
        product.reviewed_at = now
        product.reviewed_by = admin_id
        product.rejection_reason = None
    elif to == S.rejected:
        product.reviewed_at = now
        product.reviewed_by = admin_id
        product.rejection_reason = reason
        # A taken-down listing loses any edit that was waiting for review.
        product.pending_revision = None
        product.revision_submitted_at = None
