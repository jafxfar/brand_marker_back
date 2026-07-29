"""actors table and FK migration

Revision ID: 002
Revises: 001
Create Date: 2026-06-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "actors" in tables:
        invited_cols = (
            {c["name"] for c in inspector.get_columns("rfq_invited_suppliers")}
            if "rfq_invited_suppliers" in tables
            else set()
        )
        rfqs_fk = next(
            (
                fk
                for fk in inspector.get_foreign_keys("rfqs")
                if "actor_id" in fk.get("constrained_columns", [])
            ),
            None,
        ) if "rfqs" in tables else None
        if "supplier_actor_id" in invited_cols or (
            rfqs_fk and rfqs_fk.get("referred_table") == "actors"
        ):
            return

    for enum_sql in (
        "CREATE TYPE actor_kind AS ENUM ('individual', 'company')",
        "CREATE TYPE actor_side AS ENUM ('buyer', 'supplier')",
        "CREATE TYPE trust_level AS ENUM ('basic', 'standard', 'verified')",
    ):
        op.execute(
            sa.text(
                f"""
                DO $$ BEGIN
                    {enum_sql};
                EXCEPTION
                    WHEN duplicate_object THEN NULL;
                END $$;
                """
            )
        )

    actor_kind = postgresql.ENUM("individual", "company", name="actor_kind", create_type=False)
    actor_side = postgresql.ENUM("buyer", "supplier", name="actor_side", create_type=False)
    trust_level = postgresql.ENUM("basic", "standard", "verified", name="trust_level", create_type=False)

    if "actors" not in tables:
        op.create_table(
            "actors",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("kind", actor_kind, nullable=False),
            sa.Column("side", actor_side, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("trust_level", trust_level, nullable=False, server_default="basic"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
        op.create_index("ix_actors_user_id", "actors", ["user_id"])
        op.create_index("ix_actors_company_id", "actors", ["company_id"])
        op.create_index(
            "uq_actor_individual_user_side",
            "actors",
            ["user_id", "side"],
            unique=True,
            postgresql_where=sa.text("kind = 'individual'"),
        )
        op.create_index(
            "uq_actor_company_side",
            "actors",
            ["company_id", "side"],
            unique=True,
            postgresql_where=sa.text("kind = 'company'"),
        )

    conn = op.get_bind()
    companies = conn.execute(
        sa.text(
            "SELECT id, title, actor_type::text AS actor_type, "
            "verification_status::text AS vstatus FROM companies"
        )
    ).fetchall()

    company_actor_map: dict[tuple[int, str], int] = {}
    existing_actors = conn.execute(
        sa.text(
            "SELECT id, company_id, side::text AS side "
            "FROM actors WHERE kind = 'company' AND company_id IS NOT NULL"
        )
    ).fetchall()
    for row in existing_actors:
        company_actor_map[(row.company_id, row.side)] = row.id

    for row in companies:
        if (row.id, row.actor_type) in company_actor_map:
            continue
        trust = "verified" if row.vstatus == "verified" else "standard"
        result = conn.execute(
            sa.text(
                "INSERT INTO actors (kind, side, user_id, company_id, display_name, "
                "trust_level, is_active) VALUES ('company', :side, NULL, :company_id, "
                ":title, :trust, true) RETURNING id"
            ),
            {"side": row.actor_type, "company_id": row.id, "title": row.title, "trust": trust},
        )
        actor_id = result.scalar_one()
        company_actor_map[(row.id, row.actor_type)] = actor_id

    def remap_fk(table: str, column: str, side: str | None = None) -> None:
        if table not in inspector.get_table_names():
            return
        rows = conn.execute(sa.text(f"SELECT id, {column} AS val FROM {table}")).fetchall()
        for row in rows:
            old_id = row.val
            if old_id is None:
                continue
            if side:
                new_id = company_actor_map.get((old_id, side))
            else:
                new_id = company_actor_map.get((old_id, "buyer")) or company_actor_map.get(
                    (old_id, "supplier")
                )
            if new_id is None:
                continue
            conn.execute(
                sa.text(f"UPDATE {table} SET {column} = :new_id WHERE id = :row_id"),
                {"new_id": new_id, "row_id": row.id},
            )

    for table, column, side in [
        ("rfqs", "actor_id", "buyer"),
        ("proposals", "supplier_actor_id", "supplier"),
        ("contracts", "buyer_actor_id", "buyer"),
        ("contracts", "supplier_actor_id", "supplier"),
        ("reviews", "reviewer_actor_id", None),
        ("reviews", "target_actor_id", None),
    ]:
        remap_fk(table, column, side)

    if "rfq_invited_suppliers" in inspector.get_table_names():
        cols = {c["name"] for c in inspector.get_columns("rfq_invited_suppliers")}
        if "supplier_id" in cols:
            remap_fk("rfq_invited_suppliers", "supplier_id", "supplier")
            op.alter_column(
                "rfq_invited_suppliers", "supplier_id", new_column_name="supplier_actor_id"
            )

    fk_targets = [
        ("rfqs", "actor_id"),
        ("proposals", "supplier_actor_id"),
        ("contracts", "buyer_actor_id"),
        ("contracts", "supplier_actor_id"),
        ("reviews", "reviewer_actor_id"),
        ("reviews", "target_actor_id"),
        ("rfq_invited_suppliers", "supplier_actor_id"),
    ]
    for table, column in fk_targets:
        if table not in inspector.get_table_names():
            continue
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            if column in fk.get("constrained_columns", []):
                op.drop_constraint(fk["name"], table, type_="foreignkey")
        op.create_foreign_key(
            f"{table}_{column}_actors_fkey", table, "actors", [column], ["id"]
        )


def downgrade() -> None:
    pass
