"""Проверка денежных значений перед сохранением в NUMERIC(18, 2)."""

from decimal import Decimal

MAX_MONEY = Decimal("9999999999999999.99")
CENT = Decimal("0.01")


def validate_money(value: Decimal, *, positive: bool = False) -> None:
    """Проверяет конечность, диапазон и точность до копеек без округления."""
    if not value.is_finite():
        msg = "Денежное значение должно быть конечным числом."
        raise ValueError(msg)
    if positive and value <= Decimal("0.00"):
        msg = "Сумма должна быть строго положительной."
        raise ValueError(msg)
    if value < -MAX_MONEY or value > MAX_MONEY:
        msg = "Сумма выходит за диапазон NUMERIC(18, 2)."
        raise ValueError(msg)
    if value != value.quantize(CENT):
        msg = "Сумма должна быть указана с точностью до копеек."
        raise ValueError(msg)
