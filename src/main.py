"""Сборка приложения с SQLAlchemy и одной транзакцией на команду CLI."""

from datetime import datetime
from decimal import InvalidOperation

from sqlalchemy import select
from sqlalchemy.exc import DataError, IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from src.cli.terminal_interface import TerminalInterface
from src.database.mappers import UserMapper
from src.database.models import UserORM
from src.database.session import SessionFactory
from src.models.user import User
from src.repositories.sqlalchemy import (
    SQLAlchemyAccountRepository,
    SQLAlchemyBudgetRepository,
    SQLAlchemyCategoryRepository,
    SQLAlchemyTransactionRepository,
)
from src.services.account import AccountService
from src.services.budget import BudgetService
from src.services.category import CategoryService
from src.services.export import ExportService
from src.services.transaction import TransactionService


def build_interface(session: Session, user_id: int) -> TerminalInterface:
    """Собирает сервисы поверх одной сессии текущей команды."""
    accounts = SQLAlchemyAccountRepository(session)
    categories = SQLAlchemyCategoryRepository(session)
    transactions = SQLAlchemyTransactionRepository(session)
    budgets = SQLAlchemyBudgetRepository(session)
    return TerminalInterface(
        user_id=user_id,
        account_service=AccountService(accounts),
        tx_service=TransactionService(transactions, accounts, categories),
        budget_service=BudgetService(budgets, transactions, categories),
        category_service=CategoryService(categories),
        export_service=ExportService(accounts, categories),
    )


def initialize_profile() -> int:
    """Повторяемо создает учебный профиль CLI и начальные категории.

    Авторизация остается за рамками консольного прототипа. Маркер !disabled
    не является хэшем реального пароля и не допускает входа в учетную запись.
    """
    with SessionFactory.begin() as session:
        user = session.scalar(
            select(UserORM).where(UserORM.email == "cli@capitaltracker.local")
        )
        if user is None:
            user = UserMapper.to_orm(
                User(
                    id=0,
                    username="CLI",
                    email="cli@capitaltracker.local",
                    password_hash="!disabled",
                    created_at=datetime.now(),
                )
            )
            session.add(user)
            session.flush()
        CategoryService(SQLAlchemyCategoryRepository(session)).seed_defaults(user.id)
        return user.id


def run_application() -> None:
    """Обрабатывает команды, фиксируя успех и откатывая ошибочные изменения."""
    user_id = initialize_profile()
    while True:
        try:
            with SessionFactory.begin() as session:
                keep_running = build_interface(session, user_id).run_once()
            if not keep_running:
                break
        except (InvalidOperation, ValueError, PermissionError) as err:
            print(f"[!] Ошибка: {err}. Изменения команды отменены.")
        except (IntegrityError, DataError):
            print("[!] Нарушено ограничение базы данных. Изменения команды отменены.")


def main() -> None:
    """Запускает CLI после отдельно выполненных миграций Alembic."""
    try:
        run_application()
    except (KeyboardInterrupt, EOFError):
        print("\n[!] Ввод завершен. Незавершенная команда отменена.")
    except SQLAlchemyError:
        print(
            "[!] База данных недоступна или схема не подготовлена. "
            "Проверьте DATABASE_URL, запустите docker compose up -d "
            "и uv run alembic upgrade head."
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
