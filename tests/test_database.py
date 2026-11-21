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
from src.cli.terminal_interface import TerminalInterface
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
from src.repositories.account import SQLAlchemyAccountRepository
from src.repositories.budget import SQLAlchemyBudgetRepository
from src.repositories.category import SQLAlchemyCategoryRepository
from src.repositories.transaction import SQLAlchemyTransactionRepository
from src.services.account import AccountService
from src.services.budget import BudgetService
from src.services.category import CategoryService
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
    ).export_to_csv(owner, service.get_history(owner))
    assert output.encode("utf-8").startswith(b"\xef\xbb\xbf")
    assert "ID;Дата и время;Тип;Счет;Категория;Сумма (руб.)" in output
    assert "Продукты" in output and "Без категории" in output


def test_export_rejects_foreign_transaction(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Запрещает экспорт операции другого пользователя."""
    owner, source, _, _, _ = records
    other = UserMapper.to_orm(
        User(
            0,
            "Другой",
            "other-export@capitaltracker.local",
            "!disabled",
            datetime.now(),
        )
    )
    session.add(other)
    session.flush()

    foreign_tx = Transaction(
        1,
        other.id,
        TransactionType.EXPENSE,
        Decimal("10"),
        source,
        None,
        datetime.now(),
    )
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    with pytest.raises(PermissionError):
        exporter.export_to_csv(owner, [foreign_tx])


def test_export_rejects_mixed_owners(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Запрещает частичный экспорт списка с разными владельцами."""
    owner, source, _, expense, _ = records
    other = UserMapper.to_orm(
        User(
            0, "Другой", "other-mixed@capitaltracker.local", "!disabled", datetime.now()
        )
    )
    session.add(other)
    session.flush()

    service = transaction_service(session)
    own_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("10"), source, expense
    )
    foreign_tx = Transaction(
        2,
        other.id,
        TransactionType.EXPENSE,
        Decimal("5"),
        source,
        expense,
        datetime.now(),
    )
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    with pytest.raises(PermissionError):
        exporter.export_to_csv(owner, [own_tx, foreign_tx])


def test_export_rejects_foreign_account_in_transaction(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет владельца основного счета в доменном объекте."""
    owner, _, _, _, _ = records
    other = UserMapper.to_orm(
        User(
            0,
            "Другой",
            "other-account@capitaltracker.local",
            "!disabled",
            datetime.now(),
        )
    )
    session.add(other)
    session.flush()
    foreign_account = AccountService(
        SQLAlchemyAccountRepository(session)
    ).create_account(other.id, "Чужой", AccountType.CASH, Decimal("0"))

    tx = Transaction(
        1,
        owner,
        TransactionType.EXPENSE,
        Decimal("10"),
        foreign_account.id,
        None,
        datetime.now(),
    )
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    with pytest.raises(PermissionError):
        exporter.export_to_csv(owner, [tx])


def test_export_rejects_foreign_category(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет владельца категории в доменном объекте."""
    owner, source, _, _, _ = records
    other = UserMapper.to_orm(
        User(
            0,
            "Другой",
            "other-category@capitaltracker.local",
            "!disabled",
            datetime.now(),
        )
    )
    session.add(other)
    session.flush()
    foreign_category = CategoryORM(user_id=other.id, name="Чужая", direction="EXPENSE")
    session.add(foreign_category)
    session.flush()

    tx = Transaction(
        1,
        owner,
        TransactionType.EXPENSE,
        Decimal("10"),
        source,
        foreign_category.id,
        datetime.now(),
    )
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    with pytest.raises(PermissionError):
        exporter.export_to_csv(owner, [tx])


def test_export_rejects_foreign_transfer_target(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет владельца целевого счета перевода."""
    owner, source, _, _, _ = records
    other = UserMapper.to_orm(
        User(
            0,
            "Другой",
            "other-target@capitaltracker.local",
            "!disabled",
            datetime.now(),
        )
    )
    session.add(other)
    session.flush()
    foreign_account = AccountService(
        SQLAlchemyAccountRepository(session)
    ).create_account(other.id, "Чужой", AccountType.CASH, Decimal("0"))

    tx = Transaction(
        1,
        owner,
        TransactionType.TRANSFER,
        Decimal("10"),
        source,
        None,
        datetime.now(),
        foreign_account.id,
    )
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    with pytest.raises(PermissionError):
        exporter.export_to_csv(owner, [tx])


def test_export_allows_archived_account_history(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Разрешает экспорт истории собственного архивного счета."""
    owner, source, _, expense, _ = records
    service = transaction_service(session)
    service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("10"), source, expense
    )
    AccountService(SQLAlchemyAccountRepository(session)).archive_account(source, owner)

    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )
    output = exporter.export_to_csv(owner, service.get_history(owner))

    assert "Продукты" in output


def test_export_empty_history_has_bom_and_headers(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет BOM и заголовки CSV при пустом списке операций."""
    owner, _, _, _, _ = records
    exporter = ExportService(
        SQLAlchemyAccountRepository(session), SQLAlchemyCategoryRepository(session)
    )

    output = exporter.export_to_csv(owner, [])

    assert output.encode("utf-8").startswith(b"\xef\xbb\xbf")
    assert "ID;Дата и время;Тип;Счет;Категория;Сумма (руб.)" in output


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


def test_account_name_length_is_checked_after_trimming(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет ограничение названия счета в 100 символов после trim."""
    owner = records[0]
    accounts = AccountService(SQLAlchemyAccountRepository(session))

    account = accounts.create_account(owner, "A" * 100, AccountType.CASH, Decimal("0"))
    assert len(account.name) == 100

    with pytest.raises(ValueError, match="100"):
        accounts.create_account(owner, "A" * 101, AccountType.CASH, Decimal("0"))

    trimmed = accounts.create_account(
        owner, " " + "B" * 100 + " ", AccountType.CASH, Decimal("0")
    )
    assert trimmed.name == "B" * 100


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


def test_history_filters_by_inclusive_dates(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет включительность границ периода и исключение операций вне него."""
    owner, source, _, expense, _ = records
    service = transaction_service(session)

    transactions = [
        service.register_transaction(
            owner, TransactionType.EXPENSE, Decimal("1"), source, expense
        )
        for _ in range(4)
    ]

    timestamps = [
        datetime(2025, 12, 31, 23, 59),
        datetime(2026, 1, 1, 0, 0),
        datetime(2026, 1, 3, 23, 59),
        datetime(2026, 1, 4, 0, 0),
    ]

    for tx, timestamp in zip(transactions, timestamps, strict=True):
        session.execute(
            update(TransactionORM)
            .where(TransactionORM.id == tx.id)
            .values(timestamp=timestamp)
        )

    session.flush()

    result = service.get_history(
        owner,
        date_from=datetime(2026, 1, 1).date(),
        date_to=datetime(2026, 1, 3).date(),
    )

    assert [tx.id for tx in result] == [
        transactions[1].id,
        transactions[2].id,
    ]


def test_history_rejects_invalid_date_range(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет запрет диапазона, в котором начальная дата позже конечной."""
    owner = records[0]

    with pytest.raises(ValueError):
        transaction_service(session).get_history(
            owner,
            date_from=datetime(2026, 1, 2).date(),
            date_to=datetime(2026, 1, 1).date(),
        )


def test_history_filters_by_transaction_type(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет фильтрацию истории по типу операции."""
    owner, source, _, expense, income = records
    service = transaction_service(session)

    expense_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    income_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("1"), source, income
    )

    result = service.get_history(owner, tx_type=TransactionType.EXPENSE)

    assert [tx.id for tx in result] == [expense_tx.id]
    assert income_tx.id not in [tx.id for tx in result]


def test_history_filters_by_category(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет фильтрацию истории по категории."""
    owner, source, _, expense, income = records
    service = transaction_service(session)

    expense_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    income_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("1"), source, income
    )

    result = service.get_history(owner, category_id=expense)

    assert [tx.id for tx in result] == [expense_tx.id]
    assert income_tx.id not in [tx.id for tx in result]


def test_history_filters_by_account(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет фильтрацию истории по счету."""
    owner, source, target, expense, income = records
    service = transaction_service(session)

    source_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    target_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("1"), target, income
    )

    result = service.get_history(owner, account_id=source)

    assert [tx.id for tx in result] == [source_tx.id]
    assert target_tx.id not in [tx.id for tx in result]


def test_history_combines_multiple_filters(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет совместное применение нескольких фильтров истории."""
    owner, source, target, expense, income = records
    service = transaction_service(session)

    matching_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    wrong_category_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("1"), source, income
    )
    wrong_type_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("1"), source, income
    )
    wrong_account_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), target, expense
    )

    timestamp = datetime(2026, 1, 2, 12, 0)
    for tx in (matching_tx, wrong_category_tx, wrong_type_tx, wrong_account_tx):
        session.execute(
            update(TransactionORM)
            .where(TransactionORM.id == tx.id)
            .values(timestamp=timestamp)
        )

    result = service.get_history(
        owner,
        date_from=datetime(2026, 1, 1).date(),
        date_to=datetime(2026, 1, 3).date(),
        account_id=source,
        category_id=expense,
        tx_type=TransactionType.EXPENSE,
    )

    assert [tx.id for tx in result] == [matching_tx.id]


def test_history_without_filters_returns_all_user_transactions(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет получение всей истории пользователя без фильтров."""
    owner, source, target, expense, income = records
    service = transaction_service(session)

    first_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), source, expense
    )
    second_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("2"), target, income
    )

    result = service.get_history(owner)

    assert [tx.id for tx in result] == [first_tx.id, second_tx.id]


def test_history_returns_empty_list_when_no_transactions_match(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет возврат пустого списка при отсутствии совпадений."""
    owner = records[0]

    result = transaction_service(session).get_history(
        owner,
        date_from=datetime(2026, 1, 1).date(),
        date_to=datetime(2026, 1, 31).date(),
    )

    assert result == []


def test_history_rejects_foreign_account_and_category(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет запрет фильтрации истории по чужому счету и категории."""
    owner = records[0]

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

    with pytest.raises(PermissionError):
        service.get_history(owner, account_id=foreign_account.id)

    with pytest.raises(PermissionError):
        service.get_history(owner, category_id=foreign_category.id)


def test_history_is_available_for_own_archived_account(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет доступность истории собственного архивного счета."""
    owner, source, target, expense, _ = records
    service = transaction_service(session)

    tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("1"), target, expense
    )

    AccountService(SQLAlchemyAccountRepository(session)).archive_account(target, owner)

    result = service.get_history(owner, account_id=target)

    assert [item.id for item in result] == [tx.id]


def test_history_finds_transfer_by_source_account(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет поиск перевода по исходному счету."""
    owner, source, target, _, _ = records
    service = transaction_service(session)

    transfer = service.make_transfer(owner, source, target, Decimal("10"))

    result = service.get_history(owner, account_id=source)

    assert transfer.id in [tx.id for tx in result]


def test_history_finds_transfer_by_target_account(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет поиск перевода по целевому счету."""
    owner, source, target, _, _ = records
    service = transaction_service(session)

    transfer = service.make_transfer(owner, source, target, Decimal("10"))

    result = service.get_history(owner, account_id=target)

    assert transfer.id in [tx.id for tx in result]


def test_reading_history_does_not_change_account_balances(
    session: Session, records: tuple[int, int, int, int, int]
) -> None:
    """Проверяет, что чтение истории не изменяет остатки на счетах."""
    owner, source, target, expense, _ = records
    service = transaction_service(session)

    source_before = SQLAlchemyAccountRepository(session).get_by_id(source)
    target_before = SQLAlchemyAccountRepository(session).get_by_id(target)

    assert source_before is not None
    assert target_before is not None

    source_balance = source_before.balance
    target_balance = target_before.balance

    service.get_history(owner, account_id=source)
    service.get_history(owner, account_id=target)

    source_after = SQLAlchemyAccountRepository(session).get_by_id(source)
    target_after = SQLAlchemyAccountRepository(session).get_by_id(target)

    assert source_after is not None
    assert target_after is not None
    assert source_after.balance == source_balance
    assert target_after.balance == target_balance


def test_cli_uses_same_filters_for_history_and_csv(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Журнал и CSV используют одинаковые фильтры без изменения балансов."""
    owner, source, _, expense_category, income_category = records

    account_repo = SQLAlchemyAccountRepository(session)
    category_repo = SQLAlchemyCategoryRepository(session)
    tx_repo = SQLAlchemyTransactionRepository(session)

    tx_service = transaction_service(session)
    expense_tx = tx_service.register_transaction(
        owner,
        TransactionType.EXPENSE,
        Decimal("12.34"),
        source,
        expense_category,
    )
    income_tx = tx_service.register_transaction(
        owner,
        TransactionType.INCOME,
        Decimal("56.78"),
        source,
        income_category,
    )

    interface = TerminalInterface(
        owner,
        AccountService(account_repo),
        tx_service,
        BudgetService(SQLAlchemyBudgetRepository(session), tx_repo, category_repo),
        CategoryService(category_repo),
        ExportService(account_repo, category_repo),
    )

    session.flush()
    account_before = session.get(AccountORM, source)
    assert account_before is not None
    balance_before = account_before.balance

    answers = iter(["", "", "", "", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    interface._handle_show_history()
    journal_output = capsys.readouterr().out

    monkeypatch.chdir(tmp_path)
    answers = iter(["", "", "", "", "2"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    interface._handle_export_csv()
    export_output = capsys.readouterr().out

    csv_output = (tmp_path / "transactions_export.csv").read_text(encoding="utf-8")

    assert f"#{expense_tx.id}" in journal_output
    assert f"#{income_tx.id}" not in journal_output
    assert "12.34" in journal_output
    assert "12.34" in csv_output
    assert "56.78" not in csv_output
    assert "выгружены" in export_output

    account_after = session.get(AccountORM, source)
    assert account_after is not None
    balance_after = account_after.balance
    assert balance_after == balance_before


@pytest.mark.parametrize("choice", ["5", "7", "8"])
@pytest.mark.parametrize("existing_file", [False, True])
@pytest.mark.parametrize("invalid_filter", ["date", "type", "foreign_account"])
def test_cli_invalid_filters_preserve_csv(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    choice: str,
    existing_file: bool,
    invalid_filter: str,
) -> None:
    """Ошибочные фильтры отменяют просмотр, удаление и экспорт без изменений."""
    owner, source, _, expense, _ = records
    service = transaction_service(session)
    service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("12.34"), source, expense
    )
    balance_before = AccountService(
        SQLAlchemyAccountRepository(session)
    ).calculate_total_capital(owner)
    history_before = service.get_history(owner)
    filters = ["", "", "", "", ""]
    if invalid_filter == "date":
        filters[0] = "2026-02-30"
    elif invalid_filter == "type":
        filters[4] = "4"
    else:
        other = UserMapper.to_orm(
            User(
                0, "Другой", "filter@capitaltracker.local", "!disabled", datetime.now()
            )
        )
        session.add(other)
        session.flush()
        account = AccountService(SQLAlchemyAccountRepository(session)).create_account(
            other.id, "Чужой", AccountType.CASH, Decimal("0")
        )
        filters[2] = str(account.id)

    monkeypatch.chdir(tmp_path)
    csv_path = tmp_path / "transactions_export.csv"
    original = b"previous export\r\n"
    if existing_file:
        csv_path.write_bytes(original)
    answers = iter([choice, *filters])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert application.build_interface(session, owner).run_once()

    output = capsys.readouterr().out
    assert "[!]" in output
    assert "Журнал транзакций:" not in output
    assert "выгружены" not in output
    assert "\\n" not in output
    if existing_file:
        assert csv_path.read_bytes() == original
    else:
        assert not csv_path.exists()
    assert service.get_history(owner) == history_before
    assert (
        AccountService(SQLAlchemyAccountRepository(session)).calculate_total_capital(
            owner
        )
        == balance_before
    )


def test_in_memory_transaction_keyword_arguments() -> None:
    """Проверяет совместимость именованных вызовов с контрактом репозитория."""
    from src.repositories.transaction import InMemoryTransactionRepository

    repository = InMemoryTransactionRepository()
    transaction = Transaction(
        0, 1, TransactionType.EXPENSE, Decimal("1.00"), 1, 1, datetime.now()
    )
    saved = repository.add(transaction=transaction)
    assert repository.get_by_id(transaction_id=saved.id) == saved
    repository.delete(transaction_id=saved.id)
    assert repository.get_by_id(transaction_id=saved.id) is None


def test_export_preserves_previous_file(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """При ошибке записи сохраняет предыдущий CSV-файл."""
    owner = records[0]
    monkeypatch.chdir(tmp_path)
    csv_path = tmp_path / "transactions_export.csv"
    previous_content = b"previous report\\r\\n"
    csv_path.write_bytes(previous_content)
    import tempfile

    original_tempfile = tempfile.NamedTemporaryFile

    class FailingFile:
        def __init__(self, file):
            self.file = file
            self.name = file.name

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def write(self, data):
            self.file.write(data)
            raise OSError("Недостаточно места")

    def failing_tempfile(*args, **kwargs):
        return FailingFile(original_tempfile(*args, **kwargs))

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", failing_tempfile)

    answers = iter(["8", "", "", "", "", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    interface = application.build_interface(session, owner)
    assert interface.run_once()

    output = capsys.readouterr().out
    assert "Не удалось записать CSV" in output
    assert "выгружены" not in output
    assert csv_path.read_bytes() == previous_content


@pytest.mark.parametrize("write_failure", [False, True])
def test_cli_export_handles_file_errors(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    write_failure: bool,
) -> None:
    """Ошибка открытия или записи CSV не прерывает работу меню."""
    import tempfile

    owner = records[0]
    monkeypatch.chdir(tmp_path)
    if write_failure:

        def failing_tempfile(*args, **kwargs):
            raise OSError("Недостаточно места")

        monkeypatch.setattr(tempfile, "NamedTemporaryFile", failing_tempfile)
    else:
        (tmp_path / "transactions_export.csv").mkdir()

    answers = iter(["8", "", "", "", "", "", "0"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    interface = application.build_interface(session, owner)

    assert interface.run_once()
    assert not interface.run_once()
    output = capsys.readouterr().out
    assert "Не удалось записать CSV" in output
    assert "выгружены" not in output


@pytest.mark.parametrize("empty", [False, True])
def test_cli_delete_after_history(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
    empty: bool,
) -> None:
    """Удаление работает после показа истории и отменяется при пустой выборке."""
    owner, source, _, expense, _ = records
    service = transaction_service(session)
    transaction = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("10"), source, expense
    )
    filters = ["", "", "", "", "1" if empty else ""]
    answers = iter(["7", *filters, *([] if empty else [str(transaction.id)])])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert application.build_interface(session, owner).run_once()
    assert bool(service.get_history(owner)) == empty
    account = SQLAlchemyAccountRepository(session).get_by_id(source)
    assert account is not None
    assert account.balance == Decimal("990" if empty else "1000")


def test_cli_delete_rejects_id_outside_selection(
    session: Session,
    records: tuple[int, int, int, int, int],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Запрещает удаление операции, отсутствующей в отфильтрованной истории."""
    owner, source, _, expense, income = records
    service = transaction_service(session)

    expense_tx = service.register_transaction(
        owner, TransactionType.EXPENSE, Decimal("10"), source, expense
    )
    income_tx = service.register_transaction(
        owner, TransactionType.INCOME, Decimal("20"), source, income
    )

    history_before = service.get_history(owner)
    assert {tx.id for tx in history_before} == {expense_tx.id, income_tx.id}
    account = SQLAlchemyAccountRepository(session).get_by_id(source)
    assert account is not None
    balance_before = account.balance

    answers = iter(["7", "", "", "", "", "2", str(income_tx.id)])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    application.build_interface(session, owner).run_once()

    history_after = service.get_history(owner)
    account_after = SQLAlchemyAccountRepository(session).get_by_id(source)

    assert {tx.id for tx in history_after} == {
        expense_tx.id,
        income_tx.id,
    }
    assert account_after is not None
    assert account_after.balance == balance_before
