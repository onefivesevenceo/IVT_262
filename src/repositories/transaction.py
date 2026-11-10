from abc import ABC, abstractmethod

from src.models.transaction import Transaction


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


class InMemoryTransactionRepository(TransactionRepository):
    """Хранилище транзакций в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Transaction] = {}
        self._seq: int = 1

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
        return [tx for tx in self._storage.values() if tx.user_id == user_id]

    def delete(self, tx_id: int) -> None:
        """Удаляет запись транзакции по первичному ключу."""
        self._storage.pop(tx_id, None)
