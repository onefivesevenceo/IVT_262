from src.models.category import Category, CategoryDirection
from src.repositories.category import CategoryRepository


class CategoryService:
    """Сервис управления категориями доходов и расходов."""

    def __init__(self, category_repo: CategoryRepository) -> None:
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

    def get_by_id(self, category_id: int) -> Category | None:
        """Возвращает категорию по её идентификатору."""
        return self._repo.get_by_id(category_id)
