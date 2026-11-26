"""Negotiation: choosing an offer, two chat threads per deal, leak strikes

Revision ID: 0037_negotiation_chat
Revises: 0036_single_address
Create Date: 2026-11-26

M4 · S8, CX-099 and CX-100 (A-074, A-075); docs/04_data_model.md →
"Negotiation chat (0037)".

* ``deals`` gains ``chosen_offer_id``: the offer the buyer went ahead with,
  which fixes the seller.
* ``offers.status`` gains ``not_chosen`` for the other offers on that deal.
* new ``chat_threads`` (one per deal and side), ``chat_messages`` (never
  edited) and ``leak_strikes`` (blocked messages, text not kept).
* ``businesses`` gains ``suspended_at`` and ``suspended_reason``.

No existing rows change. Portable (Postgres + SQLite batch ops). Reversible:
downgrade drops the new tables and columns; offers marked ``not_chosen``
become ``expired``.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0037_negotiation_chat"
down_revision: Union[str, None] = "0036_single_address"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_OFFER = "status IN ('published', 'expired', 'withdrawn')"
NEW_OFFER = "status IN ('published', 'expired', 'withdrawn', 'not_chosen')"


def upgrade() -> None:
    with op.batch_alter_table("businesses") as batch:
        batch.add_column(sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("suspended_reason", sa.String(200), nullable=True))
        batch.create_check_constraint(
            "ck_businesses_suspension_has_reason", "(suspended_at IS NULL) = (suspended_reason IS NULL)"
        )
    with op.batch_alter_table("offers") as batch:
        batch.drop_constraint("ck_offers_status", type_="check")
        batch.create_check_constraint("ck_offers_status", NEW_OFFER)
    with op.batch_alter_table("deals") as batch:
        batch.add_column(sa.Column("chosen_offer_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_deals_chosen_offer_id", "offers", ["chosen_offer_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "chat_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("side", sa.String(6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("side IN ('buyer', 'seller')", name="ck_chat_threads_side"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="CASCADE", name="fk_chat_threads_deal_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("deal_id", "side", name="uq_chat_threads_deal_side"),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("thread_id", sa.Uuid(), nullable=False),
        sa.Column("origin", sa.String(6), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("author_user_id", sa.Uuid(), nullable=True),
        sa.Column("author_business_id", sa.Uuid(), nullable=True),
        sa.Column("sender_code", sa.String(12), nullable=True),
        sa.Column("admin_id", sa.Uuid(), nullable=True),
        sa.Column("relayed_from_id", sa.Uuid(), nullable=True),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("review_note", sa.String(500), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("origin IN ('own', 'relay', 'desk', 'system')", name="ck_chat_messages_origin"),
        sa.CheckConstraint("status IN ('delivered', 'held', 'rejected')", name="ck_chat_messages_status"),
        sa.CheckConstraint("status <> 'rejected' OR review_note IS NOT NULL", name="ck_chat_messages_rejected_has_note"),
        sa.CheckConstraint("(origin = 'relay') = (relayed_from_id IS NOT NULL)", name="ck_chat_messages_relay_source"),
        sa.ForeignKeyConstraint(["thread_id"], ["chat_threads.id"], ondelete="CASCADE", name="fk_chat_messages_thread_id"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL", name="fk_chat_messages_author_user_id"),
        sa.ForeignKeyConstraint(
            ["author_business_id"], ["businesses.id"], ondelete="SET NULL", name="fk_chat_messages_author_business_id"
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["admin_users.id"], ondelete="SET NULL", name="fk_chat_messages_admin_id"),
        sa.ForeignKeyConstraint(
            ["relayed_from_id"], ["chat_messages.id"], ondelete="CASCADE", name="fk_chat_messages_relayed_from_id"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_thread_time", "chat_messages", ["thread_id", "created_at"])
    op.create_index("ix_chat_messages_held", "chat_messages", ["status", "created_at"])
    op.create_table(
        "leak_strikes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("deal_id", sa.Uuid(), nullable=True),
        sa.Column("reasons", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE", name="fk_leak_strikes_business_id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL", name="fk_leak_strikes_user_id"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="SET NULL", name="fk_leak_strikes_deal_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_leak_strikes_business_time", "leak_strikes", ["business_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_leak_strikes_business_time", table_name="leak_strikes")
    op.drop_table("leak_strikes")
    op.drop_index("ix_chat_messages_held", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_time", table_name="chat_messages")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    with op.batch_alter_table("deals") as batch:
        batch.drop_constraint("fk_deals_chosen_offer_id", type_="foreignkey")
        batch.drop_column("chosen_offer_id")
    op.execute("UPDATE offers SET status = 'expired' WHERE status = 'not_chosen'")
    with op.batch_alter_table("offers") as batch:
        batch.drop_constraint("ck_offers_status", type_="check")
        batch.create_check_constraint("ck_offers_status", OLD_OFFER)
    with op.batch_alter_table("businesses") as batch:
        batch.drop_constraint("ck_businesses_suspension_has_reason", type_="check")
        batch.drop_column("suspended_reason")
        batch.drop_column("suspended_at")
