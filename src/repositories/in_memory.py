from decimal import Decimal

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction


class InMemoryAccountRepository:
    """Хранилище счетов в оперативной памяти."""

    def __init__(self) -> None:
        self._accounts: dict[int, Account] = {}
        self._id_counter: int = 1

    def add(self, account: Account) -> Account:
        """Сохраняет счет и присваивает уникальный идентификатор."""
        assigned_id = self._id_counter
        self._id_counter += 1
        account.id = assigned_id
        self._accounts[assigned_id] = account
        return account

    def get_by_id(self, account_id: int) -> Account | None:
        """Извлекает счет по ID."""
        return self._accounts.get(account_id)

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Фильтрует счета по владельцу."""
        return [
            acc
            for acc in self._accounts.values()
            if acc.user_id == user_id and not acc.is_archived
        ]

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Мутирует остаток на счете."""
        if account := self._accounts.get(account_id):
            account.balance = new_balance

    def archive(self, account_id: int) -> None:
        """Переводит счет в архивный статус."""
        if account := self._accounts.get(account_id):
            account.is_archived = True


class InMemoryTransactionRepository:
    """Хранилище транзакций в оперативной памяти."""

    def __init__(self) -> None:
        self._transactions: dict[int, Transaction] = {}
        self._id_counter: int = 1

    def add(self, transaction: Transaction) -> Transaction:
        """Добавляет транзакцию с автогенерацией ключа."""
        assigned_id = self._id_counter
        self._id_counter += 1
        stored_tx = Transaction(
            id=assigned_id,
            user_id=transaction.user_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            account_id=transaction.account_id,
            category_id=transaction.category_id,
            timestamp=transaction.timestamp,
            to_account_id=transaction.to_account_id,
        )
        self._transactions[assigned_id] = stored_tx
        return stored_tx

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по ID."""
        return self._transactions.get(transaction_id)

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает список всех транзакций пользователя."""
        return [
            tx for tx in self._transactions.values() if tx.user_id == user_id
        ]

    def delete(self, transaction_id: int) -> None:
        """Удаляет операцию из словаря."""
        self._transactions.pop(transaction_id, None)


class InMemoryBudgetRepository:
    """Хранилище бюджетных лимитов в памяти."""

    def __init__(self) -> None:
        self._budgets: dict[tuple[int, int, int, int], BudgetLimit] = {}
        self._id_counter: int = 1

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает лимит бюджета."""
        key = (budget.user_id, budget.category_id, budget.month, budget.year)
        budget.id = self._id_counter
        self._id_counter += 1
        self._budgets[key] = budget
        return budget

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Ищет лимит по составному ключу."""
        return self._budgets.get((user_id, category_id, month, year))


class InMemoryCategoryRepository:
    """Хранилище категорий в памяти."""

    def __init__(self) -> None:
        self._categories: dict[int, Category] = {}
        self._id_counter: int = 1

    def add(self, category: Category) -> Category:
        """Добавляет категорию."""
        assigned_id = self._id_counter
        self._id_counter += 1
        stored = Category(
            id=assigned_id,
            user_id=category.user_id,
            name=category.name,
            direction=category.direction,
        )
        self._categories[assigned_id] = stored
        return stored

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""
        return self._categories.get(category_id)

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает категории пользователя."""
        return [c for c in self._categories.values() if c.user_id == user_id]
