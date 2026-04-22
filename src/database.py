from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class LearningRepository:
    def __init__(self, path: Path | str | None = None, database_url: str | None = None) -> None:
        self.database_url = database_url or ""
        self.backend = "sqlite"
        self.error = ""
        self.path = self._resolve_sqlite_path(path, database_url)
        self._ensure_schema()

    def _resolve_sqlite_path(self, path: Path | str | None, database_url: str | None) -> Path:
        if database_url:
            parsed = urlparse(database_url)
            if parsed.scheme and parsed.scheme != "sqlite":
                self.backend = parsed.scheme
                self.error = f"Unsupported database backend '{parsed.scheme}'. Falling back to local SQLite."
                return Path("logs/zones.sqlite")
            if parsed.scheme == "sqlite":
                if parsed.netloc and parsed.path:
                    return Path(f"//{parsed.netloc}{parsed.path}")
                if parsed.path:
                    return Path(parsed.path.lstrip("/")) if parsed.path.startswith("/") and ":" not in parsed.path else Path(parsed.path)
        return Path(path or "logs/zones.sqlite")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    setup_direction TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    pnl REAL NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    params TEXT NOT NULL,
                    message TEXT NOT NULL DEFAULT '',
                    recorded_at TEXT NOT NULL DEFAULT ''
                )
                """
            )

    def save_report(self, payload: dict[str, Any]) -> None:
        created_at = str(payload.get("created_at") or _utc_now())
        account_id = str(payload.get("account", {}).get("account_id") or payload.get("account_id") or "demo")
        symbol = str(payload.get("symbol") or "EURUSD")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO reports (created_at, account_id, symbol, payload) VALUES (?, ?, ?, ?)",
                (created_at, account_id, symbol, json.dumps(payload)),
            )

    def recent_reports(self, limit: int = 5) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT created_at, account_id, symbol, payload FROM reports ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        reports: list[dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(row["payload"])
            except json.JSONDecodeError:
                payload = {}
            reports.append(
                {
                    "created_at": row["created_at"],
                    "account_id": row["account_id"],
                    "symbol": row["symbol"],
                    "payload": payload,
                }
            )
        return reports

    def latest_report(self, account_id: str | None = None, symbol: str | None = None) -> dict[str, Any] | None:
        clauses: list[str] = []
        params: list[str] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT payload FROM reports {where} ORDER BY id DESC LIMIT 1",
                params,
            ).fetchone()
        if not row:
            return None
        try:
            payload = json.loads(row["payload"])
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    def tracked_symbols(self, account_id: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[str] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT symbol, account_id, MAX(created_at) AS last_seen
                FROM reports
                {where}
                GROUP BY symbol, account_id
                ORDER BY last_seen DESC
                LIMIT 50
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def record_feedback(
        self,
        *,
        created_at: str,
        symbol: str,
        timeframe: str,
        setup_direction: str,
        outcome: str,
        pnl: float,
        notes: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO feedback (created_at, symbol, timeframe, setup_direction, outcome, pnl, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (created_at or _utc_now(), symbol, timeframe, setup_direction, outcome, float(pnl), notes),
            )

    def feedback_rows(self, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM feedback ORDER BY id DESC"
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (max(1, int(limit)),)
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def add_command(self, command: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO commands (created_at, account_id, symbol, type, status, params, message, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    command["created_at"],
                    command["account_id"],
                    command["symbol"],
                    command["type"],
                    command.get("status", "pending"),
                    json.dumps(command.get("params", {})),
                    command.get("message", ""),
                    command.get("recorded_at", ""),
                ),
            )

    def command_rows(self, account_id: str | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[str] = []
        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM commands {where} ORDER BY id DESC LIMIT 100",
                params,
            ).fetchall()
        commands = []
        for row in rows:
            item = dict(row)
            try:
                item["params"] = json.loads(item.get("params") or "{}")
            except json.JSONDecodeError:
                item["params"] = {}
            commands.append(item)
        return commands

    def connection_health(self) -> dict[str, Any]:
        with self._connect() as conn:
            report_count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
            feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
            command_count = conn.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        return {
            "status": "ok",
            "backend": self.backend,
            "target": str(self.path),
            "report_count": report_count,
            "snapshot_count": report_count,
            "feedback_count": feedback_count,
            "command_count": command_count,
            "error": self.error,
        }
