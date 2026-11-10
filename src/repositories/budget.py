from abc import ABC, abstractmethod

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
