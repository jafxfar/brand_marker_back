"""add proposal_messages table

Revision ID: 014
Revises: 013
Create Date: 2026-08-15
"""

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_messages (
            id SERIAL PRIMARY KEY,
            proposal_id INTEGER NOT NULL REFERENCES proposals (id),
            sender_id INTEGER NOT NULL REFERENCES users (id),
            text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proposal_messages_proposal_id "
        "ON proposal_messages (proposal_id);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_proposal_messages_sender_id "
        "ON proposal_messages (sender_id);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_proposal_messages_sender_id;")
    op.execute("DROP INDEX IF EXISTS ix_proposal_messages_proposal_id;")
    op.execute("DROP TABLE IF EXISTS proposal_messages;")
