from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class AccountType(str, Enum):
    """Типы финансовых счетов."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    CASH = "CASH"
    SAVINGS = "SAVINGS"


@dataclass
class Account:
    """Доменная модель счета с поддержкой изменения баланса и архивации."""

    id: int
    user_id: int
    name: str
    account_type: AccountType
    balance: Decimal
    is_archived: bool = False
