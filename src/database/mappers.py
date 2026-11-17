"""Явное преобразование между доменными датаклассами и ORM-моделями."""

from src.database.models import (
    AccountORM,
    BudgetLimitORM,
    CategoryORM,
    TransactionORM,
    UserORM,
)
from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction
from src.models.user import User


class UserMapper:
    """Преобразователь учетной записи без передачи ORM в доменный слой."""

    @staticmethod
    def to_domain(row: UserORM) -> User:
        """Создает неизменяемую доменную учетную запись."""
        return User(row.id, row.username, row.email, row.password_hash, row.created_at)

    @staticmethod
    def to_orm(entity: User) -> UserORM:
        """Создает ORM-запись, оставляя новый ID генератору базы."""
        row = UserORM(
            username=entity.username,
            email=entity.email,
            password_hash=entity.password_hash,
            created_at=entity.created_at,
        )
        if entity.id:
            row.id = entity.id
        return row


class AccountMapper:
    """Преобразователь счета и его точного денежного остатка."""

    @staticmethod
    def to_domain(row: AccountORM) -> Account:
        """Создает доменный счет из сохраненной записи."""
        return Account(
            row.id,
            row.user_id,
            row.name,
            row.account_type,
            row.balance,
            row.is_archived,
        )

    @staticmethod
    def to_orm(entity: Account) -> AccountORM:
        """Создает ORM-счет из доменного объекта."""
        row = AccountORM(
            user_id=entity.user_id,
            name=entity.name,
            account_type=entity.account_type,
            balance=entity.balance,
            is_archived=entity.is_archived,
        )
        if entity.id:
            row.id = entity.id
        return row


class CategoryMapper:
    """Преобразователь неизменяемой категории доходов или расходов."""

    @staticmethod
    def to_domain(row: CategoryORM) -> Category:
        """Возвращает категорию, не зависящую от сессии SQLAlchemy."""
        return Category(row.id, row.user_id, row.name, row.direction)

    @staticmethod
    def to_orm(entity: Category) -> CategoryORM:
        """Создает ORM-категорию из датакласса."""
        row = CategoryORM(
            user_id=entity.user_id, name=entity.name, direction=entity.direction
        )
        if entity.id:
            row.id = entity.id
        return row


class TransactionMapper:
    """Преобразователь финансовой операции, включая межбалансовый перевод."""

    @staticmethod
    def to_domain(row: TransactionORM) -> Transaction:
        """Создает неизменяемую доменную операцию."""
        return Transaction(
            row.id,
            row.user_id,
            row.transaction_type,
            row.amount,
            row.account_id,
            row.category_id,
            row.timestamp,
            row.to_account_id,
        )

    @staticmethod
    def to_orm(entity: Transaction) -> TransactionORM:
        """Создает запись журнала из доменной операции."""
        row = TransactionORM(
            user_id=entity.user_id,
            transaction_type=entity.transaction_type,
            amount=entity.amount,
            account_id=entity.account_id,
            category_id=entity.category_id,
            timestamp=entity.timestamp,
            to_account_id=entity.to_account_id,
        )
        if entity.id:
            row.id = entity.id
        return row


class BudgetLimitMapper:
    """Преобразователь месячного бюджетного лимита."""

    @staticmethod
    def to_domain(row: BudgetLimitORM) -> BudgetLimit:
        """Создает доменный лимит из записи базы данных."""
        return BudgetLimit(
            row.id,
            row.user_id,
            row.category_id,
            row.month,
            row.year,
            row.limit_amount,
        )

    @staticmethod
    def to_orm(entity: BudgetLimit) -> BudgetLimitORM:
        """Создает ORM-лимит, не изменяя исходный датакласс."""
        row = BudgetLimitORM(
            user_id=entity.user_id,
            category_id=entity.category_id,
            month=entity.month,
            year=entity.year,
            limit_amount=entity.limit_amount,
        )
        if entity.id:
            row.id = entity.id
        return row
