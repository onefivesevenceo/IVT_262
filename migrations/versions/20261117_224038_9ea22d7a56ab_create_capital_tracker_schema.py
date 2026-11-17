"""create capital tracker schema

Revision ID: 9ea22d7a56ab
Revises:
Create Date: 2026-11-17 22:40:38.556780

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ea22d7a56ab"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет изменение схемы базы данных."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(username)) > 0", name=op.f("ck_users_username_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum(
                "DEBIT",
                "CREDIT",
                "CASH",
                "SAVINGS",
                name="account_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("balance", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "account_type IN ('DEBIT', 'CREDIT', 'CASH', 'SAVINGS')",
            name=op.f("ck_accounts_account_type"),
        ),
        sa.CheckConstraint(
            "balance > -10000000000000000 AND balance < 10000000000000000",
            name=op.f("ck_accounts_balance_finite"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_accounts_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_accounts_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("user_id", "id", name=op.f("uq_accounts_user_id")),
    )
    op.create_index(op.f("ix_accounts_user_id"), "accounts", ["user_id"], unique=False)
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(
                "INCOME",
                "EXPENSE",
                name="category_direction",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('INCOME', 'EXPENSE')",
            name=op.f("ck_categories_category_direction"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_categories_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_categories_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("user_id", "id", name=op.f("uq_categories_user_id")),
    )
    op.create_index(
        op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False
    )
    op.create_table(
        "budget_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "limit_amount > 0 AND limit_amount < 10000000000000000",
            name=op.f("ck_budget_limits_limit_positive_finite"),
        ),
        sa.CheckConstraint(
            "month BETWEEN 1 AND 12", name=op.f("ck_budget_limits_month_range")
        ),
        sa.CheckConstraint(
            "year BETWEEN 1970 AND 2100", name=op.f("ck_budget_limits_year_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_budget_limits_owner_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_budget_limits_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_limits")),
        sa.UniqueConstraint(
            "user_id", "category_id", "month", "year", name="uq_budget_period"
        ),
    )
    op.create_index(
        op.f("ix_budget_limits_category_id"),
        "budget_limits",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_budget_limits_user_id"), "budget_limits", ["user_id"], unique=False
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "INCOME",
                "EXPENSE",
                "TRANSFER",
                name="transaction_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("to_account_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND to_account_id IS NOT NULL "
            "AND to_account_id <> account_id AND category_id IS NULL) OR "
            "(transaction_type IN ('INCOME', 'EXPENSE') "
            "AND category_id IS NOT NULL AND to_account_id IS NULL)",
            name=op.f("ck_transactions_operation_fields"),
        ),
        sa.CheckConstraint(
            "transaction_type IN ('INCOME', 'EXPENSE', 'TRANSFER')",
            name=op.f("ck_transactions_transaction_type"),
        ),
        sa.CheckConstraint(
            "amount > 0 AND amount < 10000000000000000",
            name=op.f("ck_transactions_amount_positive_finite"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_transactions_owner_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "to_account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_target",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_transactions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        op.f("ix_transactions_account_id"), "transactions", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_category_id"),
        "transactions",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_to_account_id"),
        "transactions",
        ["to_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Возвращает предыдущее состояние схемы базы данных."""
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_to_account_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_budget_limits_user_id"), table_name="budget_limits")
    op.drop_index(op.f("ix_budget_limits_category_id"), table_name="budget_limits")
    op.drop_table("budget_limits")
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_index(op.f("ix_accounts_user_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("users")
