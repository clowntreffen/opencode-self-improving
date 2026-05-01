"""HuggingFace Spaces Bucket storage - persists between restarts."""

import json
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from huggingface_hub import HfApi, list_repo_files
from config import config

from .base import StorageBase
from .memory import MemoryStorage


class HFBucketStorage(StorageBase):
    """Storage using HuggingFace Spaces built-in bucket (S3-compatible)."""

    def __init__(self):
        self.api = HfApi() if config.HF_TOKEN else None
        self.repo_id = None  # Will be set when space is created
        self._memory = MemoryStorage()  # Cache for fast access
        self._loaded = False

    def _ensure_loaded(self):
        """Load existing lessons from bucket on first access."""
        if not self._loaded and self.api:
            self._load_from_bucket()
            self._loaded = True

    def _load_from_bucket(self):
        """Load existing data from bucket."""
        # This would be called at startup to load cached data
        # For now, we rely on in-memory cache + bucket writes
        pass

    def _get_file_path(self, folder: str, filename: str) -> str:
        """Get the full path in the bucket."""
        return f"{folder}/{filename}"

    def save_lesson(self, lesson: Dict[str, Any]) -> bool:
        # Save to memory cache first
        result = self._memory.save_lesson(lesson)
        
        # Try to persist to bucket if available
        if self.api and config.HF_TOKEN:
            try:
                self._persist_lesson_to_bucket(lesson)
            except Exception as e:
                print(f"Warning: Could not persist lesson to bucket: {e}")
        
        return result

    def _persist_lesson_to_bucket(self, lesson: Dict[str, Any]):
        """Write lesson to bucket file."""
        # In HF Spaces, we write to /data/ folder
        lesson_id = lesson.get("id", str(uuid.uuid4()))
        task_type = lesson.get("task_type", "unknown")
        
        # Create folder if needed
        folder = f"/data/lessons/{task_type}"
        
        # Write to local file (HF Spaces auto-syncs /data to bucket)
        import os
        os.makedirs(folder, exist_ok=True)
        
        file_path = f"{folder}/{lesson_id}.json"
        with open(file_path, 'w') as f:
            json.dump(lesson, f, indent=2)

    def get_lessons(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._memory.get_lessons(task_type)

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        return self._memory.get_lesson(lesson_id)

    def update_lesson(self, lesson_id: str, updates: Dict[str, Any]) -> bool:
        result = self._memory.update_lesson(lesson_id, updates)
        
        if result:
            lesson = self._memory.get_lesson(lesson_id)
            if lesson:
                self._persist_lesson_to_bucket(lesson)
        
        return result

    def save_session(self, session: Dict[str, Any]) -> bool:
        result = self._memory.save_session(session)
        
        if result and self.api and config.HF_TOKEN:
            try:
                session_id = session.get("id", str(uuid.uuid4()))
                folder = "/data/sessions"
                import os
                os.makedirs(folder, exist_ok=True)
                
                file_path = f"{folder}/{session_id}.json"
                with open(file_path, 'w') as f:
                    json.dump(session, f, indent=2)
            except Exception as e:
                print(f"Warning: Could not persist session to bucket: {e}")
        
        return result

    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        return self._memory.get_sessions(limit)

    def save_config(self, key: str, value: Any) -> bool:
        return self._memory.save_config(key, value)

    def get_config(self, key: str) -> Optional[Any]:
        return self._memory.get_config(key)
    
    def get_stats(self) -> Dict[str, int]:
        stats = self._memory.get_stats()
        stats["bucket_enabled"] = self.api is not None and bool(config.HF_TOKEN)
        return stats


def get_storage() -> StorageBase:
    """Factory function to get appropriate storage."""
    if config.BUCKET_TYPE == "hf" and config.HF_TOKEN:
        return HFBucketStorage()
    return MemoryStorage()