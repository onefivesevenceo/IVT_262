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
