from decimal import Decimal
from typing import Protocol

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction


class AccountRepositoryProtocol(Protocol):
    """Контракт взаимодействия с хранилищем финансовых счетов."""

    def add(self, account: Account) -> Account:
        """Добавляет счет в хранилище."""
        ...

    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет по его идентификатору."""
        ...

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает все счета пользователя."""
        ...

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Обновляет текущий остаток счета."""
        ...

    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный."""
        ...


class TransactionRepositoryProtocol(Protocol):
    """Контракт взаимодействия с журналом транзакций."""

    def add(self, transaction: Transaction) -> Transaction:
        """Сохраняет новую транзакцию."""
        ...

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по идентификатору."""
        ...

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает все операции конкретного пользователя."""
        ...

    def delete(self, transaction_id: int) -> None:
        """Удаляет операцию из журнала."""
        ...


class BudgetRepositoryProtocol(Protocol):
    """Контракт управления лимитами бюджетов."""

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает или обновляет лимит."""
        ...

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит на указанный период."""
        ...


class CategoryRepositoryProtocol(Protocol):
    """Контракт управления справочником категорий."""

    def add(self, category: Category) -> Category:
        """Добавляет категорию."""
        ...

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""
        ...

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает список категорий пользователя."""
        ...
