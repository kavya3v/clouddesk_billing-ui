"""Server-side settings; no import-time credential reads or logging."""
import os
from urllib.parse import urlsplit
from backend.errors import ConfigurationError


def supabase_settings() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        raise ConfigurationError("Supabase settings are missing.")
    try:
        parts = urlsplit(url)
        valid = (parts.scheme == "https" and parts.hostname and not parts.username
                 and not parts.password and not parts.query and not parts.fragment and not parts.path)
    except ValueError:
        valid = False
    if not valid:
        raise ConfigurationError("Supabase project origin is invalid.")
    return url, key


def require_pipeline_settings() -> None:
    supabase_settings()
    if not os.environ.get("FIREWORKS_API_KEY", "").strip():
        raise ConfigurationError("Fireworks settings are missing.")
