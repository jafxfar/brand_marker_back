"""admin disputes entity

Revision ID: 007
Revises: 006
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for type_name, values in (
        (
            "dispute_status",
            ("open", "under_review", "resolved", "appealed"),
        ),
        (
            "dispute_resolution",
            ("release_funds", "refund_buyer", "partial_refund", "close_case"),
        ),
    ):
        values_sql = ", ".join(f"'{value}'" for value in values)
        op.execute(
            f"""
            DO $$
            BEGIN
                CREATE TYPE {type_name} AS ENUM ({values_sql});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END
            $$;
            """
        )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS disputes (
            id SERIAL PRIMARY KEY,
            contract_id INTEGER NOT NULL REFERENCES contracts(id),
            status dispute_status NOT NULL DEFAULT 'open',
            opened_by_actor_id INTEGER REFERENCES actors(id),
            buyer_statement TEXT,
            supplier_statement TEXT,
            resolution dispute_resolution,
            resolution_note TEXT,
            partial_buyer_amount DOUBLE PRECISION,
            resolved_at TIMESTAMPTZ,
            resolved_by_id INTEGER REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_disputes_contract_id ON disputes (contract_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_disputes_opened_by_actor_id
        ON disputes (opened_by_actor_id);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_dispute_active_contract
        ON disputes (contract_id)
        WHERE status IN ('open', 'under_review', 'appealed');
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS dispute_evidence (
            id SERIAL PRIMARY KEY,
            dispute_id INTEGER NOT NULL REFERENCES disputes(id),
            uploaded_by_actor_id INTEGER NOT NULL REFERENCES actors(id),
            file_name VARCHAR(255) NOT NULL,
            file_url VARCHAR(500) NOT NULL,
            file_type VARCHAR(100) NOT NULL,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_dispute_evidence_dispute_id
        ON dispute_evidence (dispute_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_dispute_evidence_uploaded_by_actor_id
        ON dispute_evidence (uploaded_by_actor_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dispute_evidence;")
    op.execute("DROP TABLE IF EXISTS disputes;")
    op.execute("DROP TYPE IF EXISTS dispute_resolution;")
    op.execute("DROP TYPE IF EXISTS dispute_status;")
