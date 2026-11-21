# Тема: «Проектирование базы данных CapitalTracker и адаптация консольного прототипа с использованием SQLAlchemy и Alembic»

**Команда проекта (гр. ИВТ-262):**
* **Павловский Иван Юрьевич** — Team Lead, архитектура ядра, реализация моделей и сервисов
* **Ларченко Иван Михайлович** — консольный интерфейс (CLI), интеграция модулей, тестирование

---

## 1. Подготовка проекта и управление зависимостями (uv)

### 1.1. Цель и порядок разработки

Выполнен переход консольного CapitalTracker от InMemory-хранилищ к PostgreSQL. Применен порядок DB-First: определены таблицы, связи и ограничения по доменным сущностям, схема перенесена в ORM-модели, создана и применена миграция, затем подключены репозитории и адаптирована сборка CLI.

Веб-интерфейс, авторизация и интеграции с банками в лабораторную № 4 не включены. Интерфейс сохраняет девять действий и выход.

Изучен [методический конспект лабораторной № 4](https://gist.github.com/Tamerlan91011/8c9f81979009bbffe1f3ce8b7e92fad6). Из него применены общий `Base`, миграции как способ создания схемы и передача одной сессии участвующим репозиториям без самостоятельных `commit()`. Дополнительно выполнен пункт задания о классах-мапперах доменных датаклассов.

### 1.2. Зависимости

SQLAlchemy и Alembic уже присутствовали в проекте. Для подключения к PostgreSQL добавлен драйвер:

```bash
uv add "psycopg[binary]>=3.2.0"
```

При проверке использовались SQLAlchemy 2.1.4, Alembic 1.20.0 и Psycopg 3.3.9; разрешенные версии зафиксированы в `uv.lock`. Дополнительные библиотеки настроек и инфраструктурные сервисы не подключались.

### 1.3. Файл конфигурации `pyproject.toml`

```toml
[project]
name = "capital-tracker"
version = "0.1.0"
description = "Система мониторинга денежных потоков, категоризации расходов и планирования бюджета"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "alembic>=1.13.0",
    "fastapi>=0.110.0",
    "psycopg[binary]>=3.2.0",
    "pydantic>=2.6.0",
    "sqlalchemy>=2.0.0",
]

[project.scripts]
capital-tracker = "src.main:main"

[build-system]
requires = ["uv_build>=0.13.1,<0.14.0"]
build-backend = "uv_build"

[tool.uv.build-backend]
module-name = "src"
module-root = "."

[dependency-groups]
dev = [
    "mypy>=1.9.0",
    "pytest>=8.0.0",
    "ruff>=0.3.0",
]

[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "A", "C4", "SIM"]
ignore = []

[tool.mypy]
python_version = "3.11"
strict = true
ignore_missing_imports = true
```

### 1.4. Исключение локальных и сгенерированных файлов из Git

Проверено, что окружение, секреты, кэши и результаты сборки не отслеживаются. Миграции, тесты, Compose и lock-файл сохраняются в Git. Данные PostgreSQL находятся в Docker-томе за пределами репозитория.

#### `.gitignore`

```gitignore
# macOS и IDE
.DS_Store
.idea/

# Окружение и локальные настройки
.venv/
.env
.env.*
!.env.example

# Python и инструменты проверки
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/

# Результаты сборки и экспорта
build/
dist/
*.egg-info/
transactions_export.csv
```

---

## 2. Структура проекта и схема БД

### 2.1. Добавленные компоненты

```text
capital-tracker/
├── docker-compose.yaml            <-- PostgreSQL 15, постоянный том, healthcheck
├── alembic.ini                    <-- Настройки миграций
├── migrations/
│   ├── env.py                     <-- Общая metadata и подключение к БД
│   ├── script.py.mako             <-- Шаблон ревизий
│   └── versions/                  <-- Начальная миграция схемы
├── docs/
│   ├── er.md                      <-- ER-диаграмма и таблица ограничений
│   └── laba_4.md                   <-- Текущий отчет
├── tests/
│   ├── conftest.py                <-- Отдельная PostgreSQL и схема через Alembic
│   └── test_database.py           <-- Приемочные проверки
└── src/
    ├── configs/settings.py        <-- DATABASE_URL из окружения
    ├── database/
    │   ├── base.py                <-- Общий DeclarativeBase
    │   ├── models.py              <-- Пять ORM-моделей
    │   ├── mappers.py             <-- Датаклассы ↔ ORM
    │   └── session.py             <-- Engine и фабрика Session
    ├── repositories/             <-- ABC, InMemory и SQLAlchemy по сущностям
    ├── services/money.py          <-- Конечность, диапазон и точность денег
    ├── cli/terminal_interface.py  <-- Одна команда за вызов run_once
    └── main.py                    <-- DI и граница транзакции команды
```

Доменные датаклассы и ABC-контракты сохранены. Старые InMemory-реализации остаются в исходниках, но в штатной DI-сборке не используются.

### 2.2. ER-диаграмма

Полная схема с атрибутами, ключами, индексами и ограничениями размещена в [docs/er.md](er.md).

```mermaid
erDiagram
    USERS ||--o{ ACCOUNTS : owns
    USERS ||--o{ CATEGORIES : owns
    USERS ||--o{ TRANSACTIONS : records
    USERS ||--o{ BUDGET_LIMITS : sets
    ACCOUNTS ||--o{ TRANSACTIONS : source
    ACCOUNTS |o--o{ TRANSACTIONS : transfer_target
    CATEGORIES |o--o{ TRANSACTIONS : classifies
    CATEGORIES ||--o{ BUDGET_LIMITS : limits

    USERS {
        int id PK
        varchar username
        varchar email UK
        varchar password_hash
        timestamp created_at
    }
    ACCOUNTS {
        int id PK
        int user_id FK
        varchar name
        varchar account_type
        numeric balance
        boolean is_archived
    }
    CATEGORIES {
        int id PK
        int user_id FK
        varchar name
        varchar direction
    }
    TRANSACTIONS {
        int id PK
        int user_id FK
        varchar transaction_type
        numeric amount
        int account_id FK
        int category_id FK "NULL только для TRANSFER"
        timestamp timestamp
        int to_account_id FK "NULL для INCOME и EXPENSE"
    }
    BUDGET_LIMITS {
        int id PK
        int user_id FK
        int category_id FK
        int month
        int year
        numeric limit_amount
    }
```

### 2.3. Обоснование M:N и каскадов

Связь «счета — категории» реализована через `transactions`: по одному счету проходят операции разных категорий, одна категория встречается на разных счетах. Операция выступает объектом связи с суммой, типом и датой. Повторные операции одной пары допустимы, каждая имеет свой PK.

`AccountORM.categories` и `CategoryORM.accounts` используют `secondary`, `back_populates`, `viewonly=True`. Они показывают фактические связи из истории, не создают записи сами и не требуют введения меток или других новых сущностей. После изменения операций в той же сессии коллекции перечитываются через `Session.expire`; новая сессия также читает актуальные данные. Такой вариант совместного использования объекта связи и доступа M:N описан в [SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html#combining-association-object-with-many-to-many-access-patterns).

Все FK используют `ON DELETE RESTRICT`. ORM не удаляет историю и не обнуляет FK: у родительских коллекций установлено `passive_deletes="all"`, включая случай уже загруженных коллекций. Счета переводятся в архив, а их операции остаются доступны для просмотра и отмены.

### 2.4. Точность денег и изоляция владельцев

Денежные колонки имеют тип `NUMERIC(18, 2)`, в доменных объектах используется `Decimal`. Сервисы проверяют конечность, положительность суммы операции или лимита, допустимый диапазон и отсутствие дробных копеек. Сумма `0.005` отклоняется, а не округляется отдельно на двух счетах. Начальный баланс может быть отрицательным.

Ограничения БД дополнительно отклоняют некорректные суммы и `NaN`; бесконечность не помещается в выбранный `NUMERIC`. Составные FK включают `user_id`, поэтому нельзя записать операцию или лимит со ссылкой на чужой счет либо категорию даже в обход сервисов. Соответствие направления категории типу операции проверяется в сервисном слое.

Время хранится без часового пояса, как в предыдущем прототипе; периоды бюджетов используют локальное время приложения.

---

## 3. Архитектура и принципы SOLID

* **SRP:** ORM-модели описывают хранение, мапперы выполняют преобразование, репозитории работают с сессией, сервисы проверяют бизнес-правила, CLI читает ввод и выводит результат.
* **OCP и DIP:** SQLAlchemy-репозитории реализуют прежние ABC-контракты; сервисы не импортируют ORM или `Session`.
* **LSP и ISP:** сохраняются специализированные контракты счетов, категорий, операций и лимитов; новая реализация возвращает те же доменные типы.

`main.py` создает одну сессию на команду через `SessionFactory.begin()` и передает ее всем репозиториям. Репозитории выполняют `flush()`, но не `commit()`. Исключения из обработчиков выходят за границу контекста транзакции, после отката выводится ошибка. Это обеспечивает совместный откат остатков и журнала при сбое записи. Управление транзакциями основано на [контекстах SQLAlchemy](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#managing-transactions).

При старте повторяемо создается один учебный профиль CLI по email `cli@capitaltracker.local`, ID выдает база. Категории создаются только при отсутствии категорий пользователя. `!disabled` — маркер отключенного входа, а не хэш реального пароля: аутентификация в этой версии отсутствует.

---

## 4. Реализация программных компонентов

Листинги ниже скопированы из фактических файлов. Все классы и функции имеют русские docstrings; комментарии внутри функций отсутствуют.

### 4.1. Настройки и фабрика сессий

#### `src/configs/settings.py`

```python
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
```

#### `src/database/base.py`

```python
"""Общая метаинформация таблиц и соглашение об именовании ограничений."""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Единая декларативная база всех ORM-моделей CapitalTracker."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

#### `src/database/session.py`

```python
"""Движок и фабрика коротких сессий без создания таблиц."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.configs.settings import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
```

### 4.2. ORM-модели и мапперы

#### `src/database/models.py`

```python
"""Текущее состояние схемы БД, создаваемой миграциями Alembic."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base as Base
from src.models.account import AccountType
from src.models.category import CategoryDirection
from src.models.transaction import TransactionType


class UserORM(Base):
    """Пользователь, которому принадлежат финансовые данные."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime)

    accounts: Mapped[list["AccountORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    categories: Mapped[list["CategoryORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    transactions: Mapped[list["TransactionORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )
    budget_limits: Mapped[list["BudgetLimitORM"]] = relationship(
        back_populates="user", passive_deletes="all"
    )

    __table_args__ = (
        CheckConstraint("length(trim(username)) > 0", name="username_not_blank"),
    )


class AccountORM(Base):
    """Счет с точным остатком и логическим архивированием."""

    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    account_type: Mapped[AccountType] = mapped_column(
        Enum(
            AccountType, native_enum=False, create_constraint=True, name="account_type"
        )
    )
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    user: Mapped[UserORM] = relationship(back_populates="accounts")
    transactions: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        foreign_keys="TransactionORM.account_id",
        back_populates="account",
        passive_deletes="all",
    )
    incoming_transfers: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.to_account_id",
        foreign_keys="TransactionORM.to_account_id",
        back_populates="to_account",
        passive_deletes="all",
    )
    categories: Mapped[list["CategoryORM"]] = relationship(
        secondary="transactions",
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        secondaryjoin="CategoryORM.id == TransactionORM.category_id",
        back_populates="accounts",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
        CheckConstraint(
            "balance > -10000000000000000 AND balance < 10000000000000000",
            name="balance_finite",
        ),
    )


class CategoryORM(Base):
    """Категория операций, принадлежащая одному пользователю."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    direction: Mapped[CategoryDirection] = mapped_column(
        Enum(
            CategoryDirection,
            native_enum=False,
            create_constraint=True,
            name="category_direction",
        )
    )

    user: Mapped[UserORM] = relationship(back_populates="categories")
    transactions: Mapped[list["TransactionORM"]] = relationship(
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        foreign_keys="TransactionORM.category_id",
        back_populates="category",
        passive_deletes="all",
    )
    budget_limits: Mapped[list["BudgetLimitORM"]] = relationship(
        primaryjoin="CategoryORM.id == BudgetLimitORM.category_id",
        foreign_keys="BudgetLimitORM.category_id",
        back_populates="category",
        passive_deletes="all",
    )
    accounts: Mapped[list[AccountORM]] = relationship(
        secondary="transactions",
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        secondaryjoin="AccountORM.id == TransactionORM.account_id",
        back_populates="categories",
        viewonly=True,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "id"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_blank"),
    )


class TransactionORM(Base):
    """Операция и объект связи счета с категорией, включая сумму и дату."""

    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            native_enum=False,
            create_constraint=True,
            name="transaction_type",
        )
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_id: Mapped[int] = mapped_column(index=True)
    category_id: Mapped[int | None] = mapped_column(index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime)
    to_account_id: Mapped[int | None] = mapped_column(index=True)

    user: Mapped[UserORM] = relationship(back_populates="transactions")
    account: Mapped[AccountORM] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.account_id",
        foreign_keys=[account_id],
        back_populates="transactions",
    )
    to_account: Mapped[AccountORM | None] = relationship(
        primaryjoin="AccountORM.id == TransactionORM.to_account_id",
        foreign_keys=[to_account_id],
        back_populates="incoming_transfers",
    )
    category: Mapped[CategoryORM | None] = relationship(
        primaryjoin="CategoryORM.id == TransactionORM.category_id",
        foreign_keys=[category_id],
        back_populates="transactions",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_account",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "to_account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_target",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_transactions_owner_category",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "amount > 0 AND amount < 10000000000000000", name="amount_positive_finite"
        ),
        CheckConstraint(
            "(transaction_type = 'TRANSFER' AND to_account_id IS NOT NULL "
            "AND to_account_id <> account_id AND category_id IS NULL) OR "
            "(transaction_type IN ('INCOME', 'EXPENSE') "
            "AND category_id IS NOT NULL AND to_account_id IS NULL)",
            name="operation_fields",
        ),
    )


class BudgetLimitORM(Base):
    """Единственный лимит категории пользователя на календарный месяц."""

    __tablename__ = "budget_limits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int] = mapped_column(index=True)
    month: Mapped[int] = mapped_column()
    year: Mapped[int] = mapped_column()
    limit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))

    user: Mapped[UserORM] = relationship(back_populates="budget_limits")
    category: Mapped[CategoryORM] = relationship(
        primaryjoin="CategoryORM.id == BudgetLimitORM.category_id",
        foreign_keys=[category_id],
        back_populates="budget_limits",
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_budget_limits_owner_category",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "user_id", "category_id", "month", "year", name="uq_budget_period"
        ),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_range"),
        CheckConstraint("year BETWEEN 1970 AND 2100", name="year_range"),
        CheckConstraint(
            "limit_amount > 0 AND limit_amount < 10000000000000000",
            name="limit_positive_finite",
        ),
    )
```

#### `src/database/mappers.py`

```python
"""Явное преобразование между доменными датаклассами и ORM-моделями."""

from src.database.models import (
    AccountORM,
    BudgetLimitORM,
    CategoryORM,
    TransactionORM,
    UserORM,
)
from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction
from src.models.user import User


class UserMapper:
    """Преобразователь учетной записи без передачи ORM в доменный слой."""

    @staticmethod
    def to_domain(row: UserORM) -> User:
        """Создает неизменяемую доменную учетную запись."""
        return User(row.id, row.username, row.email, row.password_hash, row.created_at)

    @staticmethod
    def to_orm(entity: User) -> UserORM:
        """Создает ORM-запись, оставляя новый ID генератору базы."""
        row = UserORM(
            username=entity.username,
            email=entity.email,
            password_hash=entity.password_hash,
            created_at=entity.created_at,
        )
        if entity.id:
            row.id = entity.id
        return row


class AccountMapper:
    """Преобразователь счета и его точного денежного остатка."""

    @staticmethod
    def to_domain(row: AccountORM) -> Account:
        """Создает доменный счет из сохраненной записи."""
        return Account(
            row.id,
            row.user_id,
            row.name,
            row.account_type,
            row.balance,
            row.is_archived,
        )

    @staticmethod
    def to_orm(entity: Account) -> AccountORM:
        """Создает ORM-счет из доменного объекта."""
        row = AccountORM(
            user_id=entity.user_id,
            name=entity.name,
            account_type=entity.account_type,
            balance=entity.balance,
            is_archived=entity.is_archived,
        )
        if entity.id:
            row.id = entity.id
        return row


class CategoryMapper:
    """Преобразователь неизменяемой категории доходов или расходов."""

    @staticmethod
    def to_domain(row: CategoryORM) -> Category:
        """Возвращает категорию, не зависящую от сессии SQLAlchemy."""
        return Category(row.id, row.user_id, row.name, row.direction)

    @staticmethod
    def to_orm(entity: Category) -> CategoryORM:
        """Создает ORM-категорию из датакласса."""
        row = CategoryORM(
            user_id=entity.user_id, name=entity.name, direction=entity.direction
        )
        if entity.id:
            row.id = entity.id
        return row


class TransactionMapper:
    """Преобразователь финансовой операции, включая межбалансовый перевод."""

    @staticmethod
    def to_domain(row: TransactionORM) -> Transaction:
        """Создает неизменяемую доменную операцию."""
        return Transaction(
            row.id,
            row.user_id,
            row.transaction_type,
            row.amount,
            row.account_id,
            row.category_id,
            row.timestamp,
            row.to_account_id,
        )

    @staticmethod
    def to_orm(entity: Transaction) -> TransactionORM:
        """Создает запись журнала из доменной операции."""
        row = TransactionORM(
            user_id=entity.user_id,
            transaction_type=entity.transaction_type,
            amount=entity.amount,
            account_id=entity.account_id,
            category_id=entity.category_id,
            timestamp=entity.timestamp,
            to_account_id=entity.to_account_id,
        )
        if entity.id:
            row.id = entity.id
        return row


class BudgetLimitMapper:
    """Преобразователь месячного бюджетного лимита."""

    @staticmethod
    def to_domain(row: BudgetLimitORM) -> BudgetLimit:
        """Создает доменный лимит из записи базы данных."""
        return BudgetLimit(
            row.id,
            row.user_id,
            row.category_id,
            row.month,
            row.year,
            row.limit_amount,
        )

    @staticmethod
    def to_orm(entity: BudgetLimit) -> BudgetLimitORM:
        """Создает ORM-лимит, не изменяя исходный датакласс."""
        row = BudgetLimitORM(
            user_id=entity.user_id,
            category_id=entity.category_id,
            month=entity.month,
            year=entity.year,
            limit_amount=entity.limit_amount,
        )
        if entity.id:
            row.id = entity.id
        return row
```

### 4.3. Репозитории SQLAlchemy

#### `src/repositories/account.py`

```python
from abc import ABC, abstractmethod
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import AccountMapper
from src.database.models import AccountORM
from src.models.account import Account


class AccountRepository(ABC):
    """Абстрактный контракт взаимодействия с хранилищем счетов."""

    @abstractmethod
    def add(self, account: Account) -> Account:
        """Добавляет счет в хранилище."""

    @abstractmethod
    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет по его идентификатору."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает все активные счета пользователя."""

    @abstractmethod
    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Обновляет текущий остаток счета."""

    @abstractmethod
    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный."""


class InMemoryAccountRepository(AccountRepository):
    """Хранилище счетов в оперативной памяти."""

    def __init__(self) -> None:
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[int, Account] = {}
        self._seq: int = 1

    def add(self, account: Account) -> Account:
        """Добавляет счет в оперативную память."""
        saved = Account(
            id=self._seq,
            user_id=account.user_id,
            name=account.name,
            account_type=account.account_type,
            balance=account.balance,
            is_archived=account.is_archived,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет по его идентификатору."""
        return self._storage.get(account_id)

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает все активные (не архивные) счета пользователя."""
        return [
            acc
            for acc in self._storage.values()
            if acc.user_id == user_id and not acc.is_archived
        ]

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Обновляет остаток счета. Если не найден — выбрасывает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для обновления баланса."
            raise ValueError(msg)
        account.balance = new_balance

    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный. Если не найден — выбрасывает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для архивации."
            raise ValueError(msg)
        account.is_archived = True


class SQLAlchemyAccountRepository(AccountRepository):
    """Хранилище счетов без самостоятельной фиксации транзакций."""

    def __init__(self, session: Session) -> None:
        """Принимает общую сессию текущей прикладной операции."""
        self._session = session

    def add(self, account: Account) -> Account:
        """Сохраняет счет и возвращает датакласс с присвоенным ID."""
        row = AccountMapper.to_orm(account)
        self._session.add(row)
        self._session.flush()
        return AccountMapper.to_domain(row)

    def get_by_id(self, account_id: int) -> Account | None:
        """Возвращает счет, включая архивный для сохранения истории."""
        row = self._session.get(AccountORM, account_id)
        return AccountMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Account]:
        """Возвращает активные счета владельца в порядке создания."""
        query = (
            select(AccountORM)
            .where(AccountORM.user_id == user_id, AccountORM.is_archived.is_(False))
            .order_by(AccountORM.id)
        )
        return [AccountMapper.to_domain(row) for row in self._session.scalars(query)]

    def update_balance(self, account_id: int, new_balance: Decimal) -> None:
        """Меняет остаток без commit; отсутствие счета является ошибкой."""
        row = self._session.get(AccountORM, account_id)
        if row is None:
            msg = "Счет не найден для обновления баланса."
            raise ValueError(msg)
        row.balance = new_balance
        self._session.flush()

    def archive(self, account_id: int) -> None:
        """Архивирует счет, сохраняя связанные операции."""
        row = self._session.get(AccountORM, account_id)
        if row is None:
            msg = "Счет не найден для архивации."
            raise ValueError(msg)
        row.is_archived = True
        self._session.flush()
```

#### `src/repositories/category.py`

```python
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import CategoryMapper
from src.database.models import CategoryORM
from src.models.category import Category


class CategoryRepository(ABC):
    """Абстрактный контракт управления справочником категорий."""

    @abstractmethod
    def add(self, category: Category) -> Category:
        """Добавляет категорию."""

    @abstractmethod
    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает список категорий пользователя."""


class InMemoryCategoryRepository(CategoryRepository):
    """Хранилище категорий классификации операций в оперативной памяти."""

    def __init__(self) -> None:
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[int, Category] = {}
        self._seq: int = 1

    def add(self, category: Category) -> Category:
        """Добавляет категорию в память."""
        saved = Category(
            id=self._seq,
            user_id=category.user_id,
            name=category.name,
            direction=category.direction,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по ID."""
        return self._storage.get(category_id)

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает список категорий пользователя."""
        return [cat for cat in self._storage.values() if cat.user_id == user_id]


class SQLAlchemyCategoryRepository(CategoryRepository):
    """Хранилище категорий с преобразованием записей в датаклассы."""

    def __init__(self, session: Session) -> None:
        """Принимает сессию от вызывающего кода."""
        self._session = session

    def add(self, category: Category) -> Category:
        """Сохраняет категорию без фиксации внешней транзакции."""
        row = CategoryMapper.to_orm(category)
        self._session.add(row)
        self._session.flush()
        return CategoryMapper.to_domain(row)

    def get_by_id(self, category_id: int) -> Category | None:
        """Находит категорию по первичному ключу."""
        row = self._session.get(CategoryORM, category_id)
        return CategoryMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Category]:
        """Возвращает категории владельца в порядке создания."""
        query = (
            select(CategoryORM)
            .where(CategoryORM.user_id == user_id)
            .order_by(CategoryORM.id)
        )
        return [CategoryMapper.to_domain(row) for row in self._session.scalars(query)]
```

#### `src/repositories/transaction.py`

```python
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import TransactionMapper
from src.database.models import TransactionORM
from src.models.transaction import Transaction


class TransactionRepository(ABC):
    """Абстрактный контракт взаимодействия с журналом транзакций."""

    @abstractmethod
    def add(self, transaction: Transaction) -> Transaction:
        """Сохраняет новую транзакцию."""

    @abstractmethod
    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по идентификатору."""

    @abstractmethod
    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает все операции конкретного пользователя."""

    @abstractmethod
    def delete(self, transaction_id: int) -> None:
        """Удаляет операцию из журнала."""


class InMemoryTransactionRepository(TransactionRepository):
    """Хранилище транзакций в оперативной памяти."""

    def __init__(self) -> None:
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[int, Transaction] = {}
        self._seq: int = 1

    def add(self, transaction: Transaction) -> Transaction:
        """Сохраняет транзакцию в памяти."""
        saved = Transaction(
            id=self._seq,
            user_id=transaction.user_id,
            transaction_type=transaction.transaction_type,
            amount=transaction.amount,
            account_id=transaction.account_id,
            category_id=transaction.category_id,
            timestamp=transaction.timestamp,
            to_account_id=transaction.to_account_id,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает транзакцию по ее номеру."""
        return self._storage.get(transaction_id)

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает историю операций пользователя."""
        return [tx for tx in self._storage.values() if tx.user_id == user_id]

    def delete(self, transaction_id: int) -> None:
        """Удаляет запись транзакции по первичному ключу."""
        self._storage.pop(transaction_id, None)


class SQLAlchemyTransactionRepository(TransactionRepository):
    """Хранилище операций в той же транзакции, что и изменения балансов."""

    def __init__(self, session: Session) -> None:
        """Принимает общую сессию счетов и журнала операций."""
        self._session = session

    def add(self, transaction: Transaction) -> Transaction:
        """Добавляет запись журнала и получает ее ID через flush."""
        row = TransactionMapper.to_orm(transaction)
        self._session.add(row)
        self._session.flush()
        return TransactionMapper.to_domain(row)

    def get_by_id(self, transaction_id: int) -> Transaction | None:
        """Возвращает операцию либо None без передачи ORM наружу."""
        row = self._session.get(TransactionORM, transaction_id)
        return TransactionMapper.to_domain(row) if row is not None else None

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает журнал владельца в прежнем порядке добавления."""
        query = (
            select(TransactionORM)
            .where(TransactionORM.user_id == user_id)
            .order_by(TransactionORM.id)
        )
        return [
            TransactionMapper.to_domain(row) for row in self._session.scalars(query)
        ]

    def delete(self, transaction_id: int) -> None:
        """Удаляет запись в рамках общей транзакции отката остатков."""
        row = self._session.get(TransactionORM, transaction_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()
```

#### `src/repositories/budget.py`

```python
from abc import ABC, abstractmethod

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.mappers import BudgetLimitMapper
from src.database.models import BudgetLimitORM
from src.models.budget import BudgetLimit


class BudgetRepository(ABC):
    """Абстрактный контракт управления лимитами бюджетов."""

    @abstractmethod
    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает или обновляет лимит."""

    @abstractmethod
    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит на указанный период."""


class InMemoryBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов бюджетов в оперативной памяти."""

    def __init__(self) -> None:
        """Создает пустое хранилище и последовательность идентификаторов."""
        self._storage: dict[str, BudgetLimit] = {}
        self._seq: int = 1

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Устанавливает или перезаписывает лимит."""
        key = f"{budget.user_id}:{budget.category_id}:{budget.month}:{budget.year}"
        saved = BudgetLimit(
            id=self._seq,
            user_id=budget.user_id,
            category_id=budget.category_id,
            month=budget.month,
            year=budget.year,
            limit_amount=budget.limit_amount,
        )
        self._storage[key] = saved
        self._seq += 1
        return saved

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит по ключу периода."""
        key = f"{user_id}:{category_id}:{month}:{year}"
        return self._storage.get(key)


class SQLAlchemyBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов с заменой суммы без смены ID."""

    def __init__(self, session: Session) -> None:
        """Принимает сессию текущей операции."""
        self._session = session

    def set_limit(self, budget: BudgetLimit) -> BudgetLimit:
        """Добавляет лимит или меняет существующий по ключу периода."""
        row = self._find_row(
            budget.user_id, budget.category_id, budget.month, budget.year
        )
        if row is None:
            row = BudgetLimitMapper.to_orm(budget)
            self._session.add(row)
        else:
            row.limit_amount = budget.limit_amount
        self._session.flush()
        return BudgetLimitMapper.to_domain(row)

    def get_limit(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimit | None:
        """Возвращает лимит указанной категории, владельца и периода."""
        row = self._find_row(user_id, category_id, month, year)
        return BudgetLimitMapper.to_domain(row) if row is not None else None

    def _find_row(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> BudgetLimitORM | None:
        """Находит ORM-запись по уникальному ключу бюджетного периода."""
        return self._session.scalar(
            select(BudgetLimitORM).where(
                BudgetLimitORM.user_id == user_id,
                BudgetLimitORM.category_id == category_id,
                BudgetLimitORM.month == month,
                BudgetLimitORM.year == year,
            )
        )
```

#### `src/repositories/__init__.py`

```python
from src.repositories.account import (
    AccountRepository,
    InMemoryAccountRepository,
    SQLAlchemyAccountRepository,
)
from src.repositories.budget import (
    BudgetRepository,
    InMemoryBudgetRepository,
    SQLAlchemyBudgetRepository,
)
from src.repositories.category import (
    CategoryRepository,
    InMemoryCategoryRepository,
    SQLAlchemyCategoryRepository,
)
from src.repositories.transaction import (
    InMemoryTransactionRepository,
    SQLAlchemyTransactionRepository,
    TransactionRepository,
)

__all__ = [
    "AccountRepository",
    "BudgetRepository",
    "CategoryRepository",
    "InMemoryAccountRepository",
    "InMemoryBudgetRepository",
    "InMemoryCategoryRepository",
    "InMemoryTransactionRepository",
    "SQLAlchemyAccountRepository",
    "SQLAlchemyBudgetRepository",
    "SQLAlchemyCategoryRepository",
    "SQLAlchemyTransactionRepository",
    "TransactionRepository",
]
```

### 4.4. Сервисный слой

#### `src/services/money.py`

```python
"""Проверка денежных значений перед сохранением в NUMERIC(18, 2)."""

from decimal import Decimal

MAX_MONEY = Decimal("9999999999999999.99")
CENT = Decimal("0.01")


def validate_money(value: Decimal, *, positive: bool = False) -> None:
    """Проверяет конечность, диапазон и точность до копеек без округления."""
    if not value.is_finite():
        msg = "Денежное значение должно быть конечным числом."
        raise ValueError(msg)
    if positive and value <= Decimal("0.00"):
        msg = "Сумма должна быть строго положительной."
        raise ValueError(msg)
    if value < -MAX_MONEY or value > MAX_MONEY:
        msg = "Сумма выходит за диапазон NUMERIC(18, 2)."
        raise ValueError(msg)
    if value != value.quantize(CENT):
        msg = "Сумма должна быть указана с точностью до копеек."
        raise ValueError(msg)
```

#### `src/services/account.py`

```python
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
```

#### `src/services/category.py`

```python
from src.models.category import Category, CategoryDirection
from src.repositories.category import CategoryRepository


class CategoryService:
    """Сервис управления категориями доходов и расходов."""

    def __init__(self, category_repo: CategoryRepository) -> None:
        """Получает абстрактное хранилище категорий."""
        self._repo = category_repo

    def seed_defaults(self, user_id: int) -> None:
        """Инициализирует базовые категории для пользователя."""
        existing = self._repo.get_all_by_user(user_id)
        if not existing:
            self._repo.add(Category(0, user_id, "Продукты", CategoryDirection.EXPENSE))
            self._repo.add(Category(0, user_id, "Кафе", CategoryDirection.EXPENSE))
            self._repo.add(Category(0, user_id, "Зарплата", CategoryDirection.INCOME))

    def get_user_categories(self, user_id: int) -> list[Category]:
        """Возвращает все доступные категории пользователя."""
        return self._repo.get_all_by_user(user_id)

    def get_categories_by_direction(
        self, user_id: int, direction: CategoryDirection
    ) -> list[Category]:
        """Возвращает категории пользователя, отфильтрованные по направлению."""
        return [
            cat
            for cat in self._repo.get_all_by_user(user_id)
            if cat.direction == direction
        ]

    def get_by_id(self, category_id: int, user_id: int) -> Category | None:
        """Возвращает категорию владельца, запрещая доступ к чужим данным."""
        category = self._repo.get_by_id(category_id)
        if category is not None and category.user_id != user_id:
            msg = "Доступ к категории запрещен."
            raise PermissionError(msg)
        return category
```

#### `src/services/transaction.py`

```python
from datetime import date, datetime
from decimal import Decimal

from src.models.category import CategoryDirection
from src.models.transaction import Transaction, TransactionType
from src.repositories.account import AccountRepository
from src.repositories.category import CategoryRepository
from src.repositories.transaction import TransactionRepository
from src.services.money import validate_money


class TransactionService:
    """Сервис регистрации операций, атомарных переводов и отката балансов."""

    def __init__(
        self,
        tx_repo: TransactionRepository,
        account_repo: AccountRepository,
        category_repo: CategoryRepository,
    ) -> None:
        """Получает репозитории одной прикладной транзакции."""
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
        validate_money(amount, positive=True)

        account = self._account_repo.get_by_id(account_id)
        if not account or account.user_id != user_id:
            msg = "Указанный счет не существует или принадлежит другому пользователю."
            raise PermissionError(msg)

        if account.is_archived:
            msg = "Нельзя проводить новые операции по архивному счету."
            raise ValueError(msg)

        if category_id is None:
            msg = "Для дохода или расхода необходимо указать категорию."
            raise ValueError(msg)

        category = self._category_repo.get_by_id(category_id)
        if not category or category.user_id != user_id:
            msg = "Категория не найдена или принадлежит другому пользователю."
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
        validate_money(amount, positive=True)

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

        if source.is_archived or target.is_archived:
            msg = "Нельзя выполнять новый перевод с участием архивного счета."
            raise ValueError(msg)

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
        if account.user_id != user_id:
            msg = "Доступ к связанному счету запрещен."
            raise PermissionError(msg)

        if tx.transaction_type == TransactionType.EXPENSE:
            self._account_repo.update_balance(account.id, account.balance + tx.amount)
        elif tx.transaction_type == TransactionType.INCOME:
            self._account_repo.update_balance(account.id, account.balance - tx.amount)
        elif tx.transaction_type == TransactionType.TRANSFER and tx.to_account_id:
            target = self._account_repo.get_by_id(tx.to_account_id)
            if not target:
                msg = "Целевой счет перевода не найден для отката операции."
                raise ValueError(msg)
            if target.user_id != user_id:
                msg = "Доступ к целевому счету запрещен."
                raise PermissionError(msg)
            self._account_repo.update_balance(account.id, account.balance + tx.amount)
            self._account_repo.update_balance(target.id, target.balance - tx.amount)

        self._tx_repo.delete(transaction_id)

    def get_history(
        self,
        user_id: int,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        account_id: int | None = None,
        category_id: int | None = None,
        tx_type: TransactionType | None = None,
    ) -> list[Transaction]:
        """Возвращает историю операций пользователя с необязательными фильтрами."""
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("Начальная дата не может быть позже конечной.")

        if account_id is not None:
            account = self._account_repo.get_by_id(account_id)
            if not account or account.user_id != user_id:
                raise PermissionError(
                    "Счет не найден или принадлежит другому пользователю."
                )

        if category_id is not None:
            category = self._category_repo.get_by_id(category_id)
            if not category or category.user_id != user_id:
                raise PermissionError(
                    "Категория не найдена или принадлежит другому пользователю."
                )

        transactions = self._tx_repo.get_all_by_user(user_id)

        return [
            tx
            for tx in transactions
            if (date_from is None or tx.timestamp.date() >= date_from)
            and (date_to is None or tx.timestamp.date() <= date_to)
            and (
                account_id is None
                or tx.account_id == account_id
                or tx.to_account_id == account_id
            )
            and (category_id is None or tx.category_id == category_id)
            and (tx_type is None or tx.transaction_type == tx_type)
        ]
```

#### `src/services/export.py`

```python
import csv
import io

from src.models.transaction import Transaction
from src.repositories.account import AccountRepository
from src.repositories.category import CategoryRepository


class ExportService:
    """Сервис экспорта журнала операций в плоский формат CSV."""

    def __init__(
        self,
        account_repo: AccountRepository,
        category_repo: CategoryRepository,
    ) -> None:
        """Получает хранилища для подстановки имен счетов и категорий."""
        self._account_repo = account_repo
        self._category_repo = category_repo

    def export_to_csv(self, user_id: int, transactions: list[Transaction]) -> str:
        """Формирует CSV-файл после проверки принадлежности всех данных пользователю."""

        for tx in transactions:
            if tx.user_id != user_id:
                raise PermissionError("Операция принадлежит другому пользователю.")

            acc = self._account_repo.get_by_id(tx.account_id)
            if not acc or acc.user_id != user_id:
                raise PermissionError("Счет операции принадлежит другому пользователю.")

            if tx.category_id is not None:
                cat = self._category_repo.get_by_id(tx.category_id)
                if not cat or cat.user_id != user_id:
                    raise PermissionError(
                        "Категория операции принадлежит другому пользователю."
                    )

            if tx.to_account_id is not None:
                target = self._account_repo.get_by_id(tx.to_account_id)
                if not target or target.user_id != user_id:
                    raise PermissionError(
                        "Целевой счет перевода принадлежит другому пользователю."
                    )

        output = io.StringIO()
        output.write("\ufeff")
        writer = csv.writer(output, delimiter=";")
        writer.writerow(
            ["ID", "Дата и время", "Тип", "Счет", "Категория", "Сумма (руб.)"]
        )

        for tx in transactions:
            acc = self._account_repo.get_by_id(tx.account_id)
            acc_name = acc.name if acc else "Неизвестный"

            cat_name = "Без категории"
            if tx.category_id is not None:
                cat = self._category_repo.get_by_id(tx.category_id)
                if cat:
                    cat_name = cat.name

            writer.writerow(
                [
                    tx.id,
                    tx.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    tx.transaction_type.value,
                    acc_name,
                    cat_name,
                    f"{tx.amount:.2f}",
                ]
            )

        return output.getvalue()
```

#### `src/services/budget.py`

```python
from decimal import Decimal

from src.models.budget import BudgetLimit
from src.models.category import CategoryDirection
from src.models.transaction import TransactionType
from src.repositories.budget import BudgetRepository
from src.repositories.category import CategoryRepository
from src.repositories.transaction import TransactionRepository
from src.services.money import validate_money


class BudgetService:
    """Сервис контроля лимитов и расчета освоения бюджетов."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        tx_repo: TransactionRepository,
        category_repo: CategoryRepository,
    ) -> None:
        """Получает хранилища лимитов, операций и обязательных категорий."""
        self._budget_repo = budget_repo
        self._tx_repo = tx_repo
        self._category_repo = category_repo

    @staticmethod
    def _validate_period(month: int, year: int) -> None:
        """Проверяет корректность календарного месяца и года."""
        if not 1 <= month <= 12:
            msg = "Номер месяца должен находиться в диапазоне от 1 до 12."
            raise ValueError(msg)
        if year < 1970 or year > 2100:
            msg = "Указан некорректный календарный год."
            raise ValueError(msg)

    def set_budget(
        self,
        user_id: int,
        category_id: int,
        month: int,
        year: int,
        limit_amount: Decimal,
    ) -> BudgetLimit:
        """Устанавливает лимит бюджета на календарный месяц."""
        self._validate_period(month, year)

        validate_money(limit_amount, positive=True)

        category = self._category_repo.get_by_id(category_id)
        if not category or category.user_id != user_id:
            msg = "Категория не найдена или принадлежит другому пользователю."
            raise PermissionError(msg)
        if category.direction != CategoryDirection.EXPENSE:
            msg = "Бюджетный лимит можно установить только для категории расходов."
            raise ValueError(msg)

        budget = BudgetLimit(
            id=0,
            user_id=user_id,
            category_id=category_id,
            month=month,
            year=year,
            limit_amount=limit_amount,
        )
        return self._budget_repo.set_limit(budget)

    def calculate_status(
        self, user_id: int, category_id: int, month: int, year: int
    ) -> tuple[Decimal, Decimal, str]:
        """Рассчитывает сумму расходов, процент освоения и цветовой статус."""
        self._validate_period(month, year)

        category = self._category_repo.get_by_id(category_id)
        if not category or category.user_id != user_id:
            msg = "Категория не найдена или принадлежит другому пользователю."
            raise PermissionError(msg)

        budget = self._budget_repo.get_limit(user_id, category_id, month, year)
        if not budget:
            msg = "Бюджетный лимит на указанный период не установлен."
            raise ValueError(msg)

        txs = self._tx_repo.get_all_by_user(user_id)
        spent = sum(
            (
                tx.amount
                for tx in txs
                if tx.category_id == category_id
                and tx.transaction_type == TransactionType.EXPENSE
                and tx.timestamp.month == month
                and tx.timestamp.year == year
            ),
            Decimal("0.00"),
        )

        ratio = (
            (spent / budget.limit_amount) * Decimal("100.0")
            if budget.limit_amount > 0
            else Decimal("0.0")
        )

        if ratio < Decimal("80.0"):
            indicator = "GREEN (Штатный режим)"
        elif ratio <= Decimal("100.0"):
            indicator = "YELLOW (Внимание, приближение к лимиту)"
        else:
            indicator = "RED (Лимит превышен)"

        return spent, ratio, indicator
```

### 4.5. Консольный интерфейс и точка входа

#### `src/cli/terminal_interface.py`

```python
import os
import tempfile
from contextlib import suppress
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import TypeVar

from src.models.account import AccountType
from src.models.category import CategoryDirection
from src.models.transaction import Transaction, TransactionType
from src.services.account import AccountService
from src.services.budget import BudgetService
from src.services.category import CategoryService
from src.services.export import ExportService
from src.services.transaction import TransactionService

T = TypeVar("T", bound=IntEnum)


class MainMenuChoice(IntEnum):
    """Пункты главного меню консольного интерфейса."""

    SHOW_ACCOUNTS = 1
    CREATE_ACCOUNT = 2
    ADD_TRANSACTION = 3
    TRANSFER = 4
    SHOW_HISTORY = 5
    BUDGET_STATUS = 6
    DELETE_TRANSACTION = 7
    EXPORT_CSV = 8
    ARCHIVE_ACCOUNT = 9
    EXIT = 0


class AccountTypeChoice(IntEnum):
    """Выбор типа счёта в меню CLI."""

    DEBIT = 1
    CREDIT = 2
    CASH = 3
    SAVINGS = 4

    @property
    def to_domain(self) -> AccountType:
        """Преобразует пункт меню в доменный тип счета."""
        mapping = {
            AccountTypeChoice.DEBIT: AccountType.DEBIT,
            AccountTypeChoice.CREDIT: AccountType.CREDIT,
            AccountTypeChoice.CASH: AccountType.CASH,
            AccountTypeChoice.SAVINGS: AccountType.SAVINGS,
        }
        return mapping[self]


class TransactionKindChoice(IntEnum):
    """Выбор типа операции в меню CLI."""

    EXPENSE = 1
    INCOME = 2

    @property
    def to_domain(self) -> TransactionType:
        """Преобразует пункт меню в тип финансовой операции."""
        if self is TransactionKindChoice.EXPENSE:
            return TransactionType.EXPENSE
        return TransactionType.INCOME

    @property
    def category_direction(self) -> CategoryDirection:
        """Выбирает направление категории для дохода или расхода."""
        if self is TransactionKindChoice.EXPENSE:
            return CategoryDirection.EXPENSE
        return CategoryDirection.INCOME


class HistoryTypeChoice(IntEnum):
    """Выбор типа операции для фильтрации истории."""

    INCOME = 1
    EXPENSE = 2
    TRANSFER = 3

    @property
    def to_domain(self) -> TransactionType:
        """Преобразует выбор CLI в доменный тип операции."""
        mapping = {
            HistoryTypeChoice.INCOME: TransactionType.INCOME,
            HistoryTypeChoice.EXPENSE: TransactionType.EXPENSE,
            HistoryTypeChoice.TRANSFER: TransactionType.TRANSFER,
        }
        return mapping[self]


class BudgetActionChoice(IntEnum):
    """Выбор действия в подменю бюджетов."""

    SET_LIMIT = 1
    CHECK_STATUS = 2


class TerminalInterface:
    """Консольный интерфейс системы CapitalTracker."""

    def __init__(
        self,
        user_id: int,
        account_service: AccountService,
        tx_service: TransactionService,
        budget_service: BudgetService,
        category_service: CategoryService,
        export_service: ExportService,
    ) -> None:
        """Получает сервисы текущей операции, не обращаясь к репозиториям."""
        self._user_id = user_id
        self._acc_svc = account_service
        self._tx_svc = tx_service
        self._bdg_svc = budget_service
        self._cat_svc = category_service
        self._exp_svc = export_service

    def run_once(self) -> bool:
        """Обрабатывает один пункт меню внутри внешней транзакции БД."""
        self._print_header()
        choice = self._read_choice("Выберите пункт меню [0-9]: ", MainMenuChoice)
        if choice is MainMenuChoice.EXIT:
            print("\nЗавершение сеанса. Данные сохранены в базе данных.")
            return False
        handlers = {
            MainMenuChoice.SHOW_ACCOUNTS: self._handle_show_accounts,
            MainMenuChoice.CREATE_ACCOUNT: self._handle_create_account,
            MainMenuChoice.ADD_TRANSACTION: self._handle_add_transaction,
            MainMenuChoice.TRANSFER: self._handle_transfer,
            MainMenuChoice.SHOW_HISTORY: self._handle_show_history,
            MainMenuChoice.BUDGET_STATUS: self._handle_budget_status,
            MainMenuChoice.DELETE_TRANSACTION: self._handle_delete_transaction,
            MainMenuChoice.EXPORT_CSV: self._handle_export_csv,
            MainMenuChoice.ARCHIVE_ACCOUNT: self._handle_archive_account,
        }
        handlers[choice]()
        return True

    def _print_header(self) -> None:
        """Отображает верхнюю информационную плашку."""
        capital = self._acc_svc.calculate_total_capital(self._user_id)
        print("\n" + "=" * 55)
        print(f" CAPITALTRACKER CLI | Совокупный капитал: {capital:.2f} руб.")
        print("=" * 55)
        print("1. Мои счета и балансы")
        print("2. Открыть новый счет")
        print("3. Внести операцию (Расход / Доход)")
        print("4. Межбалансовый перевод")
        print("5. Журнал операций")
        print("6. Бюджеты и контроль лимитов")
        print("7. Удалить операцию (Откат остатка)")
        print("8. Экспорт отфильтрованного журнала в CSV")
        print("9. Заархивировать счет")
        print("0. Выход")
        print("-" * 55)

    def _read_choice(self, prompt: str, enum_cls: type[T]) -> T:
        """Безопасное считывание выбора пользователя из перечисления."""
        while True:
            raw = input(prompt).strip()
            try:
                return enum_cls(int(raw))
            except ValueError:
                valid_keys = ", ".join(str(e.value) for e in enum_cls)
                print(f"[!] Неверный выбор. Допустимые варианты: {valid_keys}")

    def _handle_show_accounts(self) -> None:
        """Показывает перечень счетов."""
        accounts = self._acc_svc.get_user_accounts(self._user_id)
        if not accounts:
            print("\nУ вас пока нет активных счетов.")
            return

        print("\nВаши активные счета:")
        for acc in accounts:
            type_str = acc.account_type.value
            bal_str = f"{acc.balance:.2f}"
            print(f"  [{acc.id}] {acc.name} ({type_str}): {bal_str} руб.")

    def _handle_create_account(self) -> None:
        """Диалог создания счета."""
        name = input("Введите наименование счета: ").strip()
        print("Доступные типы: 1. DEBIT, 2. CREDIT, 3. CASH, 4. SAVINGS")
        choice = self._read_choice("Выберите тип [1-4]: ", AccountTypeChoice)
        acc_type = choice.to_domain

        raw_balance = input("Введите начальный остаток: ").strip()
        balance = Decimal(raw_balance)
        acc = self._acc_svc.create_account(self._user_id, name, acc_type, balance)
        print(
            f"[OK] Счет '{acc.name}' успешно открыт с балансом {acc.balance:.2f} руб."
        )

    def _handle_archive_account(self) -> None:
        """Диалог архивации счета."""
        self._handle_show_accounts()
        raw_id = input("Введите ID счета для архивации: ").strip()
        if not raw_id.isdigit():
            print("[!] Некорректный ID счета.")
            return
        acc_id = int(raw_id)
        self._acc_svc.archive_account(acc_id, self._user_id)
        print(f"[OK] Счет ID {acc_id} успешно переведен в архив.")

    def _handle_add_transaction(self) -> None:
        """Диалог регистрации дохода или расхода."""
        self._handle_show_accounts()
        raw_acc_id = input("Введите ID счета: ").strip()
        if not raw_acc_id.isdigit():
            print("[!] Некорректный ID счета.")
            return
        acc_id = int(raw_acc_id)

        print("Тип операции: 1. Расход, 2. Доход")
        choice = self._read_choice("Выберите тип [1-2]: ", TransactionKindChoice)
        tx_type = choice.to_domain

        categories = self._cat_svc.get_categories_by_direction(
            self._user_id, choice.category_direction
        )
        print("Доступные категории:")
        for cat in categories:
            print(f"  [{cat.id}] {cat.name} ({cat.direction.value})")
        raw_cat_id = input("Введите ID категории: ").strip()
        if not raw_cat_id.isdigit():
            print("[!] Некорректный ID категории.")
            return
        cat_id = int(raw_cat_id)

        raw_amount = input("Введите сумму: ").strip()
        amount = Decimal(raw_amount)
        self._tx_svc.register_transaction(
            self._user_id, tx_type, amount, acc_id, cat_id
        )
        print("[OK] Операция успешно зафиксирована, баланс счета пересчитан.")

    def _handle_transfer(self) -> None:
        """Диалог внутреннего перевода."""
        self._handle_show_accounts()
        raw_from = input("ID счета списания: ").strip()
        raw_to = input("ID счета зачисления: ").strip()
        if not (raw_from.isdigit() and raw_to.isdigit()):
            print("[!] Некорректные идентификаторы счетов.")
            return

        raw_amount = input("Сумма перевода: ").strip()
        amount = Decimal(raw_amount)
        self._tx_svc.make_transfer(self._user_id, int(raw_from), int(raw_to), amount)
        print("[OK] Перевод успешно выполнен. Совокупный капитал неизменен.")

    def _read_history_filters(self) -> list[Transaction] | None:
        """Считывает общие фильтры и возвращает отобранные операции."""
        print("\nФильтры журнала (пустое поле — без фильтра).")

        raw_date_from = input("Дата от [ГГГГ-ММ-ДД]: ").strip()
        raw_date_to = input("Дата до [ГГГГ-ММ-ДД]: ").strip()
        raw_account_id = input("ID счета: ").strip()
        raw_category_id = input("ID категории: ").strip()
        raw_type = input("Тип операции (1 — доход, 2 — расход, 3 — перевод): ").strip()

        try:
            date_from = date.fromisoformat(raw_date_from) if raw_date_from else None
            date_to = date.fromisoformat(raw_date_to) if raw_date_to else None

            if raw_account_id and not raw_account_id.isdigit():
                raise ValueError("ID счета должен быть целым положительным числом.")
            if raw_category_id and not raw_category_id.isdigit():
                raise ValueError("ID категории должен быть целым положительным числом.")

            account_id = int(raw_account_id) if raw_account_id else None
            category_id = int(raw_category_id) if raw_category_id else None

            if account_id is not None and account_id <= 0:
                raise ValueError("ID счета должен быть положительным числом.")
            if category_id is not None and category_id <= 0:
                raise ValueError("ID категории должен быть положительным числом.")

            type_choice = HistoryTypeChoice(int(raw_type)) if raw_type else None
            tx_type = type_choice.to_domain if type_choice else None

        except ValueError as error:
            print(f"[!] Некорректный фильтр: {error}")
            return None

        try:
            return self._tx_svc.get_history(
                self._user_id,
                date_from=date_from,
                date_to=date_to,
                account_id=account_id,
                category_id=category_id,
                tx_type=tx_type,
            )
        except (ValueError, PermissionError) as error:
            print(f"[!] Ошибка фильтрации: {error}")
            return None

    def _handle_show_history(self) -> set[int]:
        """Показывает журнал и возвращает ID отображённых операций."""
        txs = self._read_history_filters()
        if txs is None:
            return set()

        if not txs:
            print("\nЖурнал операций пуст.")
            return set()

        print("\nЖурнал транзакций:")
        for tx in txs:
            print(
                f"  #{tx.id} | {tx.timestamp.strftime('%d.%m %H:%M')} | "
                f"{tx.transaction_type.value} | {tx.amount:.2f} руб. | "
                f"Счет: {tx.account_id}"
            )
        return {tx.id for tx in txs}

    def _handle_budget_status(self) -> None:
        """Проверяет освоение бюджета."""
        print("1. Установить лимит, 2. Проверить статус")
        action = self._read_choice("Выбор [1-2]: ", BudgetActionChoice)

        raw_month = input("Месяц [1-12]: ").strip()
        raw_year = input("Год [например, 2026]: ").strip()
        try:
            month = int(raw_month)
            year = int(raw_year)
        except ValueError:
            print("[!] Некорректный месяц или год.")
            return

        categories = self._cat_svc.get_categories_by_direction(
            self._user_id, CategoryDirection.EXPENSE
        )
        print("Категории расходов:")
        for cat in categories:
            print(f"  [{cat.id}] {cat.name}")
        raw_cat = input("ID категории: ").strip()
        if not raw_cat.isdigit():
            print("[!] Некорректный ID категории.")
            return
        cat_id = int(raw_cat)

        if action is BudgetActionChoice.SET_LIMIT:
            raw_lim = input("Лимит (руб): ").strip()
            lim = Decimal(raw_lim)
            self._bdg_svc.set_budget(self._user_id, cat_id, month, year, lim)
            print("[OK] Лимит успешно установлен.")
        else:
            spent, ratio, ind = self._bdg_svc.calculate_status(
                self._user_id, cat_id, month, year
            )
            print(f"Потрачено: {spent:.2f} руб. ({ratio:.1f}%) | Статус: {ind}")

    def _handle_delete_transaction(self) -> None:
        """Удаляет транзакцию с откатом сальдо."""
        visible_ids = self._handle_show_history()
        if not visible_ids:
            return
        raw_tx_id = input("Введите ID транзакции для отмены: ").strip()
        if not raw_tx_id.isdigit():
            print("[!] Некорректный ID транзакции.")
            return
        tx_id = int(raw_tx_id)
        if tx_id not in visible_ids:
            print("[!] Выберите ID операции из показанного списка.")
            return
        self._tx_svc.delete_transaction(tx_id, self._user_id)
        print("[OK] Транзакция удалена, остаток счета автоматически восстановлен.")

    def _handle_export_csv(self) -> None:
        """Экспортирует отфильтрованные данные в файл CSV."""
        txs = self._read_history_filters()
        if txs is None:
            return

        csv_data = self._exp_svc.export_to_csv(self._user_id, txs)
        filename = "transactions_export.csv"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=".",
                prefix=".transactions_export_",
                suffix=".tmp",
                delete=False,
            ) as file:
                temp_path = file.name
                file.write(csv_data)
            os.replace(temp_path, filename)
            temp_path = None
        except OSError as error:
            print(f"[!] Не удалось записать CSV: {error}")
            return
        finally:
            if temp_path is not None:
                with suppress(OSError):
                    os.unlink(temp_path)
        print(f"[OK] Данные выгружены в файл '{filename}' в кодировке UTF-8.")
```

#### `src/main.py`

```python
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
from src.repositories.account import SQLAlchemyAccountRepository
from src.repositories.budget import SQLAlchemyBudgetRepository
from src.repositories.category import SQLAlchemyCategoryRepository
from src.repositories.transaction import SQLAlchemyTransactionRepository
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
```

### 4.6. PostgreSQL в Docker Compose

Контейнер использует PostgreSQL 15 по ТЗ, именованный том сохраняет данные, `healthcheck` проверяет готовность сервера. Порт опубликован только на локальном интерфейсе. Учетные данные в Compose являются учебными, реальных банковских данных приложение не запрашивает.

#### `docker-compose.yaml`

```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: capitaltracker
      POSTGRES_PASSWORD: capitaltracker
      POSTGRES_DB: capitaltracker
    ports:
      - "127.0.0.1:5432:5432"
    volumes:
      - capitaltracker_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U capitaltracker -d capitaltracker"]
      interval: 5s
      timeout: 5s
      retries: 10

volumes:
  capitaltracker_pgdata:
```

### 4.7. Alembic и начальная миграция

Выполнены команды:

```bash
uv run alembic init migrations
uv run alembic revision --autogenerate -m "create capital tracker schema"
uv run alembic upgrade head
```

Перед применением миграция просмотрена и приведена к стилю проекта: убраны комментарии внутри функций и повторные проверки перечислений. В ORM у строковых Enum включено создание CHECK; в ревизии эти проверки выписаны явно с окончательными именами, а автоматическое создание CHECK у типа Enum выключено, чтобы не дублировать ограничения.

Автогенерация дает кандидат миграции и не отменяет ручную проверку; см. [документацию Alembic](https://alembic.sqlalchemy.org/en/latest/autogenerate.html). После применения изменения схемы оформляются новой ревизией. Таблицы не создаются из приложения или тестов напрямую.

#### `alembic.ini`

```ini
[alembic]
script_location = %(here)s/migrations
prepend_sys_path = %(here)s
path_separator = os
file_template = %%(year)d%%(month).2d%%(day).2d_%%(hour).2d%%(minute).2d%%(second).2d_%%(rev)s_%%(slug)s

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

#### `migrations/env.py`

```python
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
```

#### `migrations/versions/20261117_224038_9ea22d7a56ab_create_capital_tracker_schema.py`

```python
"""create capital tracker schema

Revision ID: 9ea22d7a56ab
Revises:
Create Date: 2026-11-17 22:40:38.556780

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9ea22d7a56ab"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет изменение схемы базы данных."""
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(trim(username)) > 0", name=op.f("ck_users_username_not_blank")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "account_type",
            sa.Enum(
                "DEBIT",
                "CREDIT",
                "CASH",
                "SAVINGS",
                name="account_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("balance", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default="false", nullable=False),
        sa.CheckConstraint(
            "account_type IN ('DEBIT', 'CREDIT', 'CASH', 'SAVINGS')",
            name=op.f("ck_accounts_account_type"),
        ),
        sa.CheckConstraint(
            "balance > -10000000000000000 AND balance < 10000000000000000",
            name=op.f("ck_accounts_balance_finite"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_accounts_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_accounts_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint("user_id", "id", name=op.f("uq_accounts_user_id")),
    )
    op.create_index(op.f("ix_accounts_user_id"), "accounts", ["user_id"], unique=False)
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column(
            "direction",
            sa.Enum(
                "INCOME",
                "EXPENSE",
                name="category_direction",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.CheckConstraint(
            "direction IN ('INCOME', 'EXPENSE')",
            name=op.f("ck_categories_category_direction"),
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_categories_name_not_blank")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_categories_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("user_id", "id", name=op.f("uq_categories_user_id")),
    )
    op.create_index(
        op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False
    )
    op.create_table(
        "budget_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("limit_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.CheckConstraint(
            "limit_amount > 0 AND limit_amount < 10000000000000000",
            name=op.f("ck_budget_limits_limit_positive_finite"),
        ),
        sa.CheckConstraint(
            "month BETWEEN 1 AND 12", name=op.f("ck_budget_limits_month_range")
        ),
        sa.CheckConstraint(
            "year BETWEEN 1970 AND 2100", name=op.f("ck_budget_limits_year_range")
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_budget_limits_owner_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_budget_limits_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_limits")),
        sa.UniqueConstraint(
            "user_id", "category_id", "month", "year", name="uq_budget_period"
        ),
    )
    op.create_index(
        op.f("ix_budget_limits_category_id"),
        "budget_limits",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_budget_limits_user_id"), "budget_limits", ["user_id"], unique=False
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "transaction_type",
            sa.Enum(
                "INCOME",
                "EXPENSE",
                "TRANSFER",
                name="transaction_type",
                native_enum=False,
                create_constraint=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("to_account_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "(transaction_type = 'TRANSFER' AND to_account_id IS NOT NULL "
            "AND to_account_id <> account_id AND category_id IS NULL) OR "
            "(transaction_type IN ('INCOME', 'EXPENSE') "
            "AND category_id IS NOT NULL AND to_account_id IS NULL)",
            name=op.f("ck_transactions_operation_fields"),
        ),
        sa.CheckConstraint(
            "transaction_type IN ('INCOME', 'EXPENSE', 'TRANSFER')",
            name=op.f("ck_transactions_transaction_type"),
        ),
        sa.CheckConstraint(
            "amount > 0 AND amount < 10000000000000000",
            name=op.f("ck_transactions_amount_positive_finite"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_account",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "category_id"],
            ["categories.user_id", "categories.id"],
            name="fk_transactions_owner_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id", "to_account_id"],
            ["accounts.user_id", "accounts.id"],
            name="fk_transactions_owner_target",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_transactions_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
    )
    op.create_index(
        op.f("ix_transactions_account_id"), "transactions", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_category_id"),
        "transactions",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_to_account_id"),
        "transactions",
        ["to_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Возвращает предыдущее состояние схемы базы данных."""
    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_to_account_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_budget_limits_user_id"), table_name="budget_limits")
    op.drop_index(op.f("ix_budget_limits_category_id"), table_name="budget_limits")
    op.drop_table("budget_limits")
    op.drop_index(op.f("ix_categories_user_id"), table_name="categories")
    op.drop_table("categories")
    op.drop_index(op.f("ix_accounts_user_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("users")
```

---

## 5. Проверка качества кода и миграций

### 5.1. Отдельная тестовая база

PostgreSQL запускается из корня репозитория. Тестовую базу создают один раз:

```bash
docker compose up -d --wait
docker compose exec -T db createdb -U capitaltracker capitaltracker_test
uv run pytest -q
```

Тесты используют `capitaltracker_test` или `TEST_DATABASE_URL` с именем базы, заканчивающимся на `_test`. Схема создается миграциями. Тест обратимости удаляет и восстанавливает таблицы исключительно этой тестовой базы; прикладная `capitaltracker` не используется. Данные остальных тестов изолированы транзакциями.

### 5.2. Результаты проверок

```bash
$ uv run ruff check src/ migrations/ tests/
All checks passed!

$ uv run ruff format --check src/ migrations/ tests/
33 files already formatted

$ uv run mypy src/ migrations/ tests/
Success: no issues found in 33 source files

$ uv run pytest -q
96 passed

$ uv build
Successfully built dist/capital_tracker-0.1.0.tar.gz
Successfully built dist/capital_tracker-0.1.0-py3-none-any.whl

$ uv run alembic current
9ea22d7a56ab (head)

$ uv run alembic history
<base> -> 9ea22d7a56ab (head), create capital tracker schema

$ uv run alembic check
No new upgrade operations detected.
```

В листинге проверок опущены служебные INFO-сообщения. Дополнительно AST-проверкой подтверждено отсутствие вызовов `create_all`, пропущенных docstrings и комментариев внутри функций в `src/`, `migrations/` и `tests/`.

### 5.3. Проверенные сценарии

| Группа | Подтвержденное поведение |
| :--- | :--- |
| Миграции | На пустой схеме создаются пять таблиц; `downgrade base` оставляет только `alembic_version`; повторный `upgrade head` восстанавливает схему |
| Доход и расход | Точные изменения остатка и компенсация при удалении |
| Перевод | Сумма капитала сохраняется; отмена восстанавливает оба остатка |
| Сбой записи | Ошибка INSERT после изменения обоих остатков откатывает их вместе; сбой второго обновления при отмене перевода сохраняет исходную операцию |
| Бюджеты | Границы 80% и 100%; исключение доходов и другого периода; обновление суммы без смены ID; UNIQUE периода и CHECK месяца, года, суммы |
| Изоляция | Составные FK запрещают чужие счета, целевой счет и категории; история выбирается по владельцу |
| История операций | Фильтры по начальной и конечной дате, счету, категории и типу; границы дат включительные, все заданные условия объединяются через AND; для счета и категории проверяется принадлежность пользователю |
| Удаление из отфильтрованной истории | Удаление разрешено только для ID, который присутствует в показанном списке; посторонний ID отклоняется, операция и остатки счетов не изменяются |
| Каскады | RESTRICT сохраняет историю при попытке удаления владельца, счета и категории с загруженными и незагруженными коллекциями |
| M:N | Обе стороны связи корректны; повторные операции не дублируют сущности в коллекции; перевод не добавляет категорию |
| CSV | BOM, разделитель `;`, русский заголовок и имена; перед экспортом проверяются владелец операции, исходный и целевой счета, а также категория; перевод экспортируется без категории |
| Ошибочные фильтры CLI | Неверная дата, недопустимый тип и чужой счет отменяют просмотр, удаление и экспорт; CSV не создается и не перезаписывается, история и остатки сохраняются |
| Ошибки файловой системы | Ошибки создания, записи, закрытия и замены временного CSV-файла обрабатываются в CLI; прежний CSV сохраняется, временный файл удаляется, сообщение об успехе не выводится |
| Валидация | Обязательная категория; непустое имя счета длиной не более 100 символов после удаления пробелов по краям; 100 символов допускаются, 101 — отклоняется; проверка конечного баланса, нечисловых и неположительных сумм, дробных копеек и переполнения |
| Повторный запуск | Новый процесс читает сохраненный счет; повторный seed не дублирует профиль и категории |

---

## 6. Запуск и демонстрация работы с БД

### 6.1. Штатный запуск

Все команды выполняются из корня проекта:

```bash
uv sync
docker compose up -d --wait
uv run alembic upgrade head
uv run capital-tracker
```

Альтернативная точка входа:

```bash
uv run python -m src.main
```

`DATABASE_URL` по умолчанию указывает на локальный PostgreSQL из Compose. Файл `.env` сам по себе Python-код не загружает; при необходимости URL задается переменной окружения. В Docker должен быть запущен Engine. Если после установки на macOS команда Docker не найдена, для текущего терминала можно добавить путь:

```bash
export PATH="$HOME/.docker/bin:$PATH"
```

### 6.2. Просмотр схемы

```bash
docker compose ps
docker compose exec -T db psql -U capitaltracker -d capitaltracker -c '\dt'
docker compose exec -T db psql -U capitaltracker -d capitaltracker -c '\d+ transactions'
```

Ожидаемые таблицы приложения: `users`, `accounts`, `categories`, `transactions`, `budget_limits`; отдельно присутствует служебная `alembic_version`.

### 6.3. Проверка сохранности данных

На отдельной тестовой базе выполнены два независимых запуска CLI. В первом создан счет «Проверка сохранения» с остатком `123.45` руб. После завершения процесса перезапущен контейнер PostgreSQL, выполнено ожидание готовности и запущен новый процесс CLI. Счет отобразился с тем же остатком.

```text
Первый запуск CLI: счет сохранен с балансом 123.45 руб.
После перезапуска контейнера и нового процесса CLI:
Проверка сохранения (DEBIT): 123.45 руб.
```

Штатная точка входа `uv run capital-tracker` также запущена на прикладной базе: меню отобразилось, выход завершился без ошибок.

### 6.4. Соответствие критериям

| № | Критерий | Реализованное подтверждение |
| :---: | :--- | :--- |
| 1 | ER-диаграмма и ограничения | `docs/er.md`, раздел 2 отчета |
| 2 | Alembic init, autogenerate, upgrade | Конфигурация, ревизия `9ea22d7a56ab`, раздел 4.7 |
| 3 | Отсутствие создания схемы через metadata | В коде и тестах нет запрещенного вызова; схема тестов тоже создается Alembic |
| 4 | Mapped, mapped_column, PK/FK | Пять классов в `src/database/models.py`, ограничения в примененной миграции |
| 5 | 1:N, M:N, back_populates, каскады | Коллекции владельца, M:N счетов и категорий, RESTRICT и приемочные тесты |
| 6 | Адаптация предыдущего кода | SQLAlchemy-репозитории, пять мапперов, DI и транзакция команды CLI |
| 7 | Compose для PostgreSQL | `docker-compose.yaml`, реальный запуск и перезапуск контейнера |

---

## 7. Ход выполнения работы и ограничения

| Дата | Выполненное действие | Результат |
| :--- | :--- | :--- |
| 17.11.2026 | Анализ задания, методического примера и прототипа | Определены таблицы и необходимые изменения |
| 17.11.2026 | Проектирование связей и ограничений | Существующие пять сущностей, M:N через операции, сохранение истории |
| 17.11.2026 | Настройка PostgreSQL и Alembic | Контейнер готов; миграция сгенерирована, проверена и применена |
| 17.11.2026 | Реализация ORM, мапперов, репозиториев и DI | CLI использует постоянное хранилище с транзакцией на команду |
| 17.11.2026 | Проверка точности денег и ограничений | Дробные копейки отклоняются до записи; ограничения проверены на PostgreSQL |
| 17.11.2026 | Приемочные проверки и повторный запуск | 47 тестов, Ruff, mypy, сборка, миграции и сохранность данных проверены |
| 17.11.2026 | Завершение документации | Проверен `.gitignore`, технические инструкции `AGENTS.md` актуализированы по реализации лабораторной № 4 |
| 19.11.2026 | Исправления фильтров и листингов после проверки PR | Исправлены переносы строк, добавлены 12 сценариев ошибочных фильтров; 80 тестов прошли |
| 19.11.2026 | Замечания преподавателя к репозиториям | SQLAlchemy-классы перенесены к ABC и InMemory, параметры методов согласованы с ABC; 81 тест прошел |
| 19.11.2026 | Проверка CLI и документации | Ошибки CSV обрабатываются, ошибка фильтра или пустая выборка отменяют удаление; 91 тест, Ruff, mypy, сборка и alembic check прошли |
| 21.11.2026 | Завершение исправлений и проверка проекта | Удаление ограничено ID из отображённой истории; CSV экспортируется атомарно через временный файл и `os.replace`; имя счета ограничено 100 символами после `strip()`; 94 теста, Ruff, mypy, Alembic check и `uv build` прошли |
| 21.11.2026 | Проверка после ревью | Проверены замена существующего CSV, отсутствие временного файла после успеха и сбоя записи, отказ для имени из 101 символа без создания счёта в памяти. Прошли 96 тестов, Ruff, mypy, проверка Alembic и сборка |

### 7.1. Исправления журнала, экспорта и счетов

| Где проявлялась проблема | Как исправили | Как проверили |
| --- | --- | --- |
| При прямом вызове сервиса экспорта можно было передать чужую операцию или смешанный список. CLI обычно передавал только свои записи, поэтому при работе через меню ошибка оставалась незаметной. | Метод `export_to_csv(user_id, transactions)` проверяет владельца каждой операции, основного счета, указанной категории и целевого счета перевода до формирования CSV. При нарушении отклоняется вся выборка. | Проверены чужая операция, смешанный список и операции со ссылками на чужие счета или категорию. История собственного архивного счета по-прежнему экспортируется. |
| Журнал и CSV выдавали всю историю владельца. Пользователь не мог получить, например, только расходы с карты за ноябрь. | Журнал и экспорт используют общую выборку по периоду, счету, категории и типу. Обе даты включаются, условия применяются одновременно. Для перевода учитываются оба счета. | Сравнили вывод журнала и содержимое CSV при одинаковом фильтре. Проверили границы дат, сочетания условий и отказ при чужом счете или категории. |
| При удалении журнал показывал отфильтрованные записи, но CLI принимал ID любой другой операции того же пользователя. Опечатка могла привести к удалению другой записи и пересчету баланса. | CLI сохраняет ID показанных операций и передает команду удаления сервису только для ID из этого множества. Пустой список или ошибка фильтра завершают команду до запроса ID. | При фильтре «только расходы» ввели ID дохода. Обе записи и остаток счета сохранились. |
| При повторном экспорте открытие файла с режимом `w` стирало прежнее содержимое до окончания записи. Даже обработанная ошибка записи могла оставить пустой или неполный отчет. | CLI записывает новый CSV во временный файл в каталоге назначения. После успешного закрытия файла вызывает `os.replace`. При сбое сообщает об ошибке и пытается удалить временный файл. | Имитировали ошибку записи и побайтно сравнили прежний CSV. Проверили также успешную замену и отсутствие временных файлов в обоих сценариях. |
| Сервис принимал название счета длиннее 100 символов. InMemory сохранял его, а PostgreSQL отклонял запись из-за ограничения колонки. | `AccountService.create_account` удаляет пробелы по краям и проверяет длину до обращения к репозиторию. При превышении предела пользователь получает сообщение с допустимой длиной. | Проверены 100 символов, 101 символ и 100 символов с пробелами по краям. При отказе InMemory новый счет не появляется. |

Проверка владельцев и общие фильтры вошли в [PR № 2](https://github.com/onefivesevenceo/IVT_262/pull/2). Ограничение удаления показанными ID, сохранение прежнего CSV при сбое и проверка длины имени вошли в [PR № 3](https://github.com/onefivesevenceo/IVT_262/pull/3). Последний прогон после ревью этой версии включал 96 успешно прошедших тестов.

Сохранены границы учебного этапа: один профиль CLI, отсутствие веб-авторизации и конвертации валют. В консольном интерфейсе реализованы фильтры истории и экспорта CSV по датам, счету, категории и типу операции. При экспорте дополнительно проверяется принадлежность пользователю операции и связанных с ней счетов и категории. Суммы и вывод остаются рублевыми. Политика одновременного редактирования из нескольких клиентов требует отдельной проработки на этапе веб-приложения.

---

*Авторы отчета: студенты гр. ИВТ-262 ВолгГТУ Павловский И. Ю., Ларченко И. М. (2026 г.)*
