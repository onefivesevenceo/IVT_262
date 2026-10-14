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
