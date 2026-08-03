"""catalog moderation statuses and reports

Revision ID: 005
Revises: 004
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("pending_review", "changes_requested", "hidden", "deleted"):
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum
                    JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                    WHERE pg_type.typname = 'item_status'
                      AND pg_enum.enumlabel = '{value}'
                ) THEN
                    ALTER TYPE item_status ADD VALUE '{value}';
                END IF;
            END
            $$;
            """
        )

    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE catalog_item_report_reason AS ENUM (
                'misleading',
                'prohibited',
                'spam',
                'copyright',
                'other'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE catalog_item_report_status AS ENUM (
                'open',
                'resolved',
                'dismissed'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS catalog_item_reports (
            id SERIAL PRIMARY KEY,
            item_id INTEGER NOT NULL REFERENCES catalog_items(id),
            reporter_user_id INTEGER NOT NULL REFERENCES users(id),
            reason catalog_item_report_reason NOT NULL,
            details TEXT,
            status catalog_item_report_status NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            resolved_at TIMESTAMPTZ,
            resolved_by_id INTEGER REFERENCES users(id)
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_catalog_item_reports_item_id
        ON catalog_item_reports (item_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_catalog_item_reports_reporter_user_id
        ON catalog_item_reports (reporter_user_id);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_catalog_item_reports_status
        ON catalog_item_reports (status);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_catalog_item_reports_created_at
        ON catalog_item_reports (created_at);
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_catalog_item_open_report
        ON catalog_item_reports (item_id, reporter_user_id)
        WHERE status = 'open';
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_catalog_item_open_report")
    op.execute("DROP INDEX IF EXISTS ix_catalog_item_reports_created_at")
    op.execute("DROP INDEX IF EXISTS ix_catalog_item_reports_status")
    op.execute("DROP INDEX IF EXISTS ix_catalog_item_reports_reporter_user_id")
    op.execute("DROP INDEX IF EXISTS ix_catalog_item_reports_item_id")
    op.execute("DROP TABLE IF EXISTS catalog_item_reports")
    op.execute("DROP TYPE IF EXISTS catalog_item_report_status")
    op.execute("DROP TYPE IF EXISTS catalog_item_report_reason")
