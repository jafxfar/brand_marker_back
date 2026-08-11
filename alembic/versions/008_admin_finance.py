"""admin platform payments ledger

Revision ID: 008
Revises: 007
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for type_name, values in (
        (
            "platform_payment_type",
            (
                "platform_revenue",
                "subscription",
                "commission",
                "refund",
                "payout",
            ),
        ),
        (
            "platform_payment_status",
            (
                "pending",
                "processing",
                "paid",
                "failed",
                "refunded",
                "cancelled",
            ),
        ),
        (
            "platform_payment_gateway",
            ("manual", "mock", "stripe", "yookassa"),
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
        CREATE TABLE IF NOT EXISTS platform_payments (
            id SERIAL PRIMARY KEY,
            external_id VARCHAR(100),
            type platform_payment_type NOT NULL,
            status platform_payment_status NOT NULL DEFAULT 'pending',
            gateway platform_payment_gateway NOT NULL DEFAULT 'manual',
            amount DOUBLE PRECISION NOT NULL,
            commission DOUBLE PRECISION NOT NULL DEFAULT 0,
            currency VARCHAR(10) NOT NULL DEFAULT 'RUB',
            title VARCHAR(255) NOT NULL,
            description TEXT,
            actor_id INTEGER REFERENCES actors(id),
            invoice_id INTEGER REFERENCES supplier_invoices(id),
            withdrawal_id INTEGER REFERENCES withdrawals(id),
            contract_id INTEGER REFERENCES contracts(id),
            subscription_user_id INTEGER REFERENCES users(id),
            metadata JSONB,
            paid_at TIMESTAMPTZ,
            failed_at TIMESTAMPTZ,
            refunded_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    for index_sql in (
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_external_id ON platform_payments (external_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_actor_id ON platform_payments (actor_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_invoice_id ON platform_payments (invoice_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_withdrawal_id ON platform_payments (withdrawal_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_contract_id ON platform_payments (contract_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_subscription_user_id ON platform_payments (subscription_user_id);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_type ON platform_payments (type);",
        "CREATE INDEX IF NOT EXISTS ix_platform_payments_status ON platform_payments (status);",
    ):
        op.execute(index_sql)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS platform_payments;")
    op.execute("DROP TYPE IF EXISTS platform_payment_gateway;")
    op.execute("DROP TYPE IF EXISTS platform_payment_status;")
    op.execute("DROP TYPE IF EXISTS platform_payment_type;")
