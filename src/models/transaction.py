from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum


class TransactionType(str, Enum):
    """Тип проводимой финансовой операции."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


@dataclass(frozen=True)
class Transaction:
    """Неизменяемая модель единичной транзакции."""

    id: int
    user_id: int
    transaction_type: TransactionType
    amount: Decimal
    account_id: int
    category_id: int | None
    timestamp: datetime
    to_account_id: int | None = None
