from decimal import Decimal

from src.models.budget import BudgetLimit
from src.models.transaction import TransactionType
from src.repositories.base import (
    BudgetRepositoryProtocol,
    TransactionRepositoryProtocol,
)


class BudgetService:
    """Сервис контроля месячных бюджетов и индикации перерасходов."""

    def __init__(
        self,
        budget_repo: BudgetRepositoryProtocol,
        tx_repo: TransactionRepositoryProtocol,
    ) -> None:
        self._budget_repo = budget_repo
        self._tx_repo = tx_repo

    def set_budget(
        self,
        user_id: int,
        category_id: int,
        month: int,
        year: int,
        limit: Decimal,
    ) -> BudgetLimit:
        """Устанавливает лимит расходов на месяц."""
        if limit <= Decimal("0.00"):
            msg = "Лимит бюджета обязан быть положительным числом."
            raise ValueError(msg)

        budget = BudgetLimit(
            id=0,
            user_id=user_id,
            category_id=category_id,
            month=month,
            year=year,
            limit_amount=limit,
        )
        return self._budget_repo.set_limit(budget)

    def calculate_status(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> tuple[Decimal, Decimal, str]:
        """Рассчитывает фактический расход, процент освоения и цветовой индикатор."""
        budget = self._budget_repo.get_limit(user_id, category_id, month, year)
        if not budget:
            msg = "Бюджет на данный период не установлен."
            raise ValueError(msg)

        all_tx = self._tx_repo.get_all_by_user(user_id)
        spent = sum(
            (
                tx.amount
                for tx in all_tx
                if tx.category_id == category_id
                and tx.transaction_type == TransactionType.EXPENSE
                and tx.timestamp.month == month
                and tx.timestamp.year == year
            ),
            Decimal("0.00"),
        )

        ratio = (spent / budget.limit_amount) * Decimal("100")

        if ratio < Decimal("80.0"):
            indicator = "GREEN (Штатный режим)"
        elif Decimal("80.0") <= ratio <= Decimal("100.0"):
            indicator = "YELLOW (Предупреждение)"
        else:
            indicator = "RED (Перерасход)"

        return spent, ratio, indicator
