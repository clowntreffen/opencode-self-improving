"""HuggingFace Dataset storage - persists lessons/sessions in a private HF dataset."""

import json
import os
import tempfile
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime

from config import config
from .base import StorageBase
from .memory import MemoryStorage

DATASET_ID = "hermesinho/opencode-self-improving-data"


class HFDatasetStorage(StorageBase):
    """Storage using a private HuggingFace Dataset for persistence."""

    def __init__(self):
        self._memory = MemoryStorage()
        self._token = config.HF_TOKEN
        self._api = None
        self._loaded = False
        self._init_api()

    def _init_api(self):
        if not self._token:
            return
        try:
            from huggingface_hub import HfApi
            self._api = HfApi(token=self._token)
        except Exception as e:
            print("HF API init error: " + str(e)[:100])

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        if not self._api:
            return
        try:
            self._load_from_dataset()
        except Exception as e:
            print("Load from dataset error: " + str(e)[:100])

    def _load_from_dataset(self):
        from huggingface_hub import hf_hub_download

        for folder in ["lessons", "sessions"]:
            try:
                index_path = hf_hub_download(
                    repo_id=DATASET_ID,
                    filename=folder + "/index.json",
                    repo_type="dataset",
                    token=self._token,
                )
                with open(index_path, "r") as f:
                    items = json.load(f)
                for item in items:
                    if folder == "lessons":
                        self._memory.save_lesson(item)
                    else:
                        self._memory.save_session(item)
            except Exception:
                pass

    def _persist_to_dataset(self, folder: str, items: List[Dict]):
        if not self._api:
            return
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                filepath = os.path.join(tmpdir, folder, "index.json")
                os.makedirs(os.path.join(tmpdir, folder), exist_ok=True)
                with open(filepath, "w") as f:
                    json.dump(items, f, indent=2)
                self._api.upload_file(
                    path_or_fileobj=filepath,
                    path_in_repo=folder + "/index.json",
                    repo_id=DATASET_ID,
                    repo_type="dataset",
                )
        except Exception as e:
            print("Persist error: " + str(e)[:100])

    def save_lesson(self, lesson: Dict[str, Any]) -> bool:
        self._ensure_loaded()
        result = self._memory.save_lesson(lesson)
        if result:
            self._persist_to_dataset("lessons", self._memory.get_all_lessons())
        return result

    def get_lessons(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return self._memory.get_lessons(task_type)

    def get_lesson(self, lesson_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_loaded()
        return self._memory.get_lesson(lesson_id)

    def update_lesson(self, lesson_id: str, updates: Dict[str, Any]) -> bool:
        self._ensure_loaded()
        result = self._memory.update_lesson(lesson_id, updates)
        if result:
            self._persist_to_dataset("lessons", self._memory.get_all_lessons())
        return result

    def save_session(self, session: Dict[str, Any]) -> bool:
        self._ensure_loaded()
        result = self._memory.save_session(session)
        return result

    def get_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        return self._memory.get_sessions(limit)

    def save_config(self, key: str, value: Any) -> bool:
        self._ensure_loaded()
        return self._memory.save_config(key, value)

    def get_config(self, key: str) -> Optional[Any]:
        self._ensure_loaded()
        return self._memory.get_config(key)

    def get_stats(self) -> Dict[str, int]:
        self._ensure_loaded()
        stats = self._memory.get_stats()
        stats["dataset_enabled"] = self._api is not None
        stats["dataset_id"] = DATASET_ID if self._api else ""
        return stats
