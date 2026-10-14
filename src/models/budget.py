from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BudgetLimit:
    """Лимит расходов по категории на календарный месяц."""

    id: int
    user_id: int
    category_id: int
    month: int
    year: int
    limit_amount: Decimal
