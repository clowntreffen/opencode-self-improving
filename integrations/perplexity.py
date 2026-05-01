"""Perplexity client - calls Perplexity Gradio Space via API."""

import json
import requests
from typing import Optional, Dict, Any

from config import config


class PerplexityClient:
    """Client for Perplexity Gradio Space API."""

    def __init__(self):
        self.enabled = config.PERPLEXITY_ENABLED
        self.base_url = config.PERPLEXITY_URL.rsplit("/gradio_api", 1)[0] if "/gradio_api" in config.PERPLEXITY_URL else config.PERPLEXITY_URL.rsplit("/sse", 1)[0]
        self._session = requests.Session()
        if config.HF_TOKEN:
            self._session.headers["Authorization"] = "Bearer " + config.HF_TOKEN

    def _call_gradio(self, endpoint: str, data: list, timeout: int = 60) -> Optional[str]:
        try:
            r = self._session.post(
                self.base_url + "/gradio_api/call/" + endpoint,
                json={"data": data},
                timeout=timeout,
            )
            if r.status_code != 200:
                return None

            event_id = r.json().get("event_id")
            if not event_id:
                return None

            r2 = self._session.get(
                self.base_url + "/gradio_api/call/" + endpoint + "/" + event_id,
                stream=True,
                timeout=timeout,
            )

            for line in r2.iter_lines():
                if line:
                    decoded = line.decode()
                    if decoded.startswith("data: ") and "[DONE]" not in decoded:
                        payload = decoded[6:]
                        try:
                            parsed = json.loads(payload)
                            if isinstance(parsed, list) and len(parsed) > 0:
                                return parsed[0] if isinstance(parsed[0], str) else json.dumps(parsed[0])
                        except (json.JSONDecodeError, IndexError):
                            return payload[:500]
            return None
        except Exception as e:
            print("Perplexity call error: " + str(e)[:100])
            return None

    def analyze_error(self, error_type: str, error_message: str, context: str = "") -> Optional[str]:
        if not self.enabled:
            return None

        prompt = (
            "Analyze this error and suggest a concise fix.\n\n"
            "Error type: " + error_type + "\n"
            "Error: " + error_message[:200] + "\n"
        )
        if context:
            prompt += "Context: " + context[:200] + "\n"
        prompt += "\nProvide only the fix, no explanation."

        return self._call_gradio("search_sync", [prompt, "auto"])

    def research_approach(self, task_type: str, task_description: str) -> Optional[str]:
        if not self.enabled:
            return None

        prompt = (
            "What is the best approach for this task?\n\n"
            "Task type: " + task_type + "\n"
            "Description: " + task_description[:200] + "\n\n"
            "Be concise. Step-by-step approach."
        )

        return self._call_gradio("search_sync", [prompt, "auto"])

    def status(self) -> Dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}

        try:
            r = self._session.get(self.base_url + "/gradio_api/info", timeout=10)
            if r.status_code == 200:
                info = r.json()
                named = list(info.get("named_endpoints", {}).keys())
                return {"enabled": True, "status": "ok", "url": self.base_url, "endpoints": named}
            return {"enabled": True, "status": "error_" + str(r.status_code), "url": self.base_url}
        except Exception as e:
            return {"enabled": True, "status": "error: " + str(e)[:60], "url": self.base_url}
