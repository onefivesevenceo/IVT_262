from abc import ABC, abstractmethod
from decimal import Decimal

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction


class AccountRepository(ABC):
    """Абстрактный контракт взаимодействия с хранилищем счетов."""

    @abstractmethod
    def add(self, account: Account) -> Account:
        """Добавляет счет в хранилище."""

    @abstractmethod
    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет по его идентификатору."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает все активные счета пользователя."""

    @abstractmethod
    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Обновляет текущий остаток счета."""

    @abstractmethod
    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный."""


class TransactionRepository(ABC):
    """Абстрактный контракт взаимодействия с журналом транзакций."""

    @abstractmethod
    def add(self, transaction: Transaction) -> Transaction:
        """Сохраняет новую транзакцию."""

    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по идентификатору."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает все операции конкретного пользователя."""

    @abstractmethod
    def delete(self, transaction_id: int) -> None:
        """Удаляет операцию из журнала."""


class BudgetRepository(ABC):
    """Абстрактный контракт управления лимитами бюджетов."""

    @abstractmethod
    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает или обновляет лимит."""

    @abstractmethod
    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит на указанный период."""


class CategoryRepository(ABC):
    """Абстрактный контракт управления справочником категорий."""

    @abstractmethod
    def add(self, category: Category) -> Category:
        """Добавляет категорию."""

    @abstractmethod
    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает список категорий пользователя."""
