"""Security utilities - ensures no sensitive data is exposed in logs or storage."""

import re
from typing import Any, Dict

# Patterns to mask in logs
SENSITIVE_PATTERNS = [
    # Passwords (numeric)
    (r'\b\d{4}\b', '****'),  # 4-digit numbers like 1305
    # API Keys / Tokens
    (r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^\s"\']+)', r'\1****'),
    (r'(token["\']?\s*[:=]\s*["\']?)([^\s"\']+)', r'\1****'),
    (r'(password["\']?\s*[:=]\s*["\']?)([^\s"\']+)', r'\1****'),
    (r'(Bearer\s+)([A-Za-z0-9\-_]{8,})', r'\1****'),
    # GitHub tokens
    (r'gh[pousr]_[A-Za-z0-9]{36,}', 'gh_****'),
    # HF tokens
    (r'hf_[A-Za-z0-9]{34,}', 'hf_****'),
]


def sanitize_log(message: str) -> str:
    """Remove sensitive data from log messages."""
    if not message:
        return message
    
    result = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result


def sanitize_for_storage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Remove sensitive data before storing in lessons/sessions."""
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        key_lower = key.lower()
        
        # Skip sensitive keys entirely
        if any(s in key_lower for s in ['password', 'token', 'key', 'secret', 'auth']):
            result[key] = '****'
        elif isinstance(value, str):
            result[key] = sanitize_log(value)
        elif isinstance(value, dict):
            result[key] = sanitize_for_storage(value)
        elif isinstance(value, list):
            result[key] = [
                sanitize_for_storage(v) if isinstance(v, dict) else sanitize_log(str(v)) if isinstance(v, str) else v
                for v in value
            ]
        else:
            result[key] = value
    
    return result


def truncate_long(value: str, max_length: int = 100) -> str:
    """Truncate long strings for display."""
    if len(value) <= max_length:
        return value
    return value[:max_length // 2] + "..." + value[-max_length // 2:]