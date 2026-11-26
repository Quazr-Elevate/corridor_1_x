"""Samples (M4 · S8, CX-102, A-077).

    requested ─(seller)→ seller_dispatched ─(desk)→ at_hub ─(desk)→ split_sealed
      ─(desk)→ forwarded ─(desk)→ buyer_received ─(buyer)→ reviewed

The buyer pays the sample fee in credits when asking. The seller ships to
the Corridor One X hub, which splits the sample, seals both halves, keeps
one (its seal number is recorded) and forwards the other under Corridor One
X's name. Forwarding without the seal numbers is refused here and by the
database. Every hop is a ``sample_events`` row with its time and who did it.

The seller's courier reference names the seller and the buyer's forward
reference is Corridor One X's: each side sees only its own leg."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BadRequest, Conflict, NotFound
from app.core.time import utcnow
from app.models.deal import Deal
from app.models.negotiation import Sample, SampleEvent
from app.models.user import User
from app.modules.credits import service as credits
from app.modules.masking import service as masking
from app.modules.negotiation import service as chat
from app.shared import leakfilter

#: (from, to) → who records it.
HOPS: dict[tuple[str, str], str] = {
    ("requested", "seller_dispatched"): "seller",
    ("seller_dispatched", "at_hub"): "desk",
    ("at_hub", "split_sealed"): "desk",
    ("split_sealed", "forwarded"): "desk",
    ("forwarded", "buyer_received"): "desk",
    ("buyer_received", "reviewed"): "buyer",
}
OPEN = ("requested", "seller_dispatched", "at_hub", "split_sealed", "forwarded", "buyer_received")


def _move(db: AsyncSession, sample: Sample, to: str, *, actor_type: str, actor_id: uuid.UUID | None) -> None:
    """The one place a sample changes status."""
    if (sample.status, to) not in HOPS:
        raise Conflict(f"A sample that is {sample.status.replace('_', ' ')} can't move to {to.replace('_', ' ')}.")
    db.add(SampleEvent(sample_id=sample.id, from_status=sample.status, to_status=to, actor_type=actor_type,
                       actor_id=actor_id, created_at=utcnow()))
    sample.status = to
    sample.updated_at = utcnow()


def _clean_ref(raw: str, what: str) -> str:
    ref = " ".join((raw or "").split())
    if len(ref) < 4:
        raise BadRequest(f"Enter the {what}.")
    return ref[:100]


# ── Traders ──────────────────────────────────────────────────────────


async def request(db: AsyncSession, user: User, code: str) -> Sample:
    """The buyer asks for a sample and pays the sample fee (A-077). One open
    sample per deal at a time. The caller commits the charge and the sample
    together."""
    p = await chat.party(db, user, code)
    if p.side != "buyer":
        raise NotFound("Deal not found.")
    if p.deal.status not in chat.WRITABLE:
        raise Conflict("Samples can be asked for while the deal is being negotiated.")
    chat.ensure_can_trade(user.business)
    if await db.scalar(select(Sample.id).where(Sample.deal_id == p.deal.id, Sample.status.in_(OPEN))):
        raise Conflict("A sample is already on its way on this deal.")
    sample = Sample(id=uuid.uuid4(), deal_id=p.deal.id, status="requested", requested_by_user_id=user.id,
                    created_at=utcnow())
    await credits.spend(db, user, "SAMPLE_FEE", idempotency_key=f"sample:{sample.id}", reference=("sample", str(sample.id)))
    db.add(sample)
    await db.flush()
    db.add(SampleEvent(sample_id=sample.id, from_status=None, to_status="requested", actor_type="user",
                       actor_id=user.id, created_at=utcnow()))
    return sample


async def of_party(db: AsyncSession, user: User, code: str) -> tuple[str, Deal, list[Sample]]:
    p = await chat.party(db, user, code)
    rows = list(await db.scalars(
        select(Sample).where(Sample.deal_id == p.deal.id).order_by(Sample.created_at.desc())
    ))
    return p.side, p.deal, rows


async def _own_sample(db: AsyncSession, user: User, code: str, sample_id: uuid.UUID | None, side: str) -> Sample:
    p = await chat.party(db, user, code)
    sample = await db.get(Sample, sample_id) if sample_id else None
    if sample is None or sample.deal_id != p.deal.id or p.side != side:
        raise NotFound("Sample not found.")
    chat.ensure_can_trade(user.business)
    return sample


async def dispatch(db: AsyncSession, user: User, code: str, sample_id: uuid.UUID | None, courier_ref: str) -> Sample:
    """The seller has sent the sample to the hub."""
    sample = await _own_sample(db, user, code, sample_id, "seller")
    sample.seller_courier_ref = _clean_ref(courier_ref, "courier and tracking number")
    _move(db, sample, "seller_dispatched", actor_type="user", actor_id=user.id)
    return sample


async def review(
    db: AsyncSession, user: User, code: str, sample_id: uuid.UUID | None, verdict: str, note: str | None
) -> Sample:
    """The buyer's verdict on the sample it received."""
    sample = await _own_sample(db, user, code, sample_id, "buyer")
    if note:
        result = leakfilter.check(note, await masking.legal_name_for_text_check(db, user.business_id))
        if result.verdict is not leakfilter.Verdict.PASS:
            raise BadRequest(f"Remove the {', '.join(result.reasons)} from the note.")
    sample.verdict = verdict
    sample.review_note = note or None
    _move(db, sample, "reviewed", actor_type="user", actor_id=user.id)
    return sample


# ── The desk ─────────────────────────────────────────────────────────


async def desk_sample(db: AsyncSession, sample_id: uuid.UUID | None) -> tuple[Sample, Deal]:
    sample = await db.get(Sample, sample_id) if sample_id else None
    if sample is None:
        raise NotFound("Sample not found.")
    return sample, await db.get(Deal, sample.deal_id)


async def at_hub(db: AsyncSession, admin_id: uuid.UUID, sample_id: uuid.UUID | None) -> tuple[Sample, Deal]:
    sample, deal = await desk_sample(db, sample_id)
    _move(db, sample, "at_hub", actor_type="admin", actor_id=admin_id)
    return sample, deal


async def seal(
    db: AsyncSession, admin_id: uuid.UUID, sample_id: uuid.UUID | None, retained: str, forward: str
) -> tuple[Sample, Deal]:
    """Split and seal: the retained half's number is what a dispute will rely on."""
    sample, deal = await desk_sample(db, sample_id)
    retained, forward = _clean_ref(retained, "retained seal number"), _clean_ref(forward, "forward seal number")
    if retained == forward:
        raise BadRequest("The two halves need different seal numbers.")
    sample.retained_seal_no, sample.forward_seal_no = retained[:40], forward[:40]
    _move(db, sample, "split_sealed", actor_type="admin", actor_id=admin_id)
    return sample, deal


async def forward(
    db: AsyncSession, admin_id: uuid.UUID, sample_id: uuid.UUID | None, courier_ref: str
) -> tuple[Sample, Deal]:
    sample, deal = await desk_sample(db, sample_id)
    if not sample.retained_seal_no:
        raise Conflict("Seal both halves and record the retained seal number before forwarding.")
    sample.forward_courier_ref = _clean_ref(courier_ref, "courier and tracking number")
    _move(db, sample, "forwarded", actor_type="admin", actor_id=admin_id)
    return sample, deal


async def received(db: AsyncSession, admin_id: uuid.UUID, sample_id: uuid.UUID | None) -> tuple[Sample, Deal]:
    sample, deal = await desk_sample(db, sample_id)
    _move(db, sample, "buyer_received", actor_type="admin", actor_id=admin_id)
    return sample, deal


async def open_samples(db: AsyncSession) -> list[tuple[Sample, Deal]]:
    return list((await db.execute(
        select(Sample, Deal).join(Deal, Deal.id == Sample.deal_id)
        .where(Sample.status.in_(OPEN)).order_by(Sample.created_at)
    )).all())


async def events(db: AsyncSession, sample_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[SampleEvent]]:
    out: dict[uuid.UUID, list[SampleEvent]] = {i: [] for i in sample_ids}
    if sample_ids:
        for e in await db.scalars(
            select(SampleEvent).where(SampleEvent.sample_id.in_(sample_ids)).order_by(SampleEvent.created_at)
        ):
            out[e.sample_id].append(e)
    return out


