from decimal import Decimal

from src.models.account import Account, AccountType
from src.repositories.account import AccountRepository
from src.services.money import validate_money


class AccountService:
    """Сервис бизнес-логики управления счетами и сальдо."""

    def __init__(self, account_repo: AccountRepository) -> None:
        """Получает абстрактное хранилище счетов."""
        self._repo = account_repo

    def create_account(
        self,
        user_id: int,
        name: str,
        account_type: AccountType,
        initial_balance: Decimal,
    ) -> Account:
        """Создает новый финансовый счет пользователя."""
        clean_name = name.strip()
        if not clean_name:
            msg = "Наименование счета не может быть пустым."
            raise ValueError(msg)
        if len(clean_name) > 100:
            msg = "Название счета должно содержать не более 100 символов."
            raise ValueError(msg)
        validate_money(initial_balance)
        account = Account(
            id=0,
            user_id=user_id,
            name=clean_name,
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
            raise PermissionError(msg)
        self._repo.archive(account_id)
