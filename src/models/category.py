from dataclasses import dataclass
from enum import Enum


class CategoryDirection(str, Enum):
    """Направление финансовых потоков категории."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


@dataclass(frozen=True)
class Category:
    """Категория классификации доходов и расходов."""

    id: int
    user_id: int
    name: str
    direction: CategoryDirection
