from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _env_path(name: str) -> Path | None:
    raw = os.getenv(name, "").strip()
    return Path(raw).expanduser() if raw else None


def app_home() -> Path:
    override = _env_path("ZONES_HOME")
    if override is not None:
        return override

    if getattr(sys, "frozen", False):
        if os.name == "nt":
            base = Path(os.getenv("PROGRAMDATA") or (Path.home() / "AppData" / "Local"))
            return base / "ZONES"
        return Path.home() / ".zones"

    return PROJECT_ROOT


def data_dir() -> Path:
    return _env_path("ZONES_DATA_DIR") or (app_home() / "data")


def logs_dir() -> Path:
    return _env_path("ZONES_LOG_DIR") or (app_home() / "logs")


def runtime_settings_path() -> Path:
    return _env_path("ZONES_RUNTIME_SETTINGS") or (logs_dir() / "runtime_settings.json")


def signal_model_path() -> Path:
    return _env_path("ZONES_SIGNAL_MODEL") or (logs_dir() / "signal_model.json")


def audit_log_path() -> Path:
    return _env_path("ZONES_AUDIT_LOG") or (logs_dir() / "ai_decisions.jsonl")


def sqlite_database_path() -> Path:
    return _env_path("ZONES_DATABASE_PATH") or (data_dir() / "zones.db")


def default_database_url() -> str:
    if os.getenv("ZONES_DATABASE_URL", "").strip():
        return str(os.getenv("ZONES_DATABASE_URL"))
    return sqlite_database_path().resolve().as_uri().replace("file:///", "sqlite:///")
