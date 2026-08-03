"""admin company statuses

Revision ID: 004
Revises: 003
Create Date: 2026-08-03
"""

from typing import Sequence, Union

from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
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
                WHERE pg_type.typname = 'verification_status'
                  AND pg_enum.enumlabel = 'needs_documents'
            ) THEN
                ALTER TYPE verification_status ADD VALUE 'needs_documents';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE company_operational_status AS ENUM (
                'active',
                'blocked',
                'deactivated'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )
    op.execute(
        """
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS operational_status company_operational_status
        NOT NULL DEFAULT 'active';
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_companies_operational_status
        ON companies (operational_status);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_companies_operational_status")
    op.execute("ALTER TABLE companies DROP COLUMN IF EXISTS operational_status")
    op.execute("DROP TYPE IF EXISTS company_operational_status")
