from __future__ import annotations

from datetime import datetime

from app.shared.schemas import CamelModel


class MilestoneOut(CamelModel):
    """A payment milestone as its own party reads it."""

    sequence: int
    kind: str
    amount_minor: int
    currency: str
    due_event: str
    due_days: int
    due_at: datetime | None
    status: str


class DeskMilestoneOut(MilestoneOut):
    id: str
    leg: str
    gate: str
    cleared_at: datetime | None
