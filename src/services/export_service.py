import csv
import io

from src.models.transaction import Transaction
from src.repositories.base import (
    AccountRepositoryProtocol,
    CategoryRepositoryProtocol,
)


class ExportService:
    """Сервис аппаратного экспорта журнала транзакций в формат CSV UTF-8."""

    def __init__(
        self,
        account_repo: AccountRepositoryProtocol,
        category_repo: CategoryRepositoryProtocol,
    ) -> None:
        self._account_repo = account_repo
        self._category_repo = category_repo

    def export_to_csv(self, transactions: list[Transaction]) -> str:
        """Формирует CSV поток текущей выборки операций."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

        writer.writerow([
            "ID",
            "Дата и время",
            "Тип операции",
            "Счет списания",
            "Счет зачисления",
            "Категория",
            "Сумма (руб)",
        ])

        for tx in transactions:
            account = self._account_repo.get_by_id(tx.account_id)
            account_name = account.name if account else "Неизвестный счет"

            target_name = "-"
            if tx.to_account_id:
                target = self._account_repo.get_by_id(tx.to_account_id)
                target_name = target.name if target else "Неизвестный счет"

            category_name = "-"
            if tx.category_id:
                category = self._category_repo.get_by_id(tx.category_id)
                category_name = category.name if category else "-"

            writer.writerow([
                tx.id,
                tx.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                tx.transaction_type.value,
                account_name,
                target_name,
                category_name,
                f"{tx.amount:.2f}",
            ])

        return output.getvalue()
