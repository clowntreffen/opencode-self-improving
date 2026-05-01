"""Abstract base storage class."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class StorageBase(ABC):
    """Abstract storage interface for lessons and sessions."""

    @abstractmethod
    def save_lesson(self, lesson: Dict[str, Any]) -> bool:
        """Save a lesson to storage."""
        pass

    @abstractmethod
    def get_lessons(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all lessons, optionally filtered by task_type."""
        pass

    @abstractmethod
    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific lesson by ID."""
        pass

    @abstractmethod
    def update_lesson(self, lesson_id: str, updates: Dict[str, Any]) -> bool:
        """Update a lesson (e.g., increment success_count)."""
        pass

    @abstractmethod
    def save_session(self, session: Dict[str, Any]) -> bool:
        """Save session data."""
        pass

    @abstractmethod
    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent sessions."""
        pass

    @abstractmethod
    def save_config(self, key: str, value: Any) -> bool:
        """Save configuration."""
        pass

    @abstractmethod
    def get_config(self, key: str) -> Optional[Any]:
        """Get configuration."""
        pass