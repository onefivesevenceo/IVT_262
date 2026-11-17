"""Подключение Alembic к общей метаинформации и настройкам проекта."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, create_engine
from sqlalchemy.pool import NullPool

from src.configs.settings import settings
from src.database import models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = models.Base.metadata


def run_migrations_offline() -> None:
    """Формирует SQL миграций без подключения к серверу."""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def migrate_connection(connection: Connection) -> None:
    """Применяет миграции через переданное подключение."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Подключается к БД или использует подключение тестового окружения."""
    connection = config.attributes.get("connection")
    if isinstance(connection, Connection):
        migrate_connection(connection)
        return
    engine = create_engine(settings.database_url, poolclass=NullPool)
    try:
        with engine.connect() as connection:
            migrate_connection(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
