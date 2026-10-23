from datetime import datetime
from decimal import Decimal

from src.models.category import CategoryDirection
from src.models.transaction import Transaction, TransactionType
from src.repositories.base import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
)


class TransactionService:
    """Сервис регистрации операций, атомарных переводов и отката балансов."""

    def __init__(
        self,
        tx_repo: TransactionRepository,
        account_repo: AccountRepository,
        category_repo: CategoryRepository | None = None,
    ) -> None:
        self._tx_repo = tx_repo
        self._account_repo = account_repo
        self._category_repo = category_repo

    def register_transaction(
        self,
        user_id: int,
        tx_type: TransactionType,
        amount: Decimal,
        account_id: int,
        category_id: int | None = None,
    ) -> Transaction:
        """Регистрирует приход/расход и пересчитывает баланс счета."""
        if not amount.is_finite() or amount <= Decimal("0.00"):
            msg = "Сумма операции обязана быть конечной и строго положительной."
            raise ValueError(msg)

        account = self._account_repo.get_by_id(account_id)
        if not account or account.user_id != user_id:
            msg = (
                "Указанный счет не существует "
                "или принадлежит другому пользователю."
            )
            raise PermissionError(msg)

        if category_id is not None and self._category_repo is not None:
            category = self._category_repo.get_by_id(category_id)
            if not category or category.user_id != user_id:
                msg = (
                    "Категория не найдена "
                    "или принадлежит другому пользователю."
                )
                raise PermissionError(msg)

            if (
                tx_type == TransactionType.EXPENSE
                and category.direction != CategoryDirection.EXPENSE
            ):
                msg = "Для операции расхода выбрана категория доходов."
                raise ValueError(msg)

            if (
                tx_type == TransactionType.INCOME
                and category.direction != CategoryDirection.INCOME
            ):
                msg = "Для операции дохода выбрана категория расходов."
                raise ValueError(msg)

        if tx_type == TransactionType.EXPENSE:
            new_balance = account.balance - amount
        elif tx_type == TransactionType.INCOME:
            new_balance = account.balance + amount
        else:
            msg = "Для переводов используйте метод make_transfer."
            raise ValueError(msg)

        self._account_repo.update_balance(account_id, new_balance)

        tx = Transaction(
            id=0,
            user_id=user_id,
            transaction_type=tx_type,
            amount=amount,
            account_id=account_id,
            category_id=category_id,
            timestamp=datetime.now(),
        )
        return self._tx_repo.add(tx)

    def make_transfer(
        self,
        user_id: int,
        from_account_id: int,
        to_account_id: int,
        amount: Decimal,
    ) -> Transaction:
        """Выполняет межбалансовый перевод без изменения совокупного капитала."""
        if not amount.is_finite() or amount <= Decimal("0.00"):
            msg = "Сумма перевода обязана быть конечной и строго положительной."
            raise ValueError(msg)

        if from_account_id == to_account_id:
            msg = "Счета списания и зачисления должны различаться."
            raise ValueError(msg)

        source = self._account_repo.get_by_id(from_account_id)
        target = self._account_repo.get_by_id(to_account_id)

        if not source or source.user_id != user_id:
            msg = "Исходный счет не найден."
            raise PermissionError(msg)

        if not target or target.user_id != user_id:
            msg = "Целевой счет не найден."
            raise PermissionError(msg)

        self._account_repo.update_balance(source.id, source.balance - amount)
        self._account_repo.update_balance(target.id, target.balance + amount)

        tx = Transaction(
            id=0,
            user_id=user_id,
            transaction_type=TransactionType.TRANSFER,
            amount=amount,
            account_id=from_account_id,
            category_id=None,
            timestamp=datetime.now(),
            to_account_id=to_account_id,
        )
        return self._tx_repo.add(tx)

    def delete_transaction(self, transaction_id: int, user_id: int) -> None:
        """Удаляет операцию и выполняет компенсационный пересчет сальдо."""
        tx = self._tx_repo.get_by_id(transaction_id)
        if not tx or tx.user_id != user_id:
            msg = "Операция не найдена."
            raise PermissionError(msg)

        account = self._account_repo.get_by_id(tx.account_id)
        if not account:
            msg = "Связанный счет не найден."
            raise ValueError(msg)

        if tx.transaction_type == TransactionType.EXPENSE:
            self._account_repo.update_balance(
                account.id, account.balance + tx.amount
            )
        elif tx.transaction_type == TransactionType.INCOME:
            self._account_repo.update_balance(
                account.id, account.balance - tx.amount
            )
        elif tx.transaction_type == TransactionType.TRANSFER and tx.to_account_id:
            target = self._account_repo.get_by_id(tx.to_account_id)
            if not target:
                msg = "Целевой счет перевода не найден для отката операции."
                raise ValueError(msg)
            self._account_repo.update_balance(
                account.id, account.balance + tx.amount
            )
            self._account_repo.update_balance(
                target.id, target.balance - tx.amount
            )

        self._tx_repo.delete(transaction_id)

    def get_history(self, user_id: int) -> list[Transaction]:
        """Возвращает журнал операций пользователя."""
        return self._tx_repo.get_all_by_user(user_id)
