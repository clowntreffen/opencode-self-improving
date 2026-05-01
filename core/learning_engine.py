"""Learning Engine - core of the self-improving agent."""

import uuid
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from storage.base import StorageBase
from utils.security import sanitize_for_storage


TASK_TYPES = [
    "file_operations",
    "api_call",
    "tool_execution",
    "permission",
    "validation",
    "configuration",
    "network",
    "general",
]


class LearningEngine:
    """Core engine for learning from errors and predicting approaches."""

    def __init__(self, storage: StorageBase):
        self.storage = storage

    def _make_hash(self, task_type: str, error_pattern: str) -> str:
        key = f"{task_type}:{error_pattern}"
        return hashlib.md5(key.encode()).hexdigest()[:12]

    def learn(self, task_type: str, error_pattern: str, root_cause: str,
              solution: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        safe_context = sanitize_for_storage(context) if context else {}
        existing = self._find_existing(task_type, error_pattern)
        
        if existing:
            updates = {
                "success_count": existing.get("success_count", 0) + 1,
                "solution": solution,
                "root_cause": root_cause,
                "context": safe_context,
                "last_used": datetime.now().isoformat(),
            }
            self.storage.update_lesson(existing["id"], updates)
            return {**existing, **updates}
        
        lesson = {
            "id": str(uuid.uuid4()),
            "task_type": task_type,
            "error_pattern": error_pattern,
            "root_cause": root_cause,
            "solution": solution,
            "context": safe_context,
            "success_count": 1,
            "created": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
        }
        self.storage.save_lesson(lesson)
        return lesson

    def predict(self, task_type: str, context: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
        lessons = self.storage.get_lessons(task_type)
        if not lessons:
            return None
        lessons.sort(key=lambda x: x.get("success_count", 0), reverse=True)
        best = lessons[0]
        return {
            "task_type": best["task_type"],
            "suggested_solution": best["solution"],
            "confidence": min(best.get("success_count", 1) / 5.0, 1.0),
            "based_on_lessons": best.get("success_count", 1),
        }

    def _find_existing(self, task_type: str, error_pattern: str) -> Optional[Dict]:
        lessons = self.storage.get_lessons(task_type)
        for lesson in lessons:
            if lesson.get("error_pattern") == error_pattern:
                return lesson
        return None

    def get_all_lessons(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self.storage.get_lessons(task_type)

    def get_stats(self) -> Dict[str, Any]:
        all_lessons = self.storage.get_lessons()
        stats = {"total_lessons": len(all_lessons), "by_type": {}}
        for lesson in all_lessons:
            tt = lesson.get("task_type", "unknown")
            stats["by_type"][tt] = stats["by_type"].get(tt, 0) + 1
        return stats

    def validate_response(self, response: Any, expected: Optional[str] = None) -> Dict[str, Any]:
        result = {"valid": True, "issues": []}
        if not response:
            result["valid"] = False
            result["issues"].append("Empty response")
            return result

        if isinstance(response, dict):
            if "error" in response:
                result["valid"] = False
                result["issues"].append("API error: " + str(response["error"])[:100])
            if response.get("status_code") and response["status_code"] >= 400:
                result["valid"] = False
                result["issues"].append("HTTP error: " + str(response["status_code"]))

        if isinstance(response, str):
            error_patterns = ["error", "timeout", "failed", "unauthorized", "forbidden"]
            response_lower = response.lower()
            for pattern in error_patterns:
                if pattern in response_lower and len(response) < 100:
                    result["valid"] = False
                    result["issues"].append("Error pattern: " + pattern)
                    break

        if expected:
            response_str = str(response).lower()
            if expected.lower() not in response_str:
                result["valid"] = False
                result["issues"].append("Expected '" + expected + "' not found in response")

        return result

    def save_session_event(self, event_type: str, data: Dict[str, Any]):
        session = {
            "event_type": event_type,
            "data": sanitize_for_storage(data),
            "timestamp": datetime.now().isoformat(),
        }
        self.storage.save_session(session)
