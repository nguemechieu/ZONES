from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _coerce_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _from_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def _normalize_sqlite_url(database_url: str) -> Path:
    raw = (database_url or "").strip()
    if not raw:
        raw = "sqlite:///data/zones.db"

    if raw.startswith("sqlite:///"):
        relative = raw[len("sqlite:///") :]
        return Path(relative)
    if raw.startswith("sqlite://"):
        relative = raw[len("sqlite://") :]
        return Path(relative)

    # allow plain filesystem paths too
    return Path(raw)


@dataclass(slots=True)
class RepositoryHealth:
    status: str
    backend: str
    target: str
    report_count: int
    feedback_count: int
    snapshot_count: int
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "backend": self.backend,
            "target": self.target,
            "report_count": self.report_count,
            "feedback_count": self.feedback_count,
            "snapshot_count": self.snapshot_count,
            "error": self.error,
        }


class LearningRepository:
    """
    SQLite-backed repository for:
    - live report snapshots
    - feedback rows
    - lightweight model registry
    - optional command/result audit storage
    """

    def __init__(self, database_url: str = "sqlite:///data/zones.db") -> None:
        self.database_url = database_url
        self.db_path = _normalize_sqlite_url(database_url)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._initialize()

    # ============================================================
    # CONNECTION
    # ============================================================

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS reports (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        account_id TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        execution_allowed INTEGER NOT NULL DEFAULT 0,
                        execution_direction TEXT NOT NULL DEFAULT '',
                        execution_score REAL NOT NULL DEFAULT 0.0
                    );

                    CREATE INDEX IF NOT EXISTS idx_reports_created_at
                        ON reports(created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_reports_account_symbol
                        ON reports(account_id, symbol, created_at DESC);

                    CREATE TABLE IF NOT EXISTS feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timeframe TEXT NOT NULL,
                        setup_direction TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        pnl REAL NOT NULL DEFAULT 0.0,
                        notes TEXT NOT NULL DEFAULT ''
                    );

                    CREATE INDEX IF NOT EXISTS idx_feedback_created_at
                        ON feedback(created_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_feedback_symbol_timeframe
                        ON feedback(symbol, timeframe, created_at DESC);

                    CREATE TABLE IF NOT EXISTS models (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        training_mode TEXT NOT NULL DEFAULT '',
                        summary TEXT NOT NULL DEFAULT '',
                        model_json TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_models_name_created
                        ON models(model_name, created_at DESC);

                    CREATE TABLE IF NOT EXISTS command_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        command_id TEXT NOT NULL,
                        recorded_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        message TEXT NOT NULL,
                        extras_json TEXT NOT NULL DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS idx_command_results_command_id
                        ON command_results(command_id, recorded_at DESC);
                    """
                )

    # ============================================================
    # REPORTS
    # ============================================================

    def save_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        account = payload.get("account", {}) or {}
        execution = payload.get("execution_decision", {}) or {}

        created_at = str(payload.get("created_at") or _utc_now_iso())
        account_id = str(account.get("account_id", ""))
        symbol = str(payload.get("symbol", ""))
        allowed = 1 if bool(execution.get("allowed", False)) else 0
        direction = str(execution.get("direction", ""))
        score = float(execution.get("score", 0.0) or 0.0)

        row = {
            "created_at": created_at,
            "account_id": account_id,
            "symbol": symbol,
            "payload_json": _coerce_json(payload),
            "execution_allowed": allowed,
            "execution_direction": direction,
            "execution_score": score,
        }

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reports (
                        created_at,
                        account_id,
                        symbol,
                        payload_json,
                        execution_allowed,
                        execution_direction,
                        execution_score
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["created_at"],
                        row["account_id"],
                        row["symbol"],
                        row["payload_json"],
                        row["execution_allowed"],
                        row["execution_direction"],
                        row["execution_score"],
                    ),
                )

        return row

    def recent_reports(self, limit: int = 5) -> list[dict[str, Any]]:
        limit = max(1, int(limit))

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT payload_json
                    FROM reports
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [_from_json(row["payload_json"], {}) for row in rows]

    def latest_report(self, account_id: str | None = None, symbol: str | None = None) -> dict[str, Any] | None:
        clauses: list[str] = []
        params: list[Any] = []

        if account_id:
            clauses.append("account_id = ?")
            params.append(account_id)
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol)

        where_sql = ""
        if clauses:
            where_sql = "WHERE " + " AND ".join(clauses)

        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    f"""
                    SELECT payload_json
                    FROM reports
                    {where_sql}
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()

        if not row:
            return None
        return _from_json(row["payload_json"], {})

    def report_rows_for_training(self, limit: int = 1000) -> list[dict[str, Any]]:
        """
        Flattened-ish training rows:
        keeps payload plus a few top-level labels to make model prep easier.
        """
        limit = max(1, int(limit))

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        created_at,
                        account_id,
                        symbol,
                        execution_allowed,
                        execution_direction,
                        execution_score,
                        payload_json
                    FROM reports
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            payload = _from_json(row["payload_json"], {})
            results.append(
                {
                    "created_at": row["created_at"],
                    "account_id": row["account_id"],
                    "symbol": row["symbol"],
                    "execution_allowed": bool(row["execution_allowed"]),
                    "execution_direction": row["execution_direction"],
                    "execution_score": float(row["execution_score"]),
                    "payload": payload,
                }
            )
        return results

    # ============================================================
    # FEEDBACK
    # ============================================================

    def record_feedback(
        self,
        *,
        created_at: str,
        symbol: str,
        timeframe: str,
        setup_direction: str,
        outcome: str,
        pnl: float,
        notes: str = "",
    ) -> dict[str, Any]:
        row = {
            "created_at": created_at or _utc_now_iso(),
            "symbol": str(symbol or "").upper(),
            "timeframe": str(timeframe or "5M").upper(),
            "setup_direction": str(setup_direction or "long").lower(),
            "outcome": str(outcome or "win").lower(),
            "pnl": float(pnl or 0.0),
            "notes": str(notes or ""),
        }

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO feedback (
                        created_at,
                        symbol,
                        timeframe,
                        setup_direction,
                        outcome,
                        pnl,
                        notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["created_at"],
                        row["symbol"],
                        row["timeframe"],
                        row["setup_direction"],
                        row["outcome"],
                        row["pnl"],
                        row["notes"],
                    ),
                )

        return row

    def recent_feedback(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, int(limit))

        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT created_at, symbol, timeframe, setup_direction, outcome, pnl, notes
                    FROM feedback
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        return [dict(row) for row in rows]

    def feedback_rows_for_training(self, limit: int = 1000) -> list[dict[str, Any]]:
        return self.recent_feedback(limit=limit)

    # ============================================================
    # MODEL STORAGE
    # ============================================================

    def save_model(
        self,
        *,
        model_name: str,
        model_payload: dict[str, Any],
        training_mode: str = "database-first",
        summary: str = "",
    ) -> dict[str, Any]:
        row = {
            "model_name": model_name,
            "created_at": _utc_now_iso(),
            "training_mode": training_mode,
            "summary": summary,
            "model_json": _coerce_json(model_payload),
        }

        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO models (
                        model_name,
                        created_at,
                        training_mode,
                        summary,
                        model_json
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["model_name"],
                        row["created_at"],
                        row["training_mode"],
                        row["summary"],
                        row["model_json"],
                    ),
                )

        return {
            "status": "ready",
            "model_name": model_name,
            "trained_at": row["created_at"],
            "training_mode": training_mode,
            "summary": summary,
            "sample_count": len(self.feedback_rows_for_training(limit=5000)),
        }

    def load_model(self, model_name: str = "signal_model") -> dict[str, Any] | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT model_name, created_at, training_mode, summary, model_json
                    FROM models
                    WHERE model_name = ?
                    ORDER BY datetime(created_at) DESC, id DESC
                    LIMIT 1
                    """,
                    (model_name,),
                ).fetchone()

        if not row:
            return None

        model_payload = _from_json(row["model_json"], {})
        return {
            "status": "ready",
            "model_name": row["model_name"],
            "trained_at": row["created_at"],
            "training_mode": row["training_mode"],
            "summary": row["summary"],
            "sample_count": len(self.feedback_rows_for_training(limit=5000)),
            "model": model_payload,
        }

    # ============================================================
    # COMMAND RESULT STORAGE
    # ============================================================

    # ============================================================
# COMMAND RESULT STORAGE
# ============================================================

    def record_command_result(
        self,
        *,
        command_id: str,
        status: str,
        message: str,
        extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
     row = {
        "command_id": str(command_id or ""),
        "recorded_at": _utc_now_iso(),
        "status": str(status or ""),
        "message": str(message or ""),
        "extras_json": _coerce_json(extras or {}),
    }

     with self._lock:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO command_results (
                    command_id,
                    recorded_at,
                    status,
                    message,
                    extras_json
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["command_id"],
                    row["recorded_at"],
                    row["status"],
                    row["message"],
                    row["extras_json"],
                ),
            )

     return {
        "command_id": row["command_id"],
        "recorded_at": row["recorded_at"],
        "status": row["status"],
        "message": row["message"],
        "extras": extras or {},
    }

    def command_rows(
        self,
        *,
        command_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
) -> list[dict[str, Any]]:
      limit = max(1, int(limit))

      clauses: list[str] = []
      params: list[Any] = []

      if command_id:
        clauses.append("command_id = ?")
        params.append(str(command_id))

      if status:
        clauses.append("status = ?")
        params.append(str(status))

      where_sql = ""
      if clauses:
        where_sql = "WHERE " + " AND ".join(clauses)

      with self._lock:
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT command_id, recorded_at, status, message, extras_json
                FROM command_results
                {where_sql}
                ORDER BY datetime(recorded_at) DESC, id DESC
                LIMIT ?
                """,
                (*params, limit),
            ).fetchall()

      return [
        {
            "command_id": row["command_id"],
            "recorded_at": row["recorded_at"],
            "status": row["status"],
            "message": row["message"],
            "extras": _from_json(row["extras_json"], {}),
        }
        for row in rows
    ]

    def recent_command_results(self, limit: int = 5000) -> list[dict[str, Any]]:
     return self.command_rows(limit=limit)

    def connection_health(self) -> dict[str, Any]:
        try:
            with self._lock:
                with self._connect() as conn:
                    report_count = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
                    feedback_count = conn.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
                    snapshot_count = report_count

            return {
                "status": "ok",
                "backend": "sqlite",
                "target": str(self.db_path),
                "report_count": int(report_count),
                "feedback_count": int(feedback_count),
                "snapshot_count": int(snapshot_count),
                "error": "",
            }
        except Exception as exc:
            return {
                "status": "error",
                "backend": "sqlite",
                "target": str(self.db_path),
                "report_count": 0,
                "feedback_count": 0,
                "snapshot_count": 0,
                "error": str(exc),
            }