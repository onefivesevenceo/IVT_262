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
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[int, Transaction] = {}
        self._seq: int = 1

    def add(self, transaction: Transaction) -> Transaction:
        """Сохраняет транзакцию в памяти."""
        saved = Transaction(
            id=self._seq,
            user_id=transaction.user_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            account_id=transaction.account_id,
            category_id=transaction.category_id,
            timestamp=transaction.timestamp,
            to_account_id=transaction.to_account_id,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по ее номеру."""
        return self._storage.get(transaction_id)

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает историю операций пользователя."""
        return [tx for tx in self._storage.values() if tx.user_id == user_id]

    def delete(self, transaction_id: int) -> None:
        """Удаляет запись транзакции по первичному ключу."""
        self._storage.pop(transaction_id, None)
