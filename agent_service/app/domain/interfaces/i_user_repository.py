from abc import ABC, abstractmethod
from typing import Optional, Any


class IUserRepository(ABC):
    """Abstract interface for User persistence operations."""

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[Any]:
        """Fetch user details by email."""
        pass

    @abstractmethod
    def create_user(self, email: str, hashed_password: str) -> None:
        """Create a new user in the database."""
        pass
