from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from src.app_paths import audit_log_path


class AuditLogger:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else audit_log_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log_event(self, event_type: str, payload: dict[str, Any]) -> None:
        record = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": event_type,
            "payload": payload,
        }
        line = json.dumps(record, ensure_ascii=False)

        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def log_decision(
        self,
        symbol: str,
        account_id: str,
        decision: str,
        allowed: bool,
        confidence: float | None = None,
        reasons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            "ai_decision",
            {
                "symbol": symbol,
                "account_id": account_id,
                "decision": decision,
                "allowed": allowed,
                "confidence": confidence,
                "reasons": reasons or [],
                "metadata": metadata or {},
            },
        )

    def log_command(
        self,
        command_id: str,
        action: str,
        account_id: str,
        symbol: str,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.log_event(
            "command",
            {
                "command_id": command_id,
                "action": action,
                "account_id": account_id,
                "symbol": symbol,
                "status": status,
                "metadata": metadata or {},
            },
        )
