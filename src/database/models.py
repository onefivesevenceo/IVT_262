"""Текущее состояние схемы БД, создаваемой миграциями Alembic."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base as Base
from src.models.account import AccountType
from src.models.category import CategoryDirection
from src.models.transaction import TransactionType


class UserORM(Base):
    """Пользователь, которому принадлежат финансовые данные."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    accounts: Mapped[list["AccountORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    categories: Mapped[list["CategoryORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    transactions: Mapped[list["TransactionORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    budget_limits: Mapped[list["BudgetLimitORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )

    __table_args__ = (
        CheckConstraint("length(trim(username)) > 0", name="username_not_blank"),
    )


class AccountORM(Base):
    """Счет с точным остатком и логическим архивированием."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType, native_enum=False, create_constraint=True, name="account_type"
        )
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    user: Mapped[UserORM] = relationship(back_populates="accounts")
    transactions: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        foreign_keys="TransactionORM.account_id",
        back_populates="account",
        passive_deletes="all",
    )
    incoming_transfers: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.to_account_id",
        foreign_keys="TransactionORM.to_account_id",
        back_populates="to_account",
        passive_deletes="all",
    )
    categories: Mapped[list["CategoryORM"]] = relationship(
        secondary="transactions",
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        secondaryjoin="CategoryORM.id == TransactionORM.category_id",
        back_populates="accounts",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "balance > -10000000000000000 AND balance < 10000000000000000",
            name="balance_finite",
        ),
    )


class CategoryORM(Base):
    """Категория операций, принадлежащая одному пользователю."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    direction: Mapped[CategoryDirection] = mapped_column(
        Enum(
            CategoryDirection,
            native_enum=False,
            create_constraint=True,
            name="category_direction",
        )
    )

    user: Mapped[UserORM] = relationship(back_populates="categories")
    transactions: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        foreign_keys="TransactionORM.category_id",
        back_populates="category",
        passive_deletes="all",
    )
    budget_limits: Mapped[list["BudgetLimitORM"]] = relationship(
        primaryjoin="CategoryORM.id == BudgetLimitORM.category_id",
        foreign_keys="BudgetLimitORM.category_id",
        back_populates="category",
        passive_deletes="all",
    )
    accounts: Mapped[list[AccountORM]] = relationship(
        secondary="transactions",
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        secondaryjoin="AccountORM.id == TransactionORM.account_id",
        back_populates="categories",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )


class TransactionORM(Base):
    """Операция и объект связи счета с категорией, включая сумму и дату."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            native_enum=False,
            create_constraint=True,
            name="transaction_type",
        )
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(index=True)
    category_id: Mapped[int | None] = mapped_column(index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    to_account_id: Mapped[int | None] = mapped_column(index=True)

    user: Mapped[UserORM] = relationship(back_populates="transactions")
    account: Mapped[AccountORM] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        foreign_keys=[account_id],
        back_populates="transactions",
    )
    to_account: Mapped[AccountORM | None] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.to_account_id",
        foreign_keys=[to_account_id],
        back_populates="incoming_transfers",
    )
    category: Mapped[CategoryORM | None] = relationship(
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        foreign_keys=[category_id],
        back_populates="transactions",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "to_account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_transactions_owner_category",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "amount > 0 AND amount < 10000000000000000", name="amount_positive_finite"
        ),
        CheckConstraint(
            "(transaction_type = 'TRANSFER' AND to_account_id IS NOT NULL "
            "AND to_account_id <> account_id AND category_id IS NULL) OR "
            "(transaction_type IN ('INCOME', 'EXPENSE') "
            "AND category_id IS NOT NULL AND to_account_id IS NULL)",
            name="operation_fields",
        ),
    )


class BudgetLimitORM(Base):
    """Единственный лимит категории пользователя на календарный месяц."""

    __tablename__ = "budget_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    user: Mapped[UserORM] = relationship(back_populates="budget_limits")
    category: Mapped[CategoryORM] = relationship(
        primaryjoin="CategoryORM.id == BudgetLimitORM.category_id",
        foreign_keys=[category_id],
        back_populates="budget_limits",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_budget_limits_owner_category",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "user_id", "category_id", "month", "year", name="uq_budget_period"
        ),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("year BETWEEN 1970 AND 2100", name="year_range"),
        CheckConstraint(
            "limit_amount > 0 AND limit_amount < 10000000000000000",
            name="limit_positive_finite",
        ),
    )
