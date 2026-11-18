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
        print("8. Экспорт журнала в CSV (Результат доработки)")
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
        print("\\nФильтры журнала (пустое поле — без фильтра).")

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

    def _handle_show_history(self) -> None:
        """Отображает журнал операций с фильтрами."""
        txs = self._read_history_filters()
        if txs is None:
            return

        if not txs:
            print("\\nЖурнал операций пуст.")
            return

        print("\\nЖурнал транзакций:")
        for tx in txs:
            print(
                f"  #{tx.id} | {tx.timestamp.strftime('%d.%m %H:%M')} | "
                f"{tx.transaction_type.value} | {tx.amount:.2f} руб. | "
                f"Счет: {tx.account_id}"
            )

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
        self._handle_show_history()
        raw_tx_id = input("Введите ID транзакции для отмены: ").strip()
        if not raw_tx_id.isdigit():
            print("[!] Некорректный ID транзакции.")
            return
        tx_id = int(raw_tx_id)
        self._tx_svc.delete_transaction(tx_id, self._user_id)
        print("[OK] Транзакция удалена, остаток счета автоматически восстановлен.")

    def _handle_export_csv(self) -> None:
        """Экспортирует отфильтрованные данные в файл CSV."""
        txs = self._read_history_filters()
        if txs is None:
            return

        csv_data = self._exp_svc.export_to_csv(self._user_id, txs)
        filename = "transactions_export.csv"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(csv_data)
        print(f"[OK] Данные выгружены в файл '{filename}' в кодировке UTF-8.")
