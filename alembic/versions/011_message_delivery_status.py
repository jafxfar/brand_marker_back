"""add message delivery status fields

Revision ID: 011
Revises: 010
Create Date: 2026-08-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    message_delivery_status = sa.Enum(
        "sent",
        "delivered",
        "viewed",
        name="message_delivery_status",
    )
    message_delivery_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "messages",
        sa.Column(
            "status",
            message_delivery_status,
            nullable=False,
            server_default="sent",
        ),
    )
    op.add_column(
        "messages",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "viewed_at")
    op.drop_column("messages", "delivered_at")
    op.drop_column("messages", "status")
    sa.Enum(name="message_delivery_status").drop(op.get_bind(), checkfirst=True)
