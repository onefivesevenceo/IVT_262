"""Настройки подключения приложения и Alembic к одной базе данных."""

import os

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://capitaltracker:capitaltracker@localhost:5432/capitaltracker"
)


class Settings:
    """Настройки, читаемые из переменных окружения без дополнительных пакетов."""

    def __init__(self) -> None:
        """Читает строку подключения из окружения или использует учебную БД."""
        self.database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


settings = Settings()
