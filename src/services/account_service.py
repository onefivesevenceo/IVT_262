from decimal import Decimal

from src.models.account import Account, AccountType
from src.repositories.base import AccountRepositoryProtocol


class AccountService:
    """Сервис бизнес-логики управления счетами и сальдо."""

    def __init__(self, account_repo: AccountRepositoryProtocol) -> None:
        self._repo = account_repo

    def create_account(
        self,
        user_id: int,
        name: str,
        account_type: AccountType,
        initial_balance: Decimal,
    ) -> Account:
        """Создает новый финансовый счет пользователя."""
        account = Account(
            id=0,
            user_id=user_id,
            name=name,
            account_type=account_type,
            balance=initial_balance,
        )
        return self._repo.add(account)

    def get_user_accounts(self, user_id: int) -> list[Account]:
        """Возвращает список активных счетов пользователя."""
        return self._repo.get_all_by_user(user_id)

    def calculate_total_capital(self, user_id: int) -> Decimal:
        """Рассчитывает совокупный капитал пользователя."""
        accounts = self._repo.get_all_by_user(user_id)
        return sum((acc.balance for acc in accounts), Decimal("0.00"))

    def archive_account(self, account_id: int, user_id: int) -> None:
        """Архивирует счет с валидацией принадлежности владельцу."""
        account = self._repo.get_by_id(account_id)
        if not account or account.user_id != user_id:
            msg = "Счет не найден или доступ запрещен."
            raise ValueError(msg)
        self._repo.archive(account_id)
