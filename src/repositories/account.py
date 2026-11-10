from abc import ABC, abstractmethod
from decimal import Decimal

from src.models.account import Account


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
        """Обновляет остаток счета. Если не найден — выбрасывает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для обновления баланса."
            raise ValueError(msg)
        account.balance = new_balance

    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный. Если не найден — выбрасывает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для архивации."
            raise ValueError(msg)
        account.is_archived = True
