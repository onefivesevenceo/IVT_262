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
