import re
from typing import Any, Dict, List, Union

# Fields whose values should be masked
_SENSITIVE_KEYS = {
    "password", "hashed_password", "secret", "token", "access_token",
    "refresh_token", "api_key", "apikey", "api_secret", "private_key",
    "jwt_secret", "authorization", "x-api-key", "cookie",
    "nvidia_api_key", "mongodb_url",
}

_MASK = "***REDACTED***"


def mask_secrets(data: Any, _depth: int = 0) -> Any:
    """Recursively replace sensitive values in dicts/lists with a redaction marker."""
    if _depth > 10:
        return data  # prevent infinite recursion on circular refs

    if isinstance(data, dict):
        return {
            k: _MASK if k.lower() in _SENSITIVE_KEYS else mask_secrets(v, _depth + 1)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_secrets(item, _depth + 1) for item in data]
    if isinstance(data, str):
        # Mask bearer tokens inline
        data = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", r"\1***", data)
        return data
    return data
