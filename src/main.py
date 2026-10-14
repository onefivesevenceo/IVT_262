"""Точка входа в программу CapitalTracker.

Инициализирует зависимости приложения и запускает терминальный интерфейс.
"""

import sys

from src.cli.terminal_interface import TerminalInterface
from src.repositories.in_memory import (
    InMemoryAccountRepository,
    InMemoryBudgetRepository,
    InMemoryCategoryRepository,
    InMemoryTransactionRepository,
)
from src.services.account_service import AccountService
from src.services.budget_service import BudgetService
from src.services.export_service import ExportService
from src.services.transaction_service import TransactionService


def main() -> None:
    """Инициализирует доменные сервисы и запускает рабочий цикл CLI."""
    user_id = 1

    account_repo = InMemoryAccountRepository()
    transaction_repo = InMemoryTransactionRepository()
    budget_repo = InMemoryBudgetRepository()
    category_repo = InMemoryCategoryRepository()

    account_service = AccountService(account_repo)
    transaction_service = TransactionService(transaction_repo, account_repo)
    budget_service = BudgetService(budget_repo, transaction_repo)
    export_service = ExportService(account_repo, category_repo)

    cli_app = TerminalInterface(
        user_id=user_id,
        account_service=account_service,
        tx_service=transaction_service,
        budget_service=budget_service,
        category_repo=category_repo,
        export_service=export_service,
    )

    try:
        cli_app.run()
    except KeyboardInterrupt:
        print("\n[!] Программа экстренно остановлена пользователем.")
        sys.exit(0)


if __name__ == "__main__":
    main()
