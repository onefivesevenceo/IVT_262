from abc import ABC, abstractmethod

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
        return [cat for cat in self._storage.values() if cat.user_id == user_id]
