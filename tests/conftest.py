"""Тестовая PostgreSQL: схема через Alembic, изоляция данных транзакциями."""

import os
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from src.database.mappers import UserMapper
from src.models.account import AccountType
from src.models.user import User
from src.repositories.sqlalchemy import (
    SQLAlchemyAccountRepository,
    SQLAlchemyCategoryRepository,
)
from src.services.account import AccountService
from src.services.category import CategoryService

DEFAULT_TEST_URL = "postgresql+psycopg://capitaltracker:capitaltracker@localhost:5432/capitaltracker_test"


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Применяет миграции исключительно к отдельной базе с суффиксом _test."""
    url = os.getenv("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    database = make_url(url).database
    if database is None or not database.endswith("_test"):
        msg = "TEST_DATABASE_URL должен указывать на отдельную базу с суффиксом _test."
        raise ValueError(msg)
    test_engine = create_engine(url)
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with test_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Откатывает все данные теста, включая вложенные commit и ошибки записи."""
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        ) as test_session:
            yield test_session
        transaction.rollback()


@pytest.fixture
def records(session: Session) -> tuple[int, int, int, int, int]:
    """Создает владельца, два счета и расходную с доходной категории."""
    user = UserMapper.to_orm(
        User(0, "Тест", "test@capitaltracker.local", "!disabled", datetime.now())
    )
    session.add(user)
    session.flush()
    category_service = CategoryService(SQLAlchemyCategoryRepository(session))
    category_service.seed_defaults(user.id)
    categories = category_service.get_user_categories(user.id)
    accounts = AccountService(SQLAlchemyAccountRepository(session))
    source = accounts.create_account(
        user.id, "Карта", AccountType.DEBIT, Decimal("1000")
    )
    target = accounts.create_account(
        user.id, "Наличные", AccountType.CASH, Decimal("500")
    )
    return user.id, source.id, target.id, categories[0].id, categories[2].id
