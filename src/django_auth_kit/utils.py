"""Utility functions for environment variable parsing."""

import os
from pathlib import Path
from typing import Mapping


def load_env_file(env_file: Path | None = None, env: Mapping[str, str] | None = None) -> None:
    """Load .env file if it exists. Safe to call multiple times.

    If `env` is provided, loads into that mapping instead of os.environ.
    """
    target = env if env is not None else os.environ

    if env_file is None:
        env_file = Path.cwd() / ".env"
    if env_file.exists():
        # Simple .env parser - no external dependency
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key not in target:
                target[key] = value


def _get_env(name: str, env: Mapping[str, str] | None) -> str | None:
    """Get value from env mapping or os.environ."""
    if env is not None:
        return env.get(name)
    return os.getenv(name)


def env_bool(name: str, default: bool = False, env: Mapping[str, str] | None = None) -> bool:
    """Parse environment variable as boolean."""
    value = _get_env(name, env)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_list(name: str, default: list[str] | None = None, env: Mapping[str, str] | None = None) -> list[str]:
    """Parse comma-separated environment variable as list."""
    value = _get_env(name, env)
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


def env_int(name: str, default: int = 0, env: Mapping[str, str] | None = None) -> int:
    """Parse environment variable as integer."""
    value = _get_env(name, env)
    if value is None:
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def env_str(name: str, default: str = "", env: Mapping[str, str] | None = None) -> str:
    """Get environment variable as string."""
    value = _get_env(name, env)
    return value if value is not None else default