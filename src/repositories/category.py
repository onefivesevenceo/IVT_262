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
