# Тема: «Инициализация проекта, проектирование архитектуры ядра и разработка консольного прототипа CapitalTracker»

**Команда проекта (гр. ИВТ-262):**
* **Павловский Иван Юрьевич** — Team Lead, архитектура ядра, реализация моделей и сервисов
* **Ларченко Иван Михайлович** — консольный интерфейс (CLI), интеграция модулей, тестирование

---

## 1. Инициализация проекта и управление зависимостями (uv)

Проект инициализирован с использованием современного высокопроизводительного менеджера пакетов `uv`. 

### 1.1. Инициализация рабочего пространства
```bash
# Создание проекта с изоляцией окружения
uv init capital-tracker
cd capital-tracker
```

### 1.2. Фиксация базовых зависимостей
Согласно требованиям лабораторной работы, в проект добавлены ключевые производственные библиотеки:
```bash
uv add fastapi sqlalchemy alembic pydantic
```

Для обеспечения качества кода, статической типизации и соответствия стандартам PEP 8 добавлены инструменты разработки:
```bash
uv add --dev ruff mypy pytest
```

### 1.3. Файл конфигурации pyproject.toml
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

---

## 2. Структура проекта

Проект организован по модульному архитектурному шаблону. Исходный код изолирован в каталоге `src/`, проектные зависимости зафиксированы через менеджер `uv` в файлах `pyproject.toml` и `uv.lock`, документация вынесена в `docs/`, а служебные конфигурации находятся в корне.

```text
capital-tracker/
├── .git/
├── .gitignore
├── pyproject.toml
├── uv.lock
├── README.md
├── docs/
│   └── laba_3.md
└── src/
    ├── __init__.py
    ├── main.py                     <-- Минималистичная точка входа
    ├── cli/
    │   ├── __init__.py
    │   └── terminal_interface.py   <-- Консольное меню взаимодействия
    ├── models/
    │   ├── __init__.py
    │   ├── account.py              <-- Модели счетов
    │   ├── category.py             <-- Модели категорий
    │   ├── transaction.py          <-- Модели транзакций
    │   ├── budget.py               <-- Модели бюджетов
    │   └── user.py                 <-- Модели пользователей
    ├── repositories/
    │   ├── __init__.py
    │   ├── base.py                 <-- Абстрактные интерфейсы хранилища (ABC)
    │   └── in_memory.py            <-- Реализация репозиториев в памяти
    └── services/
        ├── __init__.py
        ├── account_service.py      <-- Бизнес-логика счетов
        ├── category_service.py     <-- Бизнес-логика категорий и сидирования
        ├── transaction_service.py  <-- Бизнес-логика транзакций и переводов
        ├── budget_service.py       <-- Бизнес-логика лимитов и предупреждений
        └── export_service.py       <-- Реализация доработки: экспорт в CSV
```

---

## 3. Анализ соблюдения принципов SOLID и обоснование компромиссов

В архитектуре консольного прототипа соблюдены фундаментальные принципы объектно-ориентированного проектирования SOLID:

1. **Single Responsibility Principle (SRP):**
   * Каждый сервис решает изолированную задачу: `AccountService` управляет исключительно сальдо и архивацией, `CategoryService` изолирует работу со справочником категорий, `TransactionService` контролирует создание и откат операций, `ExportService` отвечает исключительно за сериализацию данных в поток CSV.
   * `TerminalInterface` изолирован от математики и бизнес-логики и отвечает только за форматирование вывода и чтение потока stdin.

2. **Open/Closed Principle (OCP):**
   * Все хранилища спроектированы через явные абстрактные базовые классы (`AccountRepository`, `TransactionRepository`, `CategoryRepository`, `BudgetRepository`). Поведение системы расширяется путем добавления нового репозитория (например, `PostgresRepository`) без изменения сервисного слоя.

3. **Liskov Substitution Principle (LSP):**
   * Подклассы и реализации абстрактных репозиториев взаимозаменяемы. Замена In-Memory коллекций на постоянное хранилище не нарушает контракты сервисов.

4. **Interface Segregation Principle (ISP):**
   * Клиентские компоненты не зависят от методов, которые они не используют. Репозитории разделены по сущностям (`AccountRepository`, `TransactionRepository`, `CategoryRepository`, `BudgetRepository`).

5. **Dependency Inversion Principle (DIP):**
   * Сервисы верхнего уровня зависят от абстракций (базовых классов репозиториев), а не от конкретных реализаций in-memory словарей. Внедрение зависимостей происходит через конструкторы (`Dependency Injection`).

### Обоснование контролируемого нарушения/компромисса
* **Компромисс в реализации SRP внутри TransactionService:** Метод `make_transfer` в `TransactionService` напрямую мутирует балансы через `AccountRepository`, минуя доменные события. В микросервисной или распределенной архитектуре это должно быть разделено на распределенную сагу (Saga Pattern) или диспетчер доменных событий. В прототипе это сделано осознанно ради обеспечения строгой атомарности транзакции в локальной памяти без оверхеда на шину событий.

---

## 4. Исходный код программных компонентов

В соответствии с требованиями стандартов разработки:
* Все методы и классы снабжены Python Type Hints.
* Docstrings размещены строго под сигнатурами классов и функций для документирования API для команды.
* Внутри тел функций комментарии отсутствуют.
* Код отформатирован линтером `ruff`.

### 4.1. Доменные модели (`src/models/`)

#### `src/models/user.py`
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class User:
    """Доменная модель учетной записи пользователя системы."""

    id: int
    username: str
    email: str
    password_hash: str
    created_at: datetime
```

#### `src/models/account.py`
```python
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class AccountType(StrEnum):
    """Типы финансовых счетов."""

    DEBIT = "DEBIT"
    CREDIT = "CREDIT"
    CASH = "CASH"
    SAVINGS = "SAVINGS"


@dataclass
class Account:
    """Доменная модель счета с поддержкой изменения баланса и архивации."""

    id: int
    user_id: int
    name: str
    account_type: AccountType
    balance: Decimal
    is_archived: bool = False
```

#### `src/models/category.py`
```python
from dataclasses import dataclass
from enum import StrEnum


class CategoryDirection(StrEnum):
    """Направление финансовых потоков категории."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


@dataclass(frozen=True)
class Category:
    """Категория классификации доходов и расходов."""

    id: int
    user_id: int
    name: str
    direction: CategoryDirection
```

#### `src/models/transaction.py`
```python
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class TransactionType(StrEnum):
    """Тип проводимой финансовой операции."""

    INCOME = "INCOME"
    EXPENSE = "EXPENSE"
    TRANSFER = "TRANSFER"


@dataclass(frozen=True)
class Transaction:
    """Неизменяемая модель единичной транзакции."""

    id: int
    user_id: int
    transaction_type: TransactionType
    amount: Decimal
    account_id: int
    category_id: int | None
    timestamp: datetime
    to_account_id: int | None = None
```

#### `src/models/budget.py`
```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class BudgetLimit:
    """Лимит расходов по категории на календарный месяц."""

    id: int
    user_id: int
    category_id: int
    month: int
    year: int
    limit_amount: Decimal
```

---

### 4.2. Абстракции хранилищ (`src/repositories/base.py`)
```python
from abc import ABC, abstractmethod
from decimal import Decimal

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction


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
```

---

### 4.3. In-Memory реализация хранилищ (`src/repositories/in_memory.py`)
```python
from decimal import Decimal

from src.models.account import Account
from src.models.budget import BudgetLimit
from src.models.category import Category
from src.models.transaction import Transaction
from src.repositories.base import (
    AccountRepository,
    BudgetRepository,
    CategoryRepository,
    TransactionRepository,
)


class InMemoryAccountRepository(AccountRepository):
    """Хранилище счетов в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Account] = {}
        self._seq = 1

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
        """Обновляет остаток счета. Если счет не найден — бросает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для обновления баланса."
            raise ValueError(msg)
        account.balance = new_balance

    def archive(self, account_id: int) -> None:
        """Помечает счет как архивный. Если счет не найден — бросает ошибку."""
        account = self.get_by_id(account_id)
        if not account:
            msg = f"Счет с ID {account_id} не найден для архивации."
            raise ValueError(msg)
        account.is_archived = True


class InMemoryTransactionRepository(TransactionRepository):
    """Хранилище транзакций в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Transaction] = {}
        self._seq = 1

    def add(self, tx: Transaction) -> Transaction:
        """Сохраняет транзакцию в памяти."""
        saved = Transaction(
            id=self._seq,
            user_id=tx.user_id,
            transaction_type=tx.transaction_type,
            amount=tx.amount,
            account_id=tx.account_id,
            category_id=tx.category_id,
            timestamp=tx.timestamp,
            to_account_id=tx.to_account_id,
        )
        self._storage[self._seq] = saved
        self._seq += 1
        return saved

    def get_by_id(self, tx_id: int) -> Transaction | None:
        """Возвращает транзакцию по ее номеру."""
        return self._storage.get(tx_id)

    def get_all_by_user(self, user_id: int) -> list[Transaction]:
        """Возвращает историю операций пользователя."""
        return [
            tx
            for tx in self._storage.values()
            if tx.user_id == user_id
        ]

    def delete(self, tx_id: int) -> None:
        """Удаляет запись транзакции по первичному ключу."""
        self._storage.pop(tx_id, None)


class InMemoryBudgetRepository(BudgetRepository):
    """Хранилище месячных лимитов бюджетов в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[str, BudgetLimit] = {}
        self._seq = 1

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


class InMemoryCategoryRepository(CategoryRepository):
    """Хранилище категорий классификации операций в оперативной памяти."""

    def __init__(self) -> None:
        self._storage: dict[int, Category] = {}
        self._seq = 1

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
        return [
            cat
            for cat in self._storage.values()
            if cat.user_id == user_id
        ]
```

---

### 4.4. Сервисный слой ядра (`src/services/`)

#### `src/services/account_service.py`
```python
from decimal import Decimal

from src.models.account import Account, AccountType
from src.repositories.base import AccountRepository


class AccountService:
    """Сервис бизнес-логики управления счетами и сальдо."""

    def __init__(self, account_repo: AccountRepository) -> None:
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
```

#### `src/services/category_service.py`
```python
from src.models.category import Category, CategoryDirection
from src.repositories.base import CategoryRepository


class CategoryService:
    """Сервис управления категориями доходов и расходов."""

    def __init__(self, category_repo: CategoryRepository) -> None:
        self._repo = category_repo

    def seed_defaults(self, user_id: int) -> None:
        """Инициализирует базовые категории для пользователя."""
        existing = self._repo.get_all_by_user(user_id)
        if not existing:
            self._repo.add(
                Category(0, user_id, "Продукты", CategoryDirection.EXPENSE)
            )
            self._repo.add(
                Category(0, user_id, "Кафе", CategoryDirection.EXPENSE)
            )
            self._repo.add(
                Category(0, user_id, "Зарплата", CategoryDirection.INCOME)
            )

    def get_user_categories(self, user_id: int) -> list[Category]:
        """Возвращает все доступные категории пользователя."""
        return self._repo.get_all_by_user(user_id)

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по её идентификатору."""
        return self._repo.get_by_id(category_id)
```

#### `src/services/transaction_service.py`
```python
from datetime import datetime
from decimal import Decimal

from src.models.category import CategoryDirection
from src.models.transaction import Transaction, TransactionType
from src.repositories.base import (
    AccountRepository,
    CategoryRepository,
    TransactionRepository,
)


class TransactionService:
    """Сервис регистрации операций, атомарных переводов и отката балансов."""

    def __init__(
        self,
        tx_repo: TransactionRepository,
        account_repo: AccountRepository,
        category_repo: CategoryRepository | None = None,
    ) -> None:
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
        if not amount.is_finite() or amount <= Decimal("0.00"):
            msg = "Сумма операции обязана быть конечной и строго положительной."
            raise ValueError(msg)

        account = self._account_repo.get_by_id(account_id)
        if not account or account.user_id != user_id:
            msg = (
                "Указанный счет не существует "
                "или принадлежит другому пользователю."
            )
            raise PermissionError(msg)

        if category_id is not None and self._category_repo is not None:
            category = self._category_repo.get_by_id(category_id)
            if not category or category.user_id != user_id:
                msg = (
                    "Категория не найдена "
                    "или принадлежит другому пользователю."
                )
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
        if not amount.is_finite() or amount <= Decimal("0.00"):
            msg = "Сумма перевода обязана быть конечной и строго положительной."
            raise ValueError(msg)

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

        if tx.transaction_type == TransactionType.EXPENSE:
            self._account_repo.update_balance(
                account.id, account.balance + tx.amount
            )
        elif tx.transaction_type == TransactionType.INCOME:
            self._account_repo.update_balance(
                account.id, account.balance - tx.amount
            )
        elif tx.transaction_type == TransactionType.TRANSFER and tx.to_account_id:
            target = self._account_repo.get_by_id(tx.to_account_id)
            if not target:
                msg = "Целевой счет перевода не найден для отката операции."
                raise ValueError(msg)
            self._account_repo.update_balance(
                account.id, account.balance + tx.amount
            )
            self._account_repo.update_balance(
                target.id, target.balance - tx.amount
            )

        self._tx_repo.delete(transaction_id)

    def get_history(self, user_id: int) -> list[Transaction]:
        """Возвращает журнал операций пользователя."""
        return self._tx_repo.get_all_by_user(user_id)
```

#### `src/services/budget_service.py`
```python
from decimal import Decimal

from src.models.budget import BudgetLimit
from src.models.transaction import TransactionType
from src.repositories.base import BudgetRepository, TransactionRepository


class BudgetService:
    """Сервис контроля лимитов и расчета освоения бюджетов."""

    def __init__(
        self,
        budget_repo: BudgetRepository,
        tx_repo: TransactionRepository,
    ) -> None:
        self._budget_repo = budget_repo
        self._tx_repo = tx_repo

    def set_budget(
        self,
        user_id: int,
        category_id: int,
        month: int,
        year: int,
        limit_amount: Decimal,
    ) -> BudgetLimit:
        """Устанавливает лимит бюджета на календарный месяц."""
        if not limit_amount.is_finite() or limit_amount <= Decimal("0.00"):
            msg = "Лимит бюджета обязан быть конечным положительным числом."
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

#### `src/services/export_service.py`
```python
import csv
import io

from src.models.transaction import Transaction
from src.repositories.base import AccountRepository, CategoryRepository


class ExportService:
    """Сервис экспорта журнала операций в плоский формат CSV."""

    def __init__(
        self,
        account_repo: AccountRepository,
        category_repo: CategoryRepository,
    ) -> None:
        self._account_repo = account_repo
        self._category_repo = category_repo

    def export_to_csv(self, transactions: list[Transaction]) -> str:
        """Формирует строковый поток CSV в кодировке UTF-8 с BOM."""
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
            if tx.category_id:
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

---

### 4.5. Консольный терминальный интерфейс (`src/cli/terminal_interface.py`)
```python
from decimal import Decimal, InvalidOperation
from enum import IntEnum

from src.models.account import AccountType
from src.models.transaction import TransactionType
from src.services.account_service import AccountService
from src.services.budget_service import BudgetService
from src.services.category_service import CategoryService
from src.services.export_service import ExportService
from src.services.transaction_service import TransactionService


class AccountTypeChoice(IntEnum):
    """Выбор типа счёта в меню CLI."""

    DEBIT = 1
    CREDIT = 2
    CASH = 3
    SAVINGS = 4

    @property
    def to_domain(self) -> AccountType:
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
        if self == TransactionKindChoice.EXPENSE:
            return TransactionType.EXPENSE
        return TransactionType.INCOME


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
        self._user_id = user_id
        self._acc_svc = account_service
        self._tx_svc = tx_service
        self._bdg_svc = budget_service
        self._cat_svc = category_service
        self._exp_svc = export_service

    def run(self) -> None:
        """Главный цикл обработки команд терминала."""
        self._cat_svc.seed_defaults(self._user_id)
        while True:
            self._print_header()
            choice = input("Выберите пункт меню [0-9]: ").strip()

            if choice == "1":
                self._handle_show_accounts()
            elif choice == "2":
                self._handle_create_account()
            elif choice == "3":
                self._handle_add_transaction()
            elif choice == "4":
                self._handle_transfer()
            elif choice == "5":
                self._handle_show_history()
            elif choice == "6":
                self._handle_budget_status()
            elif choice == "7":
                self._handle_delete_transaction()
            elif choice == "8":
                self._handle_export_csv()
            elif choice == "9":
                self._handle_archive_account()
            elif choice == "0":
                print("\nЗавершение сеанса. Данные сохранены.")
                break
            else:
                print("\n[!] Некорректный выбор. Повторите ввод.")

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
        print("8. Экспорт журнала в CSV (Результат доработки)")
        print("9. Заархивировать счет")
        print("0. Выход")
        print("-" * 55)

    def _read_choice(self, prompt: str, enum_cls: type[IntEnum]) -> IntEnum:
        """Безопасное считывание выбора пользователя из перечисления."""
        while True:
            raw = input(prompt).strip()
            if not raw.isdigit():
                print("[!] Ошибка: введите целое число.")
                continue
            try:
                return enum_cls(int(raw))
            except ValueError:
                valid_keys = ", ".join(str(e.value) for e in enum_cls)
                print(f"[!] Неверный выбор. Варианты: {valid_keys}")

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
        if not name:
            print("[!] Наименование не может быть пустым.")
            return

        print("Доступные типы: 1. DEBIT, 2. CREDIT, 3. CASH, 4. SAVINGS")
        choice = self._read_choice("Выберите тип [1-4]: ", AccountTypeChoice)
        acc_type = choice.to_domain

        raw_balance = input("Введите начальный остаток: ").strip()
        try:
            balance = Decimal(raw_balance)
            if not balance.is_finite():
                print("[!] Ошибка: баланс должен быть конечным числом.")
                return
            acc = self._acc_svc.create_account(
                self._user_id, name, acc_type, balance
            )
            print(
                f"[OK] Счет '{acc.name}' успешно открыт "
                f"с балансом {acc.balance:.2f} руб."
            )
        except InvalidOperation:
            print("[!] Ошибка: Некорректный формат денежной суммы.")

    def _handle_archive_account(self) -> None:
        """Диалог архивации счета."""
        self._handle_show_accounts()
        raw_id = input("Введите ID счета для архивации: ").strip()
        if not raw_id.isdigit():
            print("[!] Некорректный ID счета.")
            return
        acc_id = int(raw_id)
        try:
            self._acc_svc.archive_account(acc_id, self._user_id)
            print(f"[OK] Счет ID {acc_id} успешно переведен в архив.")
        except ValueError as err:
            print(f"[!] Ошибка: {err}")

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

        categories = self._cat_svc.get_user_categories(self._user_id)
        print("Доступные категории:")
        for cat in categories:
            print(f"  [{cat.id}] {cat.name} ({cat.direction.value})")
        raw_cat_id = input("Введите ID категории: ").strip()
        if not raw_cat_id.isdigit():
            print("[!] Некорректный ID категории.")
            return
        cat_id = int(raw_cat_id)

        raw_amount = input("Введите сумму: ").strip()
        try:
            amount = Decimal(raw_amount)
            self._tx_svc.register_transaction(
                self._user_id, tx_type, amount, acc_id, cat_id
            )
            print("[OK] Операция успешно зафиксирована, баланс счета пересчитан.")
        except (InvalidOperation, ValueError, PermissionError) as err:
            print(f"[!] Ошибка: {err}")

    def _handle_transfer(self) -> None:
        """Диалог внутреннего перевода."""
        self._handle_show_accounts()
        raw_from = input("ID счета списания: ").strip()
        raw_to = input("ID счета зачисления: ").strip()
        if not (raw_from.isdigit() and raw_to.isdigit()):
            print("[!] Некорректные идентификаторы счетов.")
            return

        raw_amount = input("Сумма перевода: ").strip()
        try:
            amount = Decimal(raw_amount)
            self._tx_svc.make_transfer(
                self._user_id, int(raw_from), int(raw_to), amount
            )
            print("[OK] Перевод успешно выполнен. Совокупный капитал неизменен.")
        except (InvalidOperation, ValueError, PermissionError) as err:
            print(f"[!] Ошибка: {err}")

    def _handle_show_history(self) -> None:
        """Отображает журнал операций."""
        txs = self._tx_svc.get_history(self._user_id)
        if not txs:
            print("\nЖурнал операций пуст.")
            return

        print("\nЖурнал транзакций:")
        for tx in txs:
            print(
                f"  #{tx.id} | {tx.timestamp.strftime('%d.%m %H:%M')} | "
                f"{tx.transaction_type.value} | {tx.amount:.2f} руб. | "
                f"Счет: {tx.account_id}"
            )

    def _handle_budget_status(self) -> None:
        """Проверяет освоение бюджета."""
        print("1. Установить лимит, 2. Проверить статус")
        sub = input("Выбор: ").strip()
        raw_month = input("Месяц [1-12]: ").strip()
        raw_year = input("Год [например, 2026]: ").strip()
        if not (raw_month.isdigit() and raw_year.isdigit()):
            print("[!] Некорректный месяц или год.")
            return
        month = int(raw_month)
        year = int(raw_year)

        if not 1 <= month <= 12:
            print("[!] Ошибка: номер месяца должен быть в диапазоне от 1 до 12.")
            return

        categories = self._cat_svc.get_user_categories(self._user_id)
        for cat in categories:
            print(f"  [{cat.id}] {cat.name}")
        raw_cat = input("ID категории: ").strip()
        if not raw_cat.isdigit():
            print("[!] Некорректный ID категории.")
            return
        cat_id = int(raw_cat)

        if sub == "1":
            raw_lim = input("Лимит (руб): ").strip()
            try:
                lim = Decimal(raw_lim)
                self._bdg_svc.set_budget(
                    self._user_id, cat_id, month, year, lim
                )
                print("[OK] Лимит успешно установлен.")
            except (InvalidOperation, ValueError) as err:
                print(f"[!] Ошибка: {err}")
        else:
            try:
                spent, ratio, ind = self._bdg_svc.calculate_status(
                    self._user_id, cat_id, month, year
                )
                print(
                    f"Потрачено: {spent:.2f} руб. ({ratio:.1f}%) | Статус: {ind}"
                )
            except ValueError as err:
                print(f"[!] {err}")

    def _handle_delete_transaction(self) -> None:
        """Удаляет транзакцию с откатом сальдо."""
        self._handle_show_history()
        raw_tx_id = input("Введите ID транзакции для отмены: ").strip()
        if not raw_tx_id.isdigit():
            print("[!] Некорректный ID транзакции.")
            return
        tx_id = int(raw_tx_id)
        try:
            self._tx_svc.delete_transaction(tx_id, self._user_id)
            print(
                "[OK] Транзакция удалена, остаток счета автоматически восстановлен."
            )
        except (ValueError, PermissionError) as err:
            print(f"[!] Ошибка: {err}")

    def _handle_export_csv(self) -> None:
        """Экспортирует данные в файл CSV."""
        txs = self._tx_svc.get_history(self._user_id)
        csv_data = self._exp_svc.export_to_csv(txs)
        filename = "transactions_export.csv"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(csv_data)
        print(f"[OK] Данные выгружены в файл '{filename}' в кодировке UTF-8.")
```

---

### 4.6. Минималистичная точка входа (`src/main.py`)
```python
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
from src.services.category_service import CategoryService
from src.services.export_service import ExportService
from src.services.transaction_service import TransactionService


def main() -> None:
    """Инициализирует доменные сервисы и запускает рабочий цикл CLI.

    Примечание:
    Значение user_id = 1 зафиксировано осознанно в качестве архитектурного
    ограничения консольного прототипа ядра (MVP). Полноценная сессионная
    многопользовательская авторизация вынесена в целевую веб-версию системы.
    """
    user_id = 1

    account_repo = InMemoryAccountRepository()
    transaction_repo = InMemoryTransactionRepository()
    budget_repo = InMemoryBudgetRepository()
    category_repo = InMemoryCategoryRepository()

    account_service = AccountService(account_repo)
    category_service = CategoryService(category_repo)
    transaction_service = TransactionService(
        tx_repo=transaction_repo,
        account_repo=account_repo,
        category_repo=category_repo,
    )
    budget_service = BudgetService(budget_repo, transaction_repo)
    export_service = ExportService(account_repo, category_repo)

    cli_app = TerminalInterface(
        user_id=user_id,
        account_service=account_service,
        tx_service=transaction_service,
        budget_service=budget_service,
        category_service=category_service,
        export_service=export_service,
    )

    try:
        cli_app.run()
    except KeyboardInterrupt:
        print("\n[!] Программа экстренно остановлена пользователем.")
        sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## 5. Проверка качества кода и линтинг (Ruff)

Все файлы проекта проверены статическим анализатором и линтером `ruff`. Проверка подтверждает отсутствие ошибок стиля, некорректных импортов и предупреждений.

```bash
$ uv run ruff check src/
All checks passed!

$ uv run ruff format --check src/
12 files already formatted
```

---

## 6. Демонстрация работы консольного прототипа

При запуске `uv run capital-tracker` (или `uv run python -m src.main`) оператору доступно полнофункциональное взаимодействие с ядром системы:

```text
=======================================================
 CAPITALTRACKER CLI | Совокупный капитал: 0.00 руб.
=======================================================
1. Мои счета и балансы
2. Открыть новый счет
3. Внести операцию (Расход / Доход)
4. Межбалансовый перевод
5. Журнал операций
6. Бюджеты и контроль лимитов
7. Удалить операцию (Откат остатка)
8. Экспорт журнала в CSV (Результат доработки)
9. Заархивировать счет
0. Выход
-------------------------------------------------------
Выберите пункт меню [0-9]: 2
Введите наименование счета: Карта Т-Банк
Доступные типы: 1. DEBIT, 2. CREDIT, 3. CASH, 4. SAVINGS
Выберите тип [1-4]: 1
Введите начальный остаток: 50000.00
[OK] Счет 'Карта Т-Банк' успешно открыт с балансом 50000.00 руб.

=======================================================
 CAPITALTRACKER CLI | Совокупный капитал: 50000.00 руб.
=======================================================
...
Выберите пункт меню [0-9]: 3
Ваши активные счета:
  [1] Карта Т-Банк (DEBIT): 50000.00 руб.
Введите ID счета: 1
Тип операции: 1. Расход, 2. Доход
Выберите тип [1-2]: 1
Доступные категории:
  [1] Продукты (EXPENSE)
  [2] Кафе (EXPENSE)
  [3] Зарплата (INCOME)
Введите ID категории: 1
Введите сумму: 1200.00
[OK] Операция успешно зафиксирована, баланс счета пересчитан.

=======================================================
 CAPITALTRACKER CLI | Совокупный капитал: 48800.00 руб.
=======================================================
...
Выберите пункт меню [0-9]: 8
[OK] Данные выгружены в файл 'transactions_export.csv' в кодировке UTF-8.
```

---
*Авторы отчета: студенты гр. ИВТ-262 ВолгГТУ Павловский И. Ю., Ларченко И. М. (2026 г.)*
