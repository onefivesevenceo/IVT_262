from decimal import Decimal

from src.models.budget import BudgetLimit
from src.models.category import CategoryDirection
from src.models.transaction import TransactionType
from src.repositories.base import (
    BudgetRepository,
    CategoryRepository,
    TransactionRepository,
)


class BudgetService:
    """Сервис контроля лимитов и расчета освоения бюджетов."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        tx_repo: TransactionRepository,
        category_repo: CategoryRepository | None = None,
    ) -> None:
        self._budget_repo = budget_repo
        self._tx_repo = tx_repo
        self._category_repo = category_repo

    @staticmethod
    def _validate_period(month: int, year: int) -> None:
        """Проверяет корректность календарного месяца и года."""
        if not 1 <= month <= 12:
            msg = "Номер месяца должен находиться в диапазоне от 1 до 12."
            raise ValueError(msg)
        if year < 1970 or year > 2100:
            msg = "Указан некорректный календарный год."
            raise ValueError(msg)

    def set_budget(
        self,
        user_id: int,
        category_id: int,
        month: int,
        year: int,
        limit_amount: Decimal,
    ) -> BudgetLimit:
        """Устанавливает лимит бюджета на календарный месяц."""
        self._validate_period(month, year)

        if not limit_amount.is_finite() or limit_amount <= Decimal("0.00"):
            msg = "Лимит бюджета обязан быть конечным положительным числом."
            raise ValueError(msg)

        if self._category_repo is not None:
            category = self._category_repo.get_by_id(category_id)
            if not category or category.user_id != user_id:
                msg = "Категория не найдена или принадлежит другому пользователю."
                raise PermissionError(msg)
            if category.direction != CategoryDirection.EXPENSE:
                msg = "Бюджетный лимит можно установить только для категории расходов."
                raise ValueError(msg)

        budget = BudgetLimit(
            id=0,
            user_id=user_id,
            category_id=category_id,
            month=month,
            year=year,
            limit_amount=limit_amount,
        )
        return self._budget_repo.set_limit(budget)

    def calculate_status(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> tuple[Decimal, Decimal, str]:
        """Рассчитывает сумму расходов, процент освоения и цветовой статус."""
        self._validate_period(month, year)

        budget = self._budget_repo.get_limit(user_id, category_id, month, year)
        if not budget:
            msg = "Бюджетный лимит на указанный период не установлен."
            raise ValueError(msg)

        txs = self._tx_repo.get_all_by_user(user_id)
        spent = sum(
            (
                tx.amount
                for tx in txs
                if tx.category_id == category_id
                and tx.transaction_type == TransactionType.EXPENSE
                and tx.timestamp.month == month
                and tx.timestamp.year == year
            ),
            Decimal("0.00"),
        )

        ratio = (
            (spent / budget.limit_amount) * Decimal("100.0")
            if budget.limit_amount > 0
            else Decimal("0.0")
        )

        if ratio < Decimal("80.0"):
            indicator = "GREEN (Штатный режим)"
        elif ratio <= Decimal("100.0"):
            indicator = "YELLOW (Внимание, приближение к лимиту)"
        else:
            indicator = "RED (Лимит превышен)"

        return spent, ratio, indicator
