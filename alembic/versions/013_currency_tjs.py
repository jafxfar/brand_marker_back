"""add TJS currency and migrate defaults from RUB

Revision ID: 013
Revises: 012
Create Date: 2026-08-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires new enum labels to be committed before use.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE currency ADD VALUE IF NOT EXISTS 'TJS'")
        op.execute("ALTER TYPE contract_currency ADD VALUE IF NOT EXISTS 'TJS'")

    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'invoices' AND column_name = 'currency'
          ) THEN
            ALTER TABLE invoices ALTER COLUMN currency SET DEFAULT 'TJS';
            UPDATE invoices SET currency = 'TJS' WHERE currency = 'RUB';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'ledger_entries' AND column_name = 'currency'
          ) THEN
            ALTER TABLE ledger_entries ALTER COLUMN currency SET DEFAULT 'TJS';
            UPDATE ledger_entries SET currency = 'TJS' WHERE currency = 'RUB';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'withdrawals' AND column_name = 'currency'
          ) THEN
            ALTER TABLE withdrawals ALTER COLUMN currency SET DEFAULT 'TJS';
            UPDATE withdrawals SET currency = 'TJS' WHERE currency = 'RUB';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'catalog_items' AND column_name = 'currency'
          ) THEN
            ALTER TABLE catalog_items ALTER COLUMN currency SET DEFAULT 'TJS';
            UPDATE catalog_items SET currency = 'TJS' WHERE currency = 'RUB';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'rfqs' AND column_name = 'currency'
          ) THEN
            UPDATE rfqs SET currency = 'TJS' WHERE currency = 'RUB';
          END IF;

          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currency') THEN
            UPDATE proposals SET currency = 'TJS' WHERE currency::text = 'RUB';
          END IF;

          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_currency') THEN
            UPDATE contracts SET currency = 'TJS' WHERE currency::text = 'RUB';
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'invoices' AND column_name = 'currency'
          ) THEN
            ALTER TABLE invoices ALTER COLUMN currency SET DEFAULT 'RUB';
            UPDATE invoices SET currency = 'RUB' WHERE currency = 'TJS';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'ledger_entries' AND column_name = 'currency'
          ) THEN
            ALTER TABLE ledger_entries ALTER COLUMN currency SET DEFAULT 'RUB';
            UPDATE ledger_entries SET currency = 'RUB' WHERE currency = 'TJS';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'withdrawals' AND column_name = 'currency'
          ) THEN
            ALTER TABLE withdrawals ALTER COLUMN currency SET DEFAULT 'RUB';
            UPDATE withdrawals SET currency = 'RUB' WHERE currency = 'TJS';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'catalog_items' AND column_name = 'currency'
          ) THEN
            ALTER TABLE catalog_items ALTER COLUMN currency SET DEFAULT 'RUB';
            UPDATE catalog_items SET currency = 'RUB' WHERE currency = 'TJS';
          END IF;

          IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'rfqs' AND column_name = 'currency'
          ) THEN
            UPDATE rfqs SET currency = 'RUB' WHERE currency = 'TJS';
          END IF;

          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'currency') THEN
            UPDATE proposals SET currency = 'RUB' WHERE currency::text = 'TJS';
          END IF;

          IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'contract_currency') THEN
            UPDATE contracts SET currency = 'RUB' WHERE currency::text = 'TJS';
          END IF;
        END $$;
        """
    )
