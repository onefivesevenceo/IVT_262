from decimal import Decimal, InvalidOperation

from src.models.account import AccountType
from src.models.category import Category, CategoryDirection
from src.models.transaction import TransactionType
from src.repositories.base import CategoryRepositoryProtocol
from src.services.account_service import AccountService
from src.services.budget_service import BudgetService
from src.services.export_service import ExportService
from src.services.transaction_service import TransactionService


class TerminalInterface:
    """Консольный интерфейс взаимодействия пользователя с системой CapitalTracker."""

    def __init__(
        self,
        user_id: int,
        account_service: AccountService,
        tx_service: TransactionService,
        budget_service: BudgetService,
        category_repo: CategoryRepositoryProtocol,
        export_service: ExportService,
    ) -> None:
        self._user_id = user_id
        self._acc_svc = account_service
        self._tx_svc = tx_service
        self._bdg_svc = budget_service
        self._cat_repo = category_repo
        self._exp_svc = export_service

    def run(self) -> None:
        """Главный цикл обработки команд терминала."""
        self._seed_default_categories()
        while True:
            self._print_header()
            choice = input("Выберите пункт меню [0-8]: ").strip()

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
            elif choice == "0":
                print("\nЗавершение сеанса. Данные сохранены.")
                break
            else:
                print("\n[!] Некорректный выбор. Повторите ввод.")

    def _seed_default_categories(self) -> None:
        """Инициализирует базовый набор категорий."""
        existing = self._cat_repo.get_all_by_user(self._user_id)
        if not existing:
            self._cat_repo.add(
                Category(0, self._user_id, "Продукты", CategoryDirection.EXPENSE)
            )
            self._cat_repo.add(
                Category(0, self._user_id, "Кафе", CategoryDirection.EXPENSE)
            )
            self._cat_repo.add(
                Category(0, self._user_id, "Зарплата", CategoryDirection.INCOME)
            )

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
        print("0. Выход")
        print("-" * 55)

    def _handle_show_accounts(self) -> None:
        """Показывает перечень счетов."""
        accounts = self._acc_svc.get_user_accounts(self._user_id)
        if not accounts:
            print("\nУ вас пока нет активных счетов.")
            return

        print("\nВаши активные счета:")
        for acc in accounts:
            print(
                f"  [{acc.id}] {acc.name} ({acc.account_type.value}): {acc.balance:.2f} руб."
            )

    def _handle_create_account(self) -> None:
        """Диалог создания счета."""
        name = input("Введите наименование счета: ").strip()
        if not name:
            print("[!] Наименование не может быть пустым.")
            return

        print("Доступные типы: 1. DEBIT, 2. CREDIT, 3. CASH, 4. SAVINGS")
        t_choice = input("Выберите тип [1-4]: ").strip()
        type_map = {
            "1": AccountType.DEBIT,
            "2": AccountType.CREDIT,
            "3": AccountType.CASH,
            "4": AccountType.SAVINGS,
        }
        acc_type = type_map.get(t_choice, AccountType.DEBIT)

        raw_balance = input("Введите начальный остаток: ").strip()
        try:
            balance = Decimal(raw_balance)
            acc = self._acc_svc.create_account(
                self._user_id, name, acc_type, balance
            )
            print(
                f"[OK] Счет '{acc.name}' успешно открыт с балансом {acc.balance:.2f} руб."
            )
        except InvalidOperation:
            print("[!] Ошибка: Некорректный формат денежной суммы.")

    def _handle_add_transaction(self) -> None:
        """Диалог регистрации дохода или расхода."""
        self._handle_show_accounts()
        raw_acc_id = input("Введите ID счета: ").strip()
        if not raw_acc_id.isdigit():
            print("[!] Некорректный ID счета.")
            return
        acc_id = int(raw_acc_id)

        print("Тип: 1. Расход, 2. Доход")
        t_choice = input("Выберите тип [1-2]: ").strip()
        tx_type = (
            TransactionType.EXPENSE
            if t_choice == "1"
            else TransactionType.INCOME
        )

        categories = self._cat_repo.get_all_by_user(self._user_id)
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

        categories = self._cat_repo.get_all_by_user(self._user_id)
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
