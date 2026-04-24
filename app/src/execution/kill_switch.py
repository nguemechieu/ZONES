from __future__ import annotations

import threading
import time
from typing import Any


class GlobalKillSwitch:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._enabled = False
        self._reason = ""
        self._activated_at = ""

    def activate(self, reason: str) -> None:
        with self._lock:
            self._enabled = True
            self._reason = reason.strip() or "manual activation"
            self._activated_at = time.strftime("%Y-%m-%d %H:%M:%S")

    def clear(self) -> None:
        with self._lock:
            self._enabled = False
            self._reason = ""
            self._activated_at = ""

    def is_active(self) -> bool:
        with self._lock:
            return self._enabled

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active": self._enabled,
                "reason": self._reason,
                "activated_at": self._activated_at,
            }

    def assert_allows(self, action: str) -> None:
        with self._lock:
            if not self._enabled:
                return

            blocked_actions = {
                "queue_command",
                "market_buy",
                "market_sell",
                "buy_limit",
                "sell_limit",
                "buy_stop",
                "sell_stop",
            }

            if action in blocked_actions:
                raise PermissionError(
                    f"Global kill-switch active: {self._reason}")
