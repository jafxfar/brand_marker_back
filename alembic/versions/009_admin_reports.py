"""migrate report reasons to spam/fraud/counterfeit/abuse/other

Revision ID: 009
Revises: 008
Create Date: 2026-08-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REASON_TYPES = (
    "catalog_item_report_reason",
    "rfq_report_reason",
    "proposal_report_reason",
)

TABLES = (
    ("catalog_item_reports", "catalog_item_report_reason"),
    ("rfq_reports", "rfq_report_reason"),
    ("proposal_reports", "proposal_report_reason"),
)

NEW_VALUES = ("spam", "fraud", "counterfeit", "abuse", "other")
OLD_VALUES = ("misleading", "prohibited", "spam", "copyright", "other")


def _migrate_reason_enum(type_name: str, table_name: str) -> None:
    new_type = f"{type_name}_new"
    values_sql = ", ".join(f"'{value}'" for value in NEW_VALUES)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = '{type_name}'
            ) AND EXISTS (
                SELECT 1
                FROM pg_enum
                JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                WHERE pg_type.typname = '{type_name}'
                  AND pg_enum.enumlabel = 'misleading'
            ) THEN
                CREATE TYPE {new_type} AS ENUM ({values_sql});
                ALTER TABLE {table_name}
                    ALTER COLUMN reason TYPE {new_type}
                    USING (
                        CASE reason::text
                            WHEN 'spam' THEN 'spam'
                            WHEN 'prohibited' THEN 'fraud'
                            WHEN 'copyright' THEN 'counterfeit'
                            WHEN 'misleading' THEN 'abuse'
                            WHEN 'other' THEN 'other'
                            WHEN 'fraud' THEN 'fraud'
                            WHEN 'counterfeit' THEN 'counterfeit'
                            WHEN 'abuse' THEN 'abuse'
                            ELSE 'other'
                        END::{new_type}
                    );
                DROP TYPE {type_name};
                ALTER TYPE {new_type} RENAME TO {type_name};
            ELSIF NOT EXISTS (
                SELECT 1 FROM pg_type WHERE typname = '{type_name}'
            ) THEN
                CREATE TYPE {type_name} AS ENUM ({values_sql});
            END IF;
        END
        $$;
        """
    )


def _revert_reason_enum(type_name: str, table_name: str) -> None:
    old_type = f"{type_name}_old"
    values_sql = ", ".join(f"'{value}'" for value in OLD_VALUES)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_type WHERE typname = '{type_name}'
            ) AND EXISTS (
                SELECT 1
                FROM pg_enum
                JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
                WHERE pg_type.typname = '{type_name}'
                  AND pg_enum.enumlabel = 'fraud'
            ) THEN
                CREATE TYPE {old_type} AS ENUM ({values_sql});
                ALTER TABLE {table_name}
                    ALTER COLUMN reason TYPE {old_type}
                    USING (
                        CASE reason::text
                            WHEN 'spam' THEN 'spam'
                            WHEN 'fraud' THEN 'prohibited'
                            WHEN 'counterfeit' THEN 'copyright'
                            WHEN 'abuse' THEN 'misleading'
                            WHEN 'other' THEN 'other'
                            ELSE 'other'
                        END::{old_type}
                    );
                DROP TYPE {type_name};
                ALTER TYPE {old_type} RENAME TO {type_name};
            END IF;
        END
        $$;
        """
    )


def upgrade() -> None:
    for table_name, type_name in TABLES:
        _migrate_reason_enum(type_name, table_name)


def downgrade() -> None:
    for table_name, type_name in TABLES:
        _revert_reason_enum(type_name, table_name)
