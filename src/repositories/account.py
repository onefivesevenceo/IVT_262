from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import AccountMapper
from src.database.models import AccountORM
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
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[int, Account] = {}
        self._seq: int = 1

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
