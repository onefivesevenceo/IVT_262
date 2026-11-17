"""Реализации существующих ABC-контрактов поверх переданной сессии."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import (
    AccountMapper,
    BudgetLimitMapper,
    CategoryMapper,
    TransactionMapper,
)
from src.database.models import (
    AccountORM,
    BudgetLimitORM,
    CategoryORM,
    TransactionORM,
)
from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction
from src.repositories.account import AccountRepository
from src.repositories.budget import BudgetRepository
from src.repositories.category import CategoryRepository
from src.repositories.transaction import TransactionRepository


class SQLAlchemyAccountRepository(AccountRepository):
    """Хранилище счетов без самостоятельной фиксации транзакций."""

    def __init__(self, session: Session) -> None:
        """Принимает общую сессию текущей прикладной операции."""
        self._session = session

    def add(self, account: Account) -> Account:
        """Сохраняет счет и возвращает датакласс с присвоенным ID."""
        row = AccountMapper.to_orm(account)
        self._session.add(row)
        self._session.flush()
        return AccountMapper.to_domain(row)

    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет, включая архивный для сохранения истории."""
        row = self._session.get(AccountORM, account_id)
        return AccountMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает активные счета владельца в порядке создания."""
        query = (
            select(AccountORM)
            .where(AccountORM.user_id == user_id, AccountORM.is_archived.is_(False))
            .order_by(AccountORM.id)
        )
        return [AccountMapper.to_domain(row) for row in self._session.scalars(query)]

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Меняет остаток без commit; отсутствие счета является ошибкой."""
        row = self._session.get(AccountORM, account_id)
        if row is None:
            msg = "Счет не найден для обновления баланса."
            raise ValueError(msg)
        row.balance = new_balance
        self._session.flush()

    def archive(self, account_id: int) -> None:
        """Архивирует счет, сохраняя связанные операции."""
        row = self._session.get(AccountORM, account_id)
        if row is None:
            msg = "Счет не найден для архивации."
            raise ValueError(msg)
        row.is_archived = True
        self._session.flush()


class SQLAlchemyCategoryRepository(CategoryRepository):
    """Хранилище категорий с преобразованием записей в датаклассы."""

    def __init__(self, session: Session) -> None:
        """Принимает сессию от вызывающего кода."""
        self._session = session

    def add(self, category: Category) -> Category:
        """Сохраняет категорию без фиксации внешней транзакции."""
        row = CategoryMapper.to_orm(category)
        self._session.add(row)
        self._session.flush()
        return CategoryMapper.to_domain(row)

    def get_by_id(self, category_id: int) -> Category | None:
        """Находит категорию по первичному ключу."""
        row = self._session.get(CategoryORM, category_id)
        return CategoryMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает категории владельца в порядке создания."""
        query = (
            select(CategoryORM)
            .where(CategoryORM.user_id == user_id)
            .order_by(CategoryORM.id)
        )
        return [CategoryMapper.to_domain(row) for row in self._session.scalars(query)]


class SQLAlchemyTransactionRepository(TransactionRepository):
    """Хранилище операций в той же транзакции, что и изменения балансов."""

    def __init__(self, session: Session) -> None:
        """Принимает общую сессию счетов и журнала операций."""
        self._session = session

    def add(self, transaction: Transaction) -> Transaction:
        """Добавляет запись журнала и получает ее ID через flush."""
        row = TransactionMapper.to_orm(transaction)
        self._session.add(row)
        self._session.flush()
        return TransactionMapper.to_domain(row)

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает операцию либо None без передачи ORM наружу."""
        row = self._session.get(TransactionORM, transaction_id)
        return TransactionMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает журнал владельца в прежнем порядке добавления."""
        query = (
            select(TransactionORM)
            .where(TransactionORM.user_id == user_id)
            .order_by(TransactionORM.id)
        )
        return [
            TransactionMapper.to_domain(row) for row in self._session.scalars(query)
        ]

    def delete(self, transaction_id: int) -> None:
        """Удаляет запись в рамках общей транзакции отката остатков."""
        row = self._session.get(TransactionORM, transaction_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()


class SQLAlchemyBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов с заменой суммы без смены ID."""

    def __init__(self, session: Session) -> None:
        """Принимает сессию текущей операции."""
        self._session = session

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Добавляет лимит или меняет существующий по ключу периода."""
        row = self._find_row(
            budget.user_id, budget.category_id, budget.month, budget.year
        )
        if row is None:
            row = BudgetLimitMapper.to_orm(budget)
            self._session.add(row)
        else:
            row.limit_amount = budget.limit_amount
        self._session.flush()
        return BudgetLimitMapper.to_domain(row)

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит указанной категории, владельца и периода."""
        row = self._find_row(user_id, category_id, month, year)
        return BudgetLimitMapper.to_domain(row) if row is not None else None

    def _find_row(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimitORM | None:
        """Находит ORM-запись по уникальному ключу бюджетного периода."""
        return self._session.scalar(
            select(BudgetLimitORM).where(
                BudgetLimitORM.user_id == user_id,
                BudgetLimitORM.category_id == category_id,
                BudgetLimitORM.month == month,
                BudgetLimitORM.year == year,
            )
        )
