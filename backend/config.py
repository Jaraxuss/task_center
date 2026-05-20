from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
DEFAULT_DB_FILENAME = "task_center.db"

DEFAULT_CORS_ORIGINS = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]


def _load_dotenv() -> dict[str, str]:
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


_DOTENV = _load_dotenv()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is not None:
        return value
    return _DOTENV.get(name, default)


@dataclass(frozen=True)
class Settings:
    api_host: str
    api_port: int
    cors_origins: list[str]
    database_path: Path
    database_url: str
    feishu_app_id: str | None
    feishu_app_secret: str | None
    feishu_default_receive_id: str | None
    feishu_default_receive_id_type: str
    reminder_worker_interval_seconds: int = 30
    reminder_max_retries: int = 3


def _int_env(name: str, default: int, *, minimum: int | None = None) -> int:
    raw = _env(name)
    if raw is None or not raw.strip():
        value = default
    else:
        value = int(raw)
    if minimum is not None:
        return max(value, minimum)
    return value


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip().rstrip("/") for item in value.split(",") if item.strip()]


def _resolve_database(env_path: str | None, env_url: str | None) -> tuple[Path, str]:
    """Resolve the SQLite database location.

    Resolution order:
    1. ``TASK_CENTER_DATABASE_URL`` (must be a SQLite URL); ``database_path`` is
       parsed from it for callers that still need a filesystem path.
    2. ``TASK_CENTER_DATABASE_PATH`` (filesystem path, absolute or relative
       to backend dir).
    3. Default ``backend/data/task_center.db``.
    """

    if env_url:
        url = env_url.strip()
        # Expect formats like sqlite:///abs/path or sqlite:///:memory:
        if not url.startswith("sqlite"):
            raise ValueError("TASK_CENTER_DATABASE_URL must start with 'sqlite'")
        # Best-effort path extraction; fine if it's :memory: (Path will still hold a sentinel).
        if ":memory:" in url:
            return Path(":memory:"), url
        # sqlite:///abs/path or sqlite:////abs/path
        without_scheme = url.split("sqlite:///", 1)[-1]
        return Path(without_scheme), url

    if env_path:
        path = Path(env_path).expanduser()
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
    else:
        path = DEFAULT_DATA_DIR / DEFAULT_DB_FILENAME
    return path, f"sqlite:///{path}"


def get_settings() -> Settings:
    api_host = (_env("TASK_CENTER_API_HOST", "0.0.0.0") or "0.0.0.0").strip() or "0.0.0.0"
    api_port = int(_env("TASK_CENTER_API_PORT", "8000") or "8000")
    cors_origins = _split_csv(_env("TASK_CENTER_CORS_ORIGINS")) or DEFAULT_CORS_ORIGINS
    database_path, database_url = _resolve_database(
        env_path=_env("TASK_CENTER_DATABASE_PATH"),
        env_url=_env("TASK_CENTER_DATABASE_URL"),
    )
    return Settings(
        api_host=api_host,
        api_port=api_port,
        cors_origins=cors_origins,
        database_path=database_path,
        database_url=database_url,
        # Prefer TaskCenter-scoped names, but keep FEISHU_* as a convenient
        # compatibility fallback for existing local scripts.
        feishu_app_id=_env("TASK_CENTER_FEISHU_APP_ID") or _env("FEISHU_APP_ID"),
        feishu_app_secret=_env("TASK_CENTER_FEISHU_APP_SECRET") or _env("FEISHU_APP_SECRET"),
        feishu_default_receive_id=_env("TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID"),
        feishu_default_receive_id_type=_env("TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE", "open_id") or "open_id",
        reminder_worker_interval_seconds=_int_env("TASK_CENTER_REMINDER_WORKER_INTERVAL_SECONDS", 30, minimum=5),
        reminder_max_retries=_int_env("TASK_CENTER_REMINDER_MAX_RETRIES", 3, minimum=1),
    )
