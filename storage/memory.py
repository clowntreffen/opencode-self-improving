"""In-memory storage (fallback when no bucket is available)."""

from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from .base import StorageBase


class MemoryStorage(StorageBase):
    """In-memory storage - no persistence between restarts."""

    def __init__(self):
        self._lessons: Dict[str, Dict[str, Any]] = {}
        self._sessions: List[Dict[str, Any]] = []
        self._configs: Dict[str, Any] = {}

    def save_lesson(self, lesson: Dict[str, Any]) -> bool:
        if "id" not in lesson:
            lesson["id"] = str(uuid.uuid4())
        if "created" not in lesson:
            lesson["created"] = datetime.now().isoformat()
        
        self._lessons[lesson["id"]] = lesson
        return True

    def get_lessons(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        lessons = list(self._lessons.values())
        if task_type:
            lessons = [l for l in lessons if l.get("task_type") == task_type]
        return sorted(lessons, key=lambda x: x.get("created", ""), reverse=True)

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        return self._lessons.get(lesson_id)

    def update_lesson(self, lesson_id: str, updates: Dict[str, Any]) -> bool:
        if lesson_id in self._lessons:
            self._lessons[lesson_id].update(updates)
            self._lessons[lesson_id]["updated"] = datetime.now().isoformat()
            return True
        return False

    def save_session(self, session: Dict[str, Any]) -> bool:
        if "id" not in session:
            session["id"] = str(uuid.uuid4())
        if "timestamp" not in session:
            session["timestamp"] = datetime.now().isoformat()
        
        self._sessions.append(session)
        # Keep only last 1000 sessions
        if len(self._sessions) > 1000:
            self._sessions = self._sessions[-1000:]
        return True

    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        sessions = sorted(self._sessions, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sessions[:limit]

    def save_config(self, key: str, value: Any) -> bool:
        self._configs[key] = value
        return True

    def get_config(self, key: str) -> Optional[Any]:
        return self._configs.get(key)
    
    def get_stats(self) -> Dict[str, int]:
        return {
            "lessons_count": len(self._lessons),
            "sessions_count": len(self._sessions),
            "config_count": len(self._configs),
        }

    def get_all_lessons(self) -> List[Dict[str, Any]]:
        return list(self._lessons.values())