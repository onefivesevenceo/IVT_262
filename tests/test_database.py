"""Приемочные проверки миграций, ограничений и финансовых сценариев на PostgreSQL."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, delete, inspect, select, text, update
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src import main as application
from src.database.mappers import UserMapper
from src.database.models import (
    AccountORM,
    BudgetLimitORM,
    CategoryORM,
    TransactionORM,
    UserORM,
)
from src.models.account import AccountType
from src.models.budget import BudgetLimit
from src.models.transaction import Transaction, TransactionType
from src.models.user import User
from src.repositories.sqlalchemy import (
    SQLAlchemyAccountRepository,
    SQLAlchemyBudgetRepository,
    SQLAlchemyCategoryRepository,
    SQLAlchemyTransactionRepository,
)
from src.services.account import AccountService
from src.services.budget import BudgetService
from src.services.export import ExportService
from src.services.transaction import TransactionService


def transaction_service(session: Session) -> TransactionService:
    """Собирает сервис операций с общей сессией всех репозиториев."""
    return TransactionService(
        SQLAlchemyTransactionRepository(session),
        SQLAlchemyAccountRepository(session),
        SQLAlchemyCategoryRepository(session),
    )


def test_migration_roundtrip(engine: Engine) -> None:
    """Проверяет downgrade/upgrade и отсутствие расхождений схемы с моделями."""
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        command.upgrade(config, "head")
        assert set(inspect(connection).get_table_names()) == {
            "users",
            "accounts",
            "categories",
            "transactions",
            "budget_limits",
            "alembic_version",
        }
        command.check(config)


@pytest.mark.parametrize("kind", [TransactionType.INCOME, TransactionType.EXPENSE])
def test_operation_and_delete(
    session: Session, records: tuple[int, int, int, int, int], kind: TransactionType
) -> None:
    """Проверяет точные остатки дохода/расхода и компенсационное удаление."""
    owner, source, _, expense, income = records
    service = transaction_service(session)
    category = income if kind is TransactionType.INCOME else expense
    tx = service.register_transaction(owner, kind, Decimal("25.15"), source, category)
    accounts = SQLAlchemyAccountRepository(session)
    account = accounts.get_by_id(source)
    assert account is not None
    assert account.balance == Decimal("1000") + (
        Decimal("25.15") if kind is TransactionType.INCOME else Decimal("-25.15")
    )
    service.delete_transaction(tx.id, owner)
    account = accounts.get_by_id(source)
    assert account is not None and account.balance == Decimal("1000")
    assert service.get_history(owner) == []


def test_transfer_and_archive_history(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет перевод, запрет новых проводок в архив и отмену старого перевода."""
    owner, source, target, _, _ = records
    service = transaction_service(session)
    accounts = AccountService(SQLAlchemyAccountRepository(session))
    tx = service.make_transfer(owner, source, target, Decimal("200"))
    assert accounts.calculate_total_capital(owner) == Decimal("1500")
    accounts.archive_account(target, owner)
    assert len(accounts.get_user_accounts(owner)) == 1
    with pytest.raises(ValueError, match="архив"):
        service.make_transfer(owner, source, target, Decimal("1"))
    service.delete_transaction(tx.id, owner)
    row = session.get(AccountORM, target)
    assert row is not None and row.balance == Decimal("500") and row.is_archived


def test_failed_journal_insert_rolls_back_balances(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Воспроизводит сбой INSERT после изменения обоих остатков и проверяет откат."""
    owner, source, target, _, _ = records
    journal = SQLAlchemyTransactionRepository(session)
    accounts = SQLAlchemyAccountRepository(session)
    service = TransactionService(
        journal, accounts, SQLAlchemyCategoryRepository(session)
    )

    def fail_insert(tx: Transaction) -> Transaction:
        """Вызывает настоящее нарушение NOT NULL при записи журнала."""
        session.execute(text("INSERT INTO transactions (id) VALUES (NULL)"))
        return tx

    monkeypatch.setattr(journal, "add", fail_insert)
    with pytest.raises(IntegrityError), session.begin_nested():
        service.make_transfer(owner, source, target, Decimal("200"))
    source_row = accounts.get_by_id(source)
    target_row = accounts.get_by_id(target)
    assert source_row is not None and source_row.balance == Decimal("1000")
    assert target_row is not None and target_row.balance == Decimal("500")
    assert journal.get_all_by_user(owner) == []


@pytest.mark.parametrize(
    "amount,color",
    [
        ("79.99", "GREEN"),
        ("80", "YELLOW"),
        ("100", "YELLOW"),
        ("100.01", "RED"),
    ],
)
def test_budget_boundaries_and_replacement(
    session: Session, records: tuple[int, int, int, int, int], amount: str, color: str
) -> None:
    """Проверяет границы индикации и обновление лимита без смены ID."""
    owner, source, _, expense, _ = records
    now = datetime.now()
    budgets = BudgetService(
        SQLAlchemyBudgetRepository(session),
        SQLAlchemyTransactionRepository(session),
        SQLAlchemyCategoryRepository(session),
    )
    first = budgets.set_budget(owner, expense, now.month, now.year, Decimal("200"))
    second = budgets.set_budget(owner, expense, now.month, now.year, Decimal("100"))
    assert first.id == second.id
    transaction_service(session).register_transaction(
        owner, TransactionType.EXPENSE, Decimal(amount), source, expense
    )
    spent, ratio, status = budgets.calculate_status(owner, expense, now.month, now.year)
    assert spent == Decimal(amount) and ratio == Decimal(amount)
    assert status.startswith(color)


def test_many_to_many_and_export(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет обе стороны M:N, повторные операции и сохранение CSV с BOM."""
    owner, source, target, expense, income = records
    service = transaction_service(session)
    for account, category, kind in [
        (source, expense, TransactionType.EXPENSE),
        (source, expense, TransactionType.EXPENSE),
        (target, expense, TransactionType.EXPENSE),
        (source, income, TransactionType.INCOME),
    ]:
        service.register_transaction(owner, kind, Decimal("1"), account, category)
    service.make_transfer(owner, source, target, Decimal("2"))
    row = session.get(AccountORM, source)
    category_row = session.get(CategoryORM, expense)
    assert row is not None and {c.id for c in row.categories} == {expense, income}
    assert category_row is not None
    assert {a.id for a in category_row.accounts} == {source, target}
    assert len(row.categories) == 2
    output = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    ).export_to_csv(service.get_history(owner))
    assert output.encode("utf-8").startswith(b"\xef\xbb\xbf")
    assert "ID;Дата и время;Тип;Счет;Категория;Сумма (руб.)" in output
    assert "Продукты" in output and "Без категории" in output


@pytest.mark.parametrize("amount", ["0", "-1", "NaN", "Infinity", "-Infinity"])
def test_database_rejects_invalid_amount(
    session: Session, records: tuple[int, int, int, int, int], amount: str
) -> None:
    """Проверяет ограничение суммы непосредственно в БД, минуя сервис."""
    owner, source, _, expense, _ = records
    tx = transaction_service(session).register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    expected_error = DataError if "Infinity" in amount else IntegrityError
    with pytest.raises(expected_error), session.begin_nested():
        session.execute(
            update(TransactionORM)
            .where(TransactionORM.id == tx.id)
            .values(amount=Decimal(amount))
        )


@pytest.mark.parametrize("column", ["account_id", "category_id", "to_account_id"])
def test_database_blocks_foreign_owner(
    session: Session, records: tuple[int, int, int, int, int], column: str
) -> None:
    """Проверяет составные FK при попытке связать операцию с чужой сущностью."""
    owner, source, target, expense, _ = records
    other = UserMapper.to_orm(
        User(0, "Другой", "other@capitaltracker.local", "!disabled", datetime.now())
    )
    session.add(other)
    session.flush()
    foreign_account = AccountService(
        SQLAlchemyAccountRepository(session)
    ).create_account(other.id, "Чужой", AccountType.CASH, Decimal("0"))
    foreign_category = CategoryORM(user_id=other.id, name="Чужая", direction="EXPENSE")
    session.add(foreign_category)
    session.flush()
    service = transaction_service(session)
    if column == "to_account_id":
        tx = service.make_transfer(owner, source, target, Decimal("1"))
    else:
        tx = service.register_transaction(
            owner, TransactionType.EXPENSE, Decimal("1"), source, expense
        )
    foreign_id = foreign_category.id if column == "category_id" else foreign_account.id
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            update(TransactionORM)
            .where(TransactionORM.id == tx.id)
            .values(**{column: foreign_id})
        )
    with pytest.raises(PermissionError):
        service.make_transfer(owner, source, foreign_account.id, Decimal("1"))
    assert service.get_history(other.id) == []


@pytest.mark.parametrize("entity", ["account", "category", "user"])
@pytest.mark.parametrize("loaded", [False, True])
def test_delete_restrict_preserves_history(
    session: Session, records: tuple[int, int, int, int, int], entity: str, loaded: bool
) -> None:
    """Проверяет RESTRICT и для загруженных, и для незагруженных ORM-коллекций."""
    owner, source, _, expense, _ = records
    transaction_service(session).register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    row: AccountORM | CategoryORM | UserORM | None
    if entity == "account":
        row = session.get(AccountORM, source)
        assert row is not None
        if loaded:
            assert row.transactions
    elif entity == "category":
        row = session.get(CategoryORM, expense)
        assert row is not None
        if loaded:
            assert row.transactions
    else:
        row = session.get(UserORM, owner)
        assert row is not None
        if loaded:
            assert row.accounts and row.categories and row.transactions
    with pytest.raises(IntegrityError), session.begin_nested():
        session.delete(row)
        session.flush()
    assert len(transaction_service(session).get_history(owner)) == 1


@pytest.mark.parametrize(
    "values",
    [
        {"category_id": None},
        {"to_account_id": -1},
        {"transaction_type": "INVALID"},
    ],
)
def test_transaction_shape_constraints(
    session: Session, records: tuple[int, int, int, int, int], values: dict[str, object]
) -> None:
    """Отклоняет некорректную структуру финансовой операции на уровне БД."""
    owner, source, _, expense, _ = records
    tx = transaction_service(session).register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            update(TransactionORM).where(TransactionORM.id == tx.id).values(**values)
        )


def test_profile_initialization_and_cli_rollback(
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Проверяет повторный seed и продолжение CLI после ошибки ввода."""
    factory = sessionmaker(
        bind=session.connection(),
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    monkeypatch.setattr(application, "SessionFactory", factory)
    first = application.initialize_profile()
    assert application.initialize_profile() == first
    assert (
        len(
            list(
                session.scalars(select(CategoryORM).where(CategoryORM.user_id == first))
            )
        )
        == 3
    )
    answers = iter(["2", "Карта", "1", "не число", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    application.run_application()
    assert "Изменения команды отменены" in capsys.readouterr().out
    assert (
        list(session.scalars(select(AccountORM).where(AccountORM.user_id == first)))
        == []
    )


def test_failed_transfer_delete_rolls_back(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет откат отмены перевода, если второе обновление завершилось ошибкой."""
    owner, source, target, _, _ = records
    accounts = SQLAlchemyAccountRepository(session)
    journal = SQLAlchemyTransactionRepository(session)
    service = TransactionService(
        journal, accounts, SQLAlchemyCategoryRepository(session)
    )
    tx = service.make_transfer(owner, source, target, Decimal("200"))
    original_update = accounts.update_balance

    def fail_target(account_id: int, amount: Decimal) -> None:
        """Имитирует ошибку после первого обновления остатка."""
        if account_id == target:
            raise ValueError("Сбой обновления целевого счета")
        original_update(account_id, amount)

    monkeypatch.setattr(accounts, "update_balance", fail_target)
    with pytest.raises(ValueError, match="Сбой"), session.begin_nested():
        service.delete_transaction(tx.id, owner)
    source_row = accounts.get_by_id(source)
    target_row = accounts.get_by_id(target)
    assert source_row is not None and source_row.balance == Decimal("800")
    assert target_row is not None and target_row.balance == Decimal("700")
    assert journal.get_by_id(tx.id) is not None


@pytest.mark.parametrize(
    "values",
    [
        {"month": 0},
        {"month": 13},
        {"year": 1969},
        {"year": 2101},
        {"limit_amount": Decimal("NaN")},
        {"limit_amount": Decimal("0")},
    ],
)
def test_budget_database_constraints(
    session: Session, records: tuple[int, int, int, int, int], values: dict[str, object]
) -> None:
    """Проверяет границы периода и суммы лимита напрямую в PostgreSQL."""
    owner, _, _, expense, _ = records
    budget = SQLAlchemyBudgetRepository(session).set_limit(
        application_budget(owner, expense)
    )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            update(BudgetLimitORM)
            .where(BudgetLimitORM.id == budget.id)
            .values(**values)
        )


def application_budget(owner: int, category: int) -> BudgetLimit:
    """Создает доменный лимит для проверки сохранения бюджетов."""
    return BudgetLimit(0, owner, category, 1, 2026, Decimal("100"))


def test_budget_unique_and_owner_constraints(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Запрещает дубли периода и назначение чужой категории лимиту."""
    owner, _, _, expense, _ = records
    budget = SQLAlchemyBudgetRepository(session).set_limit(
        application_budget(owner, expense)
    )
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(
            BudgetLimitORM(
                user_id=owner,
                category_id=expense,
                month=1,
                year=2026,
                limit_amount=Decimal("200"),
            )
        )
        session.flush()
    other = UserMapper.to_orm(
        User(0, "Другой", "budget@capitaltracker.local", "!disabled", datetime.now())
    )
    session.add(other)
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(
            update(BudgetLimitORM)
            .where(BudgetLimitORM.id == budget.id)
            .values(user_id=other.id)
        )


def test_budget_filters_type_and_period(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Исключает доходы и расходы другого периода даже при прямой записи в БД."""
    owner, source, _, expense, _ = records
    journal = SQLAlchemyTransactionRepository(session)
    for kind, year in [(TransactionType.INCOME, 2026), (TransactionType.EXPENSE, 2025)]:
        journal.add(
            Transaction(
                0, owner, kind, Decimal("500"), source, expense, datetime(year, 1, 5)
            )
        )
    journal.add(
        Transaction(
            0,
            owner,
            TransactionType.EXPENSE,
            Decimal("30"),
            source,
            expense,
            datetime(2026, 1, 5),
        )
    )
    SQLAlchemyBudgetRepository(session).set_limit(application_budget(owner, expense))
    status = BudgetService(
        SQLAlchemyBudgetRepository(session),
        journal,
        SQLAlchemyCategoryRepository(session),
    ).calculate_status(owner, expense, 1, 2026)
    assert status[0] == Decimal("30") and status[1] == Decimal("30")


def test_data_survives_session_restart(engine: Engine) -> None:
    """Проверяет настоящий commit и чтение из новой независимой сессии."""
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as first:
        user = UserMapper.to_orm(
            User(
                0,
                "Сохранение",
                "persist@capitaltracker.local",
                "!disabled",
                datetime.now(),
            )
        )
        first.add(user)
        first.flush()
        account = AccountService(SQLAlchemyAccountRepository(first)).create_account(
            user.id, "Сохраненный", AccountType.CREDIT, Decimal("-20.25")
        )
    try:
        with factory() as second:
            saved = SQLAlchemyAccountRepository(second).get_by_id(account.id)
            assert saved is not None and saved.balance == Decimal("-20.25")
    finally:
        with factory.begin() as cleanup:
            cleanup.execute(delete(AccountORM).where(AccountORM.id == account.id))
            cleanup.execute(delete(UserORM).where(UserORM.id == user.id))


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "0", "-1"])
def test_service_rejects_invalid_money(
    session: Session, records: tuple[int, int, int, int, int], amount: str
) -> None:
    """Отклоняет некорректные суммы до изменения баланса и отправки SQL."""
    owner, source, _, expense, _ = records
    with pytest.raises(ValueError):
        transaction_service(session).register_transaction(
            owner, TransactionType.EXPENSE, Decimal(amount), source, expense
        )
    saved = SQLAlchemyAccountRepository(session).get_by_id(source)
    assert saved is not None and saved.balance == Decimal("1000")


def test_service_requires_category_and_account_validation(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет обязательность категории и перенос валидации счета из CLI в сервис."""
    owner, source, _, _, _ = records
    with pytest.raises(ValueError, match="категори"):
        transaction_service(session).register_transaction(
            owner, TransactionType.EXPENSE, Decimal("1"), source
        )
    accounts = AccountService(SQLAlchemyAccountRepository(session))
    with pytest.raises(ValueError, match="Наименование"):
        accounts.create_account(owner, " ", AccountType.CASH, Decimal("0"))
    with pytest.raises(ValueError, match="конечным"):
        accounts.create_account(owner, "Счет", AccountType.CASH, Decimal("NaN"))
    with pytest.raises(PermissionError):
        accounts.archive_account(source, owner + 999999)


@pytest.mark.parametrize("amount", ["0.005", "1E100", "NaN", "Infinity"])
def test_money_validation_preserves_transfer_capital(
    session: Session, records: tuple[int, int, int, int, int], amount: str
) -> None:
    """Не допускает округления дробных копеек или переполнения при переводе."""
    owner, source, target, _, _ = records
    with pytest.raises(ValueError):
        transaction_service(session).make_transfer(
            owner, source, target, Decimal(amount)
        )
    accounts = AccountService(SQLAlchemyAccountRepository(session))
    assert accounts.calculate_total_capital(owner) == Decimal("1500")
    assert transaction_service(session).get_history(owner) == []
