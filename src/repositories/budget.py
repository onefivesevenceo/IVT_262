from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import BudgetLimitMapper
from src.database.models import BudgetLimitORM
from src.models.budget import BudgetLimit


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


class InMemoryBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов бюджетов в оперативной памяти."""

    def __init__(self) -> None:
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[str, BudgetLimit] = {}
        self._seq: int = 1

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
