from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enabled"}:
        return True
    if text in {"0", "false", "no", "off", "disabled", ""}:
        return False
    return default


def coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def mask_database_url(value: str) -> str:
    if not value:
        return "local SQLite"
    try:
        parts = urlsplit(value)
    except ValueError:
        return value
    if not parts.password:
        return value
    username = parts.username or ""
    hostname = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    masked_netloc = f"{username}:***@{hostname}{port}" if username else f"***@{hostname}{port}"
    return urlunsplit((parts.scheme, masked_netloc, parts.path, parts.query, parts.fragment))


class RuntimeSettingsStore:
    def __init__(self, path: Path | str = "logs/runtime_settings.json") -> None:
        self.path = Path(path)

    def load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


class SignalModelService:
    def __init__(self, path: Path | str = "logs/signal_model.json") -> None:
        self.path = Path(path)

    def load_model(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def train(self, repository: Any, min_feedback_samples: int = 3) -> dict[str, Any]:
        feedback = repository.feedback_rows()
        report_count = repository.connection_health().get("report_count", 0)
        wins = sum(1 for row in feedback if str(row.get("outcome", "")).lower() == "win")
        losses = sum(1 for row in feedback if str(row.get("outcome", "")).lower() == "loss")
        sample_count = len(feedback)
        ready = sample_count >= max(1, min_feedback_samples)
        if wins > losses:
            bias = "bullish"
        elif losses > wins:
            bias = "defensive"
        else:
            bias = "neutral"
        model = {
            "status": "trained" if ready else "warming_up",
            "training_mode": "feedback" if ready else "heuristic",
            "sample_count": sample_count,
            "report_count": report_count,
            "signal_bias": bias,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "summary": (
                "Model trained from recorded feedback."
                if ready
                else f"Collecting feedback: {sample_count}/{max(1, min_feedback_samples)} samples."
            ),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(model, indent=2), encoding="utf-8")
        return model

    def score_report(self, payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        model = self.load_model()
        execution = payload.get("execution_decision", {}) if isinstance(payload, dict) else {}
        score = coerce_float(execution.get("score"), 0.0)
        threshold = coerce_float(config.get("minimum_trade_score"), 2.0)
        confidence = 0.0 if threshold <= 0 else min(1.0, max(0.0, score / max(threshold * 2, 1.0)))
        direction = str(execution.get("direction") or "neutral")
        if not coerce_bool(config.get("ai_enabled"), True):
            signal = "disabled"
            summary = "AI scoring is disabled in runtime settings."
        elif direction in {"long", "short"} and score >= threshold:
            signal = direction
            summary = "Live setup is aligned with the configured threshold."
        else:
            signal = "neutral"
            summary = "No high-confidence actionable setup yet."
        return {
            "status": model.get("status", "warming_up"),
            "signal": signal,
            "confidence": round(confidence, 3),
            "training_mode": model.get("training_mode", "heuristic"),
            "summary": summary,
        }
