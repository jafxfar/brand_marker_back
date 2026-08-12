"""drop marketplace orders tables

Revision ID: 012
Revises: 011
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS order_offers CASCADE")
    op.execute("DROP TABLE IF EXISTS marketplace_orders CASCADE")
    op.execute("DROP TYPE IF EXISTS order_offer_status")
    op.execute("DROP TYPE IF EXISTS order_status")
    op.execute("DROP TYPE IF EXISTS order_kind")


def downgrade() -> None:
    order_kind = sa.Enum("product", "service", name="order_kind")
    order_status = sa.Enum(
        "published",
        "in_progress",
        "completed",
        "cancelled",
        "disputed",
        name="order_status",
    )
    order_offer_status = sa.Enum(
        "pending",
        "accepted",
        "rejected",
        "withdrawn",
        name="order_offer_status",
    )

    order_kind.create(op.get_bind(), checkfirst=True)
    order_status.create(op.get_bind(), checkfirst=True)
    order_offer_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "marketplace_orders",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("buyer_actor_id", sa.Integer(), sa.ForeignKey("actors.id"), nullable=False),
        sa.Column("kind", order_kind, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("categories.id"), nullable=True),
        sa.Column("category_label", sa.String(length=255), nullable=True),
        sa.Column("budget", sa.Float(), nullable=False, server_default="0"),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("needs_delivery", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", order_status, nullable=False, server_default="published"),
        sa.Column("accepted_offer_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_marketplace_orders_buyer_actor_id", "marketplace_orders", ["buyer_actor_id"])

    op.create_table(
        "order_offers",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "order_id",
            sa.String(length=36),
            sa.ForeignKey("marketplace_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("supplier_actor_id", sa.Integer(), sa.ForeignKey("actors.id"), nullable=False),
        sa.Column("supplier_name", sa.String(length=255), nullable=True),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("delivery_days", sa.Integer(), nullable=True),
        sa.Column("status", order_offer_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_order_offers_order_id", "order_offers", ["order_id"])
    op.create_index("ix_order_offers_supplier_actor_id", "order_offers", ["supplier_actor_id"])
