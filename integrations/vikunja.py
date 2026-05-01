"""Vikunja MCP client - optional integration for task tracking."""

import json
import requests
from typing import Optional, Dict, Any, List

from config import config


class VikunjaClient:
    """Client for Vikunja MCP API."""

    def __init__(self):
        self.enabled = config.VIKUNJA_ENABLED
        self.url = config.VIKUNJA_URL
        self._session = requests.Session()

    def _api_call(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Optional[Dict]:
        """Make an API call to Vikunja."""
        if not self.enabled:
            return None

        try:
            url = f"http://dietpi:3456/api/v1{endpoint}"
            headers = {"Content-Type": "application/json"}
            
            if method == "GET":
                r = self._session.get(url, headers=headers, timeout=10)
            elif method == "POST":
                r = self._session.post(url, headers=headers, json=data, timeout=10)
            elif method == "PUT":
                r = self._session.put(url, headers=headers, json=data, timeout=10)
            else:
                return None

            if r.status_code in (200, 201):
                return r.json()
            return None
        except Exception as e:
            print(f"Vikunja API error: {e}")
            return None

    def create_lesson_task(self, project_id: int, title: str, description: str) -> Optional[Dict]:
        """Create a task in Vikunja to track a learned lesson."""
        if not self.enabled:
            return None

        data = {
            "project_id": project_id,
            "title": title,
            "description": description,
        }
        return self._api_call("POST", "/tasks", data)

    def get_tasks(self, project_id: int) -> Optional[List[Dict]]:
        """Get tasks from a project."""
        if not self.enabled:
            return None

        result = self._api_call("GET", f"/projects/{project_id}/tasks")
        return result if isinstance(result, list) else None

    def log_session_summary(self, project_id: int, summary: str, session_data: Dict[str, Any]) -> Optional[Dict]:
        """Log a session summary as a Vikunja task."""
        if not self.enabled:
            return None

        description = f"## Session Summary\n\n{summary}\n\n"
        description += f"### Stats\n"
        description += f"- Tasks: {session_data.get('task_count', 0)}\n"
        description += f"- Errors: {session_data.get('error_count', 0)}\n"
        description += f"- Lessons Learned: {session_data.get('lessons_count', 0)}\n"

        data = {
            "project_id": project_id,
            "title": f"Session Summary: {session_data.get('date', 'unknown')}",
            "description": description,
            "done": True,
        }
        return self._api_call("POST", "/tasks", data)

    def status(self) -> Dict[str, Any]:
        """Check if Vikunja is available."""
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}

        try:
            r = self._session.get("http://dietpi:3456/api/v1/info", timeout=10)
            return {
                "enabled": True,
                "status": "ok" if r.status_code == 200 else f"error_{r.status_code}",
                "url": self.url,
            }
        except Exception as e:
            return {"enabled": True, "status": f"error: {str(e)[:50]}", "url": self.url}
