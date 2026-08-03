"""admin rfq/proposal reports and archived status

Revision ID: 006
Revises: 005
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_enum
                JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                WHERE pg_type.typname = 'rfq_status'
                  AND pg_enum.enumlabel = 'archived'
            ) THEN
                ALTER TYPE rfq_status ADD VALUE 'archived';
            END IF;
        END
        $$;
        """
    )

    for type_name, values in (
        (
            "rfq_report_reason",
            ("misleading", "prohibited", "spam", "copyright", "other"),
        ),
        (
            "proposal_report_reason",
            ("misleading", "prohibited", "spam", "copyright", "other"),
        ),
        (
            "rfq_report_status",
            ("open", "resolved", "dismissed"),
        ),
        (
            "proposal_report_status",
            ("open", "resolved", "dismissed"),
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
        CREATE TABLE IF NOT EXISTS rfq_reports (
            id SERIAL PRIMARY KEY,
            rfq_id VARCHAR(36) NOT NULL REFERENCES rfqs(id),
            reporter_user_id INTEGER NOT NULL REFERENCES users(id),
            reason rfq_report_reason NOT NULL,
            details TEXT,
            status rfq_report_status NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolved_by_id INTEGER REFERENCES users(id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rfq_reports_rfq_id ON rfq_reports (rfq_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rfq_reports_reporter_user_id
        ON rfq_reports (reporter_user_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_rfq_reports_status ON rfq_reports (status);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_rfq_open_report
        ON rfq_reports (rfq_id, reporter_user_id)
        WHERE status = 'open';
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS proposal_reports (
            id SERIAL PRIMARY KEY,
            proposal_id INTEGER NOT NULL REFERENCES proposals(id),
            reporter_user_id INTEGER NOT NULL REFERENCES users(id),
            reason proposal_report_reason NOT NULL,
            details TEXT,
            status proposal_report_status NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolved_by_id INTEGER REFERENCES users(id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_proposal_reports_proposal_id
        ON proposal_reports (proposal_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_proposal_reports_reporter_user_id
        ON proposal_reports (reporter_user_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_proposal_reports_status
        ON proposal_reports (status);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_proposal_open_report
        ON proposal_reports (proposal_id, reporter_user_id)
        WHERE status = 'open';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_proposal_open_report")
    op.execute("DROP INDEX IF EXISTS ix_proposal_reports_status")
    op.execute("DROP INDEX IF EXISTS ix_proposal_reports_reporter_user_id")
    op.execute("DROP INDEX IF EXISTS ix_proposal_reports_proposal_id")
    op.execute("DROP TABLE IF EXISTS proposal_reports")

    op.execute("DROP INDEX IF EXISTS uq_rfq_open_report")
    op.execute("DROP INDEX IF EXISTS ix_rfq_reports_status")
    op.execute("DROP INDEX IF EXISTS ix_rfq_reports_reporter_user_id")
    op.execute("DROP INDEX IF EXISTS ix_rfq_reports_rfq_id")
    op.execute("DROP TABLE IF EXISTS rfq_reports")

    op.execute("DROP TYPE IF EXISTS proposal_report_status")
    op.execute("DROP TYPE IF EXISTS proposal_report_reason")
    op.execute("DROP TYPE IF EXISTS rfq_report_status")
    op.execute("DROP TYPE IF EXISTS rfq_report_reason")
