"""Perplexity MCP client - optional integration for error analysis."""

import json
import requests
from typing import Optional, Dict, Any

from config import config


class PerplexityClient:
    """Client for Perplexity MCP API."""

    def __init__(self):
        self.enabled = config.PERPLEXITY_ENABLED
        self.url = config.PERPLEXITY_URL
        self._session = requests.Session()

    def analyze_error(self, error_type: str, error_message: str, context: str = "") -> Optional[str]:
        """Ask Perplexity to analyze an error and suggest a fix."""
        if not self.enabled:
            return None

        try:
            prompt = (
                f"Analyze this error and suggest a fix. Be concise.\n\n"
                f"Error type: {error_type}\n"
                f"Error: {error_message[:200]}\n"
            )
            if context:
                prompt += f"Context: {context[:200]}\n"
            prompt += "\nProvide only the fix, no explanation."

            response = self._session.post(
                self.url.replace("/sse", "/api/v1/chat/completions")
                if "/sse" in self.url else self.url,
                json={
                    "model": "auto",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 500,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return None
        except Exception as e:
            print(f"Perplexity error: {e}")
            return None

    def research_approach(self, task_type: str, task_description: str) -> Optional[str]:
        """Research best approach for a task type."""
        if not self.enabled:
            return None

        try:
            prompt = (
                f"What is the best approach for this task type?\n\n"
                f"Task type: {task_type}\n"
                f"Description: {task_description[:200]}\n\n"
                f"Be concise. Provide step-by-step approach."
            )

            response = self._session.post(
                self.url.replace("/sse", "/api/v1/chat/completions")
                if "/sse" in self.url else self.url,
                json={
                    "model": "auto",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 300,
                },
                timeout=30,
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return None
        except Exception as e:
            print(f"Perplexity research error: {e}")
            return None

    def status(self) -> Dict[str, Any]:
        """Check if Perplexity is available."""
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        
        try:
            r = self._session.get(
                self.url.replace("/sse", "/api/v1/models")
                if "/sse" in self.url else f"{self.url}/models",
                timeout=10,
            )
            return {
                "enabled": True,
                "status": "ok" if r.status_code == 200 else f"error_{r.status_code}",
                "url": self.url,
            }
        except Exception as e:
            return {"enabled": True, "status": f"error: {str(e)[:50]}", "url": self.url}
