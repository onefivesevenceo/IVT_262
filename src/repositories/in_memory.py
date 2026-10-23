from decimal import Decimal

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction
from src.repositories.base import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    TransactionRepository,
)


class InMemoryAccountRepository(AccountRepository):
    """Хранилище счетов в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Account] = {}
        self._seq = 1

    def add(self, account: Account) -> Account:
        """Добавляет счет в оперативную память."""
        saved = Account(
            id=self._seq,
            user_id=account.user_id,
            name=account.name,
            account_type=account.account_type,
            balance=account.balance,
            is_archived=account.is_archived,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет по его идентификатору."""
        return self._storage.get(account_id)

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает все активные (не архивные) счета пользователя."""
        return [
            acc
            for acc in self._storage.values()
            if acc.user_id == user_id and not acc.is_archived
        ]

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Обновляет остаток счета. Если счет не найден — бросает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для обновления баланса."
            raise ValueError(msg)
        account.balance = new_balance

    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный. Если счет не найден — бросает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для архивации."
            raise ValueError(msg)
        account.is_archived = True


class InMemoryTransactionRepository(TransactionRepository):
    """Хранилище транзакций в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Transaction] = {}
        self._seq = 1

    def add(self, tx: Transaction) -> Transaction:
        """Сохраняет транзакцию в памяти."""
        saved = Transaction(
            id=self._seq,
            user_id=tx.user_id,
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            account_id=tx.account_id,
            category_id=tx.category_id,
            timestamp=tx.timestamp,
            to_account_id=tx.to_account_id,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, tx_id: int) -> Transaction | None:
        """Возвращает транзакцию по ее номеру."""
        return self._storage.get(tx_id)

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает историю операций пользователя."""
        return [
            tx
            for tx in self._storage.values()
            if tx.user_id == user_id
        ]

    def delete(self, tx_id: int) -> None:
        """Удаляет запись транзакции по первичному ключу."""
        self._storage.pop(tx_id, None)


class InMemoryBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов бюджетов в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[str, BudgetLimit] = {}
        self._seq = 1

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает или перезаписывает лимит."""
        key = f"{budget.user_id}:{budget.category_id}:{budget.month}:{budget.year}"
        saved = BudgetLimit(
            id=self._seq,
            user_id=budget.user_id,
            category_id=budget.category_id,
            month=budget.month,
            year=budget.year,
            limit_amount=budget.limit_amount,
        )
        self._storage[key] = saved
        self._seq += 1
        return saved

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит по ключу периода."""
        key = f"{user_id}:{category_id}:{month}:{year}"
        return self._storage.get(key)


class InMemoryCategoryRepository(CategoryRepository):
    """Хранилище категорий классификации операций в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Category] = {}
        self._seq = 1

    def add(self, category: Category) -> Category:
        """Добавляет категорию в память."""
        saved = Category(
            id=self._seq,
            user_id=category.user_id,
            name=category.name,
            direction=category.direction,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""
        return self._storage.get(category_id)

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает список категорий пользователя."""
        return [
            cat
            for cat in self._storage.values()
            if cat.user_id == user_id
        ]
