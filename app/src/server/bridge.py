from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from src.db.repository.learning_repository import LearningRepository
from src.execution.system_state import SignalModelService
from src.server.engine_config import EngineConfig


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_timeframe(value: str) -> str:
    normalized = str(value or "").strip().upper()
    aliases = {
        "M1": "1M",
        "M5": "5M",
        "M15": "15M",
        "H1": "1H",
        "H4": "4H",
        "D1": "1D",
        "W1": "1W",
        "MN": "1MN",
        "MN1": "1MN",
    }
    return aliases.get(normalized, normalized or "5M")


class LiveFeedService:
    def __init__(
        self,
        config: EngineConfig,
        repository: LearningRepository,
        signal_service: SignalModelService | None = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.signal_service = signal_service or SignalModelService()
        self._latest: dict[tuple[str, str], dict[str, Any]] = {}
        self._commands: list[dict[str, Any]] = []
        self._command_counter = 0

    # ============================================================
    # Reports / latest state
    # ============================================================

    def latest_report(
            self,
            account_id: str | None = None,
            symbol: str | None = None,
    ) -> dict[str, Any] | None:
        account = account_id or self.config.account_id
        target_symbol = (symbol or self.config.symbol).upper()
        payload = self._latest.get((account, target_symbol))
        if payload:
            return dict(payload)
        return self.repository.latest_report(account_id=account, symbol=target_symbol)

    def tracked_symbols(self, account_id: str | None = None) -> list[dict[str, Any]]:
        """
        Since the current repository doesn't expose tracked_symbols(),
        build tracked symbols from in-memory latest snapshots + recent reports.
        """
        memory = [
            {
                "account_id": account,
                "symbol": symbol,
                "last_seen": payload.get("created_at", ""),
            }
            for (account, symbol), payload in self._latest.items()
            if not account_id or account == account_id
        ]

        stored_reports = self.repository.recent_reports(limit=250)
        stored: list[dict[str, Any]] = []
        for report in stored_reports:
            if not isinstance(report, dict):
                continue
            report_account = str(report.get("account", {}).get("account_id", ""))
            report_symbol = str(report.get("symbol", "")).upper()
            if account_id and report_account != account_id:
                continue
            if not report_symbol:
                continue
            stored.append(
                {
                    "account_id": report_account,
                    "symbol": report_symbol,
                    "last_seen": str(report.get("created_at", "")),
                }
            )

        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for item in [*stored, *memory]:
            key = (str(item.get("account_id", "")), str(item.get("symbol", "")).upper())
            by_key[key] = item

        if not by_key:
            by_key[(self.config.account_id, self.config.symbol.upper())] = {
                "account_id": self.config.account_id,
                "symbol": self.config.symbol.upper(),
                "last_seen": "",
            }

        return sorted(
            by_key.values(),
            key=lambda item: str(item.get("last_seen", "")),
            reverse=True,
        )

    def ingest_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Ingest payload must be a JSON object.")

        report = self._normalize_payload(payload)
        report["ai_signal"] = self.signal_service.score_report(
            report,
            self._config_dict(),
        )
        report["ai_response"] = self._build_ai_response(report)
        account_id = str(report["account"]["account_id"])
        symbol = str(report["symbol"]).upper()

        self._latest[(account_id, symbol)] = report
        self.repository.save_report(report)

        return {
            "status": "ok",
            "account_id": account_id,
            "symbol": symbol,
            "report": report,
            "ai_response": dict(report["ai_response"]),
        }

    def waiting_payload(
            self,
            account_id: str | None = None,
            symbol: str | None = None,
    ) -> dict[str, Any]:
        target_account = account_id or self.config.account_id
        target_symbol = (symbol or self.config.symbol).upper()
        base_price = 1.085 if target_symbol.endswith("USD") else 100.0
        candles = self._demo_candles(base_price)

        return {
            "created_at": _utc_now(),
            "symbol": target_symbol,
            "account": self._account_payload({"account_id": target_account}),
            "positions": [],
            "metadata": {
                "ingest": {
                    "source": "waiting",
                    "message": "Waiting for MT4 live feed data.",
                },
                "custom_inputs": self.config.to_dict() if hasattr(self.config, "to_dict") else self.config.__dict__,
            },
            "ai_summary": "Waiting for live MT4 data. The dashboard is online and ready to ingest snapshots.",
            "price_action": [
                {"timeframe": "1H", "bias": "neutral", "phase": "waiting", "momentum_score": 0.0},
                {"timeframe": "5M", "bias": "neutral", "phase": "waiting", "momentum_score": 0.0},
                {"timeframe": "1M", "bias": "neutral", "phase": "waiting", "momentum_score": 0.0},
            ],
            "trade_ideas": [],
            "zones": [
                {
                    "timeframe": "5M",
                    "kind": "demand",
                    "family": "temp",
                    "strength": 1,
                    "strength_label": "S1",
                    "lower": round(base_price - 0.002, 5),
                    "upper": round(base_price - 0.001, 5),
                    "status": "waiting",
                    "mode_bias": "neutral",
                    "origin_index": 10,
                }
            ],
            "liquidity_map": [],
            "news_filter": {
                "trading_blocked": False,
                "reason": "No live news filter data yet.",
                "upcoming_events": [],
            },
            "execution_decision": {
                "allowed": False,
                "direction": "neutral",
                "timeframe": "5M",
                "score": 0.0,
                "rationale": "Waiting for MT4 ingest.",
                "passed_checks": [],
                "blocked_reasons": ["No live market snapshot received"],
                "entry": "",
                "stop_loss": "",
                "take_profit": "",
            },
            "execution_context": {
                "supported_styles": ["instant", "advanced"],
                "configured_style": "advanced",
                "confirmation_timeframe": "1M",
                "rrr_state": "none",
                "bos_direction": "none",
                "local_prediction": "HOLD",
                "local_allowed": False,
                "reason": "Waiting for MT4 ingest.",
            },
            "market_structure": {
                "checkpoint_timeframe": "1H",
                "refinement_timeframe": "5M",
                "bias": "neutral",
                "labels": ["WAITING"],
                "swings": [],
                "events": [],
            },
            "chart_data": {
                "1H": candles[::5],
                "5M": candles,
                "1M": candles[-45:],
            },
            "indicator_values": {},
            "bridge": {"transport": "waiting"},
            "phase_outputs": self._phase_outputs({"swings": [], "events": []}),
        }

    def sample_ingest_schema(self) -> dict[str, Any]:
        return {
            "account": {
                "account_id": "123456",
                "balance": 10000,
                "equity": 10040,
                "free_margin": 9500,
                "margin": 500,
                "currency": "USD",
            },
            "symbol": "EURUSD",
            "timeframe": "5M",
            "candles": [
                {
                    "timestamp": "2026-04-22T12:00:00Z",
                    "open": 1.0801,
                    "high": 1.0810,
                    "low": 1.0792,
                    "close": 1.0806,
                }
            ],
            "positions": [],
            "chart_data": {
                "1H": [],
                "5M": [],
                "1M": [],
            },
            "market_structure": {
                "checkpoint_timeframe": "1H",
                "refinement_timeframe": "5M",
                "bias": "bullish",
                "labels": ["HH", "HL", "BOS"],
                "swings": [],
                "events": [],
            },
            "zones": [
                {
                    "id": "demand_1",
                    "timeframe": "5M",
                    "anchor_timeframe": "1H",
                    "kind": "demand",
                    "family": "main",
                    "strength": 2,
                    "strength_label": "S2",
                    "lower": 1.0795,
                    "upper": 1.0804,
                    "zigzag_count": 2,
                    "fractal_count": 1,
                    "touch_count": 3,
                    "retest_count": 1,
                    "status": "respected",
                    "mode_bias": "buying",
                }
            ],
            "execution_context": {
                "supported_styles": ["instant", "advanced"],
                "configured_style": "advanced",
                "confirmation_timeframe": "1M",
                "rrr_state": "reject",
                "bos_direction": "bullish",
                "local_prediction": "BUY",
                "local_allowed": True,
            },
            "execution_decision": {
                "allowed": True,
                "direction": "long",
                "timeframe": "1M",
                "score": 3.4,
                "rationale": "Main demand zone respected after BOS.",
            },
            "indicator_values": {"atr_h1": 0.0012, "atr_m5": 0.0004, "spread_points": 12},
            "bridge": {"transport": "websocket", "bridge_enabled": True},
            "news": {"trading_blocked": False, "reason": "clear"},
        }

    # ============================================================
    # Commands
    # ============================================================

    def enqueue_command(
            self,
            *,
            account_id: str,
            symbol: str,
            command_type: str,
            params: dict[str, Any],
    ) -> dict[str, Any]:
        command_type = str(command_type or "").strip()
        if not command_type:
            raise ValueError("Command type is required.")

        self._command_counter += 1
        command = {
            "id": f"cmd-{self._command_counter}",
            "created_at": _utc_now(),
            "account_id": account_id or self.config.account_id,
            "symbol": (symbol or self.config.symbol).upper(),
            "type": command_type,
            "status": "pending",
            "params": dict(params or {}),
            "message": "",
            "recorded_at": "",
        }
        self._commands.insert(0, command)
        return command

    def fetch_next_command(self, account_id: str, symbol: str) -> str:
        """
        Returns the next pending command in pipe-wire format expected by the MT4 bridge.
        """
        target_account = account_id or self.config.account_id
        target_symbol = (symbol or self.config.symbol).upper()

        for command in self._commands:
            if command.get("status") != "pending":
                continue
            if str(command.get("account_id", "")) != str(target_account):
                continue
            if str(command.get("symbol", "")).upper() != target_symbol:
                continue

            params = dict(command.get("params", {}))
            parts = [
                f"id={command['id']}",
                f"type={command['type']}",
                f"symbol={command['symbol']}",
            ]
            for key, value in params.items():
                parts.append(f"{key}={value}")
            return "|".join(parts)

        return ""

    def record_command_result(
            self,
            *,
            command_id: str,
            status: str,
            message: str,
            extras: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        extras = dict(extras or {})
        saved = self.repository.record_command_result(
            command_id=command_id,
            status=status,
            message=message,
            extras=extras,
        )

        for command in self._commands:
            if command.get("id") == command_id:
                command["status"] = status
                command["message"] = message
                command["recorded_at"] = saved["recorded_at"]
                break

        return saved

    def command_snapshot(
            self,
            account_id: str | None = None,
            symbol: str | None = None,
    ) -> dict[str, Any]:
        target_account = account_id or ""
        target_symbol = (symbol or "").upper()

        pending = [
            item
            for item in self._commands
            if (not target_account or str(item.get("account_id", "")) == target_account)
               and (not target_symbol or str(item.get("symbol", "")).upper() == target_symbol)
               and item.get("status") == "pending"
        ]

        history_rows = self.repository.recent_command_results(limit=200)
        history: list[dict[str, Any]] = []

        for row in history_rows:
            extras = dict(row.get("extras", {}) or {})
            row_account = str(extras.get("account_id", ""))
            row_symbol = str(extras.get("symbol", "")).upper()

            if target_account and row_account and row_account != target_account:
                continue
            if target_symbol and row_symbol and row_symbol != target_symbol:
                continue

            history.append(
                {
                    "id": row.get("command_id", ""),
                    "command_id": row.get("command_id", ""),
                    "status": row.get("status", ""),
                    "message": row.get("message", ""),
                    "recorded_at": row.get("recorded_at", ""),
                    "account_id": row_account,
                    "symbol": row_symbol,
                    "type": extras.get("command_type", ""),
                    "params": extras.get("params", {}),
                }
            )

        return {
            "pending": pending[:50],
            "history": history[:50],
        }

    def chart_snapshot_wire(
            self,
            account_id: str,
            symbol: str,
            timeframe: str,
    ) -> str:
        payload = self.latest_report(account_id, symbol)
        if payload is None:
            payload = self.waiting_payload(account_id, symbol)

        resolved_timeframe = _normalize_timeframe(timeframe or "5M")
        execution = dict(payload.get("execution_decision", {}) or {})
        zones = list(payload.get("zones", []) or [])
        liquidity_map = list(payload.get("liquidity_map", []) or [])
        structure = dict(payload.get("market_structure", {}) or {})
        phase_outputs = dict(payload.get("phase_outputs", {}) or {})

        swings = list(phase_outputs.get("swings", []) or structure.get("swings", []) or [])
        events = list(phase_outputs.get("events", []) or structure.get("events", []) or [])

        filtered_zones = [
            zone for zone in [*zones, *liquidity_map]
            if str(zone.get("timeframe", resolved_timeframe)) == resolved_timeframe
        ]
        if not filtered_zones:
            filtered_zones = zones[:6] + liquidity_map[:2]

        lines: list[str] = []
        header = [
            "header",
            "status=ok",
            f"resolved_timeframe={resolved_timeframe}",
            f"execution_allowed={'true' if execution.get('allowed') else 'false'}",
            f"execution_direction={execution.get('direction', 'neutral')}",
            f"zone_count={len(filtered_zones)}",
            f"swing_count={len(swings)}",
            "message=chart snapshot ready",
        ]
        lines.append("|".join(header))

        for zone in filtered_zones:
            lines.append(
                "|".join(
                    [
                        "zone",
                        f"timeframe={zone.get('timeframe', resolved_timeframe)}",
                        f"kind={zone.get('kind', '')}",
                        f"family={zone.get('family', '')}",
                        f"strength={zone.get('strength_label', zone.get('strength', ''))}",
                        f"status={zone.get('status', 'fresh')}",
                        f"mode={zone.get('mode_bias', 'neutral')}",
                        f"origin_shift={zone.get('origin_index', 0)}",
                        f"lower={zone.get('lower', '')}",
                        f"upper={zone.get('upper', '')}",
                    ]
                )
            )

        for swing in swings:
            lines.append(
                "|".join(
                    [
                        "swing",
                        f"origin_shift={swing.get('origin_shift', swing.get('shift', 0))}",
                        f"kind={swing.get('kind', 'high' if swing.get('is_high') else 'low')}",
                        f"source={swing.get('source', 'zigzag')}",
                        f"label={swing.get('label', '')}",
                        f"price={swing.get('price', '')}",
                    ]
                )
            )

        for event in events:
            lines.append(
                "|".join(
                    [
                        "event",
                        f"event={event.get('event', '')}",
                        f"structure_label={event.get('structure_label', '')}",
                        f"direction={event.get('direction', '')}",
                        f"level={event.get('level', '')}",
                    ]
                )
            )

        return "\n".join(lines)

    # ============================================================
    # Normalization
    # ============================================================

    def _config_dict(self) -> dict[str, Any]:
        return self.config.to_dict() if hasattr(self.config, "to_dict") else dict(self.config.__dict__)

    def _normalize_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        symbol = str(raw.get("symbol") or raw.get("instrument") or self.config.symbol).upper()
        timeframe = _normalize_timeframe(
            str(raw.get("timeframe") or raw.get("time_frame") or "5M")
        )

        raw_chart_data = (
            raw.get("chart_data")
            or raw.get("timeframes")
            or raw.get("candles")
            or raw.get("rates")
            or []
        )
        candles = self._normalize_candles(raw_chart_data)
        if not candles:
            candles = self._demo_candles(1.085)

        chart_data = self._chart_data(raw_chart_data, candles, timeframe)
        zones = self._normalize_zones(
            raw.get("zones") or raw.get("supply_demand_zones") or [],
            timeframe,
            candles,
        )
        ideas = raw.get("trade_ideas") or self._build_trade_ideas(zones, candles, timeframe)
        decision = dict(raw.get("execution_decision") or self._execution_decision(ideas))
        structure = self._market_structure(raw.get("market_structure"), raw.get("phase_outputs"))
        execution_context = self._execution_context(raw.get("execution_context"), decision)

        positions = raw.get("positions")
        if not isinstance(positions, list):
            positions = []

        payload = {
            "created_at": str(raw.get("created_at") or raw.get("time") or _utc_now()),
            "symbol": symbol,
            "account": self._account_payload(raw.get("account") or raw),
            "positions": positions,
            "metadata": {
                "ingest": {
                    "source": str(raw.get("source") or "live"),
                    "message": "Live payload accepted.",
                },
                "custom_inputs": dict(
                    raw.get("custom_inputs")
                    or self._config_dict()
                ),
                "bridge": dict(raw.get("bridge") or {}),
            },
            "ai_summary": str(
                raw.get("ai_summary")
                or "Live MT4 report normalized. Python scoring remains advisory while MT4 owns zone and execution logic."
            ),
            "price_action": raw.get("price_action") or self._price_action(candles, timeframe),
            "trade_ideas": raw.get("trade_ideas") or ideas,
            "zones": zones,
            "liquidity_map": raw.get("liquidity_map") or [],
            "news_filter": self._news_filter(raw.get("news") or raw.get("news_filter") or {}),
            "execution_decision": decision,
            "execution_context": execution_context,
            "market_structure": structure,
            "chart_data": chart_data,
            "indicator_values": dict(raw.get("indicator_values") or {}),
            "bridge": dict(raw.get("bridge") or {}),
            "phase_outputs": raw.get("phase_outputs") or self._phase_outputs(structure),
        }
        return payload

    def _account_payload(self, source: dict[str, Any]) -> dict[str, Any]:
        balance = _number(source.get("balance"), 10000.0)
        equity = _number(source.get("equity"), balance)
        margin = _number(source.get("margin"), 0.0)
        free_margin = _number(source.get("free_margin"), equity - margin)

        return {
            "account_id": str(source.get("account_id") or source.get("login") or self.config.account_id),
            "status": str(source.get("status") or "connected"),
            "balance": balance,
            "equity": equity,
            "free_margin": free_margin,
            "margin": margin,
            "daily_pnl": _number(source.get("daily_pnl"), equity - balance),
            "open_positions": int(_number(source.get("open_positions"), 0)),
            "risk_exposure_pct": _number(source.get("risk_exposure_pct"), 0.0),
            "name": str(source.get("name") or ""),
            "server": str(source.get("server") or ""),
            "company": str(source.get("company") or ""),
            "currency": str(source.get("currency") or "USD"),
            "leverage": str(source.get("leverage") or ""),
        }

    def _normalize_candles(self, candles: Any) -> list[dict[str, Any]]:
        if isinstance(candles, dict):
            candles = candles.get("5M") or candles.get("1H") or next(iter(candles.values()), [])

        normalized: list[dict[str, Any]] = []
        for index, candle in enumerate(candles if isinstance(candles, list) else []):
            if not isinstance(candle, dict):
                continue

            close_value = _number(candle.get("close"), _number(candle.get("bid"), 1.0))
            open_value = _number(candle.get("open"), close_value)
            high_value = _number(candle.get("high"), max(open_value, close_value))
            low_value = _number(candle.get("low"), min(open_value, close_value))

            normalized.append(
                {
                    "timestamp": str(
                        candle.get("timestamp")
                        or candle.get("time")
                        or (_utc_now() if index == 0 else "")
                    ),
                    "open": open_value,
                    "high": high_value,
                    "low": low_value,
                    "close": close_value,
                    "volume": _number(candle.get("volume"), 0.0),
                }
            )

        return normalized

    def _demo_candles(self, base_price: float) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        candles: list[dict[str, Any]] = []

        for index in range(72):
            angle = index / 7.0
            open_value = base_price + math.sin(angle) * 0.002 + index * 0.00001
            close_value = open_value + math.sin(angle * 1.7) * 0.0006
            high_value = max(open_value, close_value) + 0.00045
            low_value = min(open_value, close_value) - 0.00045

            candles.append(
                {
                    "timestamp": (
                            now - timedelta(minutes=(71 - index) * 5)
                    ).isoformat(timespec="seconds"),
                    "open": round(open_value, 5),
                    "high": round(high_value, 5),
                    "low": round(low_value, 5),
                    "close": round(close_value, 5),
                    "volume": 100 + index,
                }
            )

        return candles

    def _chart_data(
            self,
            raw_chart_data: Any,
            candles: list[dict[str, Any]],
            timeframe: str,
    ) -> dict[str, list[dict[str, Any]]]:
        if isinstance(raw_chart_data, dict):
            normalized: dict[str, list[dict[str, Any]]] = {}
            for key, value in raw_chart_data.items():
                norm_key = _normalize_timeframe(str(key))
                norm_value = self._normalize_candles(value)
                if norm_value:
                    normalized[norm_key] = norm_value
            if normalized:
                return normalized

        return {
            timeframe: candles,
            "5M": candles,
            "1M": candles[-45:],
            "1H": candles[::5] or candles,
        }

    def _normalize_zones(
            self,
            zones: Any,
            timeframe: str,
            candles: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for index, zone in enumerate(zones if isinstance(zones, list) else []):
            if not isinstance(zone, dict):
                continue

            lower = _number(zone.get("lower") or zone.get("low"), 0.0)
            upper = _number(zone.get("upper") or zone.get("high"), lower)

            normalized.append(
                {
                    "id": str(zone.get("id") or f"zone-{index}"),
                    "timeframe": _normalize_timeframe(str(zone.get("timeframe") or timeframe)),
                    "anchor_timeframe": str(zone.get("anchor_timeframe") or zone.get("structure_timeframe") or "1H"),
                    "kind": str(zone.get("kind") or zone.get("type") or "demand").lower(),
                    "family": str(zone.get("family") or "main").lower(),
                    "strength": int(_number(zone.get("strength"), 1)),
                    "strength_label": str(zone.get("strength_label") or f"S{int(_number(zone.get('strength'), 1))}"),
                    "lower": min(lower, upper),
                    "upper": max(lower, upper),
                    "body_start": _number(zone.get("body_start"), max(lower, upper)),
                    "status": str(zone.get("status") or "fresh"),
                    "mode_bias": str(zone.get("mode_bias") or "neutral"),
                    "origin_index": int(_number(zone.get("origin_index"), index)),
                    "origin_time": str(zone.get("origin_time") or zone.get("timestamp") or ""),
                    "origin_price": _number(zone.get("origin_price"), _number(zone.get("body_start"), max(lower, upper))),
                    "zigzag_count": int(_number(zone.get("zigzag_count"), 0)),
                    "fractal_count": int(_number(zone.get("fractal_count"), 0)),
                    "touch_count": int(_number(zone.get("touch_count"), 0)),
                    "retest_count": int(_number(zone.get("retest_count"), 0)),
                    "price_relation": str(zone.get("price_relation") or "unknown"),
                    "structure_label": str(zone.get("structure_label") or ""),
                }
            )

        if normalized:
            return normalized

        last_close = _number(candles[-1]["close"], 1.0)
        return [
            {
                "timeframe": timeframe,
                "kind": "demand",
                "family": "main",
                "strength": 2,
                "strength_label": "S2",
                "lower": round(last_close - 0.002, 5),
                "upper": round(last_close - 0.001, 5),
                "body_start": round(last_close - 0.001, 5),
                "status": "fresh",
                "mode_bias": "bullish",
                "origin_index": max(0, len(candles) - 30),
                "origin_time": candles[max(0, len(candles) - 30)].get("timestamp", ""),
                "origin_price": round(last_close - 0.001, 5),
                "zigzag_count": 2,
                "fractal_count": 1,
                "touch_count": 3,
                "retest_count": 1,
                "price_relation": "above",
                "structure_label": "bullish",
            },
            {
                "id": "fallback-supply",
                "timeframe": timeframe,
                "anchor_timeframe": "1H",
                "kind": "supply",
                "family": "main",
                "strength": 2,
                "strength_label": "S2",
                "lower": round(last_close + 0.001, 5),
                "upper": round(last_close + 0.002, 5),
                "body_start": round(last_close + 0.001, 5),
                "status": "fresh",
                "mode_bias": "bearish",
                "origin_index": max(0, len(candles) - 25),
                "origin_time": candles[max(0, len(candles) - 25)].get("timestamp", ""),
                "origin_price": round(last_close + 0.001, 5),
                "zigzag_count": 2,
                "fractal_count": 1,
                "touch_count": 3,
                "retest_count": 1,
                "price_relation": "below",
                "structure_label": "bearish",
            },
        ]

    def _market_structure(
            self,
            raw_structure: Any,
            raw_phase_outputs: Any,
    ) -> dict[str, Any]:
        phase_outputs = dict(raw_phase_outputs or {}) if isinstance(raw_phase_outputs, dict) else {}
        structure = dict(raw_structure or {}) if isinstance(raw_structure, dict) else {}
        return {
            "checkpoint_timeframe": str(structure.get("checkpoint_timeframe") or "1H"),
            "refinement_timeframe": str(structure.get("refinement_timeframe") or "5M"),
            "bias": str(structure.get("bias") or "neutral"),
            "labels": list(structure.get("labels") or []),
            "swings": list(structure.get("swings") or phase_outputs.get("swings") or []),
            "events": list(structure.get("events") or phase_outputs.get("events") or []),
        }

    def _execution_context(
            self,
            raw_context: Any,
            execution_decision: dict[str, Any],
    ) -> dict[str, Any]:
        context = dict(raw_context or {}) if isinstance(raw_context, dict) else {}
        return {
            "supported_styles": list(context.get("supported_styles") or ["instant", "advanced"]),
            "configured_style": str(context.get("configured_style") or execution_decision.get("style") or "advanced"),
            "confirmation_timeframe": str(context.get("confirmation_timeframe") or execution_decision.get("timeframe") or "1M"),
            "retest_limit": int(_number(context.get("retest_limit"), 0)),
            "retest_entry_mode": str(context.get("retest_entry_mode") or "close"),
            "rrr_state": str(context.get("rrr_state") or execution_decision.get("rrr_state") or "none"),
            "bos_direction": str(context.get("bos_direction") or execution_decision.get("bos_direction") or "none"),
            "local_prediction": str(context.get("local_prediction") or "HOLD"),
            "local_allowed": bool(context.get("local_allowed", execution_decision.get("allowed", False))),
            "reason": str(context.get("reason") or execution_decision.get("rationale") or ""),
            "active_zone_id": str(context.get("active_zone_id") or execution_decision.get("active_zone_id") or ""),
            "active_zone_kind": str(context.get("active_zone_kind") or execution_decision.get("active_zone_kind") or ""),
            "zone_state": str(context.get("zone_state") or "pending"),
            "retest_count": int(_number(context.get("retest_count"), 0)),
            "entry": _number(context.get("entry"), _number(execution_decision.get("entry"), 0.0)),
            "stop_loss": _number(context.get("stop_loss"), _number(execution_decision.get("stop_loss"), 0.0)),
            "take_profit": _number(context.get("take_profit"), _number(execution_decision.get("take_profit"), 0.0)),
        }

    def _price_action(self, candles: list[dict[str, Any]], timeframe: str) -> list[dict[str, Any]]:
        first = _number(candles[0]["close"], 0.0)
        last = _number(candles[-1]["close"], first)
        diff = last - first
        bias = "bullish" if diff > 0 else "bearish" if diff < 0 else "neutral"
        score = round(abs(diff) * 10000, 2)

        return [
            {"timeframe": "1H", "bias": bias, "phase": "structure", "momentum_score": score},
            {"timeframe": timeframe, "bias": bias, "phase": "execution", "momentum_score": score},
            {"timeframe": "1M", "bias": bias, "phase": "trigger", "momentum_score": score},
        ]

    def _build_trade_ideas(
            self,
            zones: list[dict[str, Any]],
            candles: list[dict[str, Any]],
            timeframe: str,
    ) -> list[dict[str, Any]]:
        if not candles:
            return []

        last_close = _number(candles[-1]["close"], 1.0)
        ideas: list[dict[str, Any]] = []

        for zone in zones[:4]:
            direction = "long" if zone["kind"] in {"demand", "support"} else "short"
            entry = last_close
            risk = max(
                abs(entry - _number(zone["lower" if direction == "long" else "upper"], entry)),
                0.001,
            )

            ideas.append(
                {
                    "timeframe": zone.get("timeframe", timeframe),
                    "direction": direction,
                    "zone_label": f"{zone.get('family', 'main')} {zone.get('kind', 'zone')}",
                    "execution_style": "confirmation",
                    "entry": round(entry, 5),
                    "stop_loss": round(entry - risk if direction == "long" else entry + risk, 5),
                    "take_profit": round(entry + risk * 2 if direction == "long" else entry - risk * 2, 5),
                    "score": float(zone.get("strength", 1)),
                }
            )

        return ideas

    def _execution_decision(self, ideas: list[dict[str, Any]]) -> dict[str, Any]:
        if not ideas:
            return {
                "allowed": False,
                "direction": "neutral",
                "timeframe": "5M",
                "score": 0.0,
                "rationale": "No eligible trade ideas.",
                "passed_checks": [],
                "blocked_reasons": ["No eligible trade ideas"],
                "entry": "",
                "stop_loss": "",
                "take_profit": "",
            }

        idea = ideas[0]
        score = _number(idea.get("score"), 0.0)
        threshold = _number(getattr(self.config, "minimum_trade_score", 2.0), 2.0)
        allowed = score >= threshold

        return {
            "allowed": allowed,
            "direction": idea.get("direction", "neutral"),
            "timeframe": idea.get("timeframe", "5M"),
            "score": score,
            "rationale": (
                "Trade idea meets configured score threshold."
                if allowed
                else "Score below configured threshold."
            ),
            "passed_checks": ["zone available"] if allowed else [],
            "blocked_reasons": [] if allowed else ["Score below threshold"],
            "entry": idea.get("entry", ""),
            "stop_loss": idea.get("stop_loss", ""),
            "take_profit": idea.get("take_profit", ""),
        }

    def _build_ai_response(self, payload: dict[str, Any]) -> dict[str, Any]:
        execution = dict(payload.get("execution_decision", {}) or {})
        context = dict(payload.get("execution_context", {}) or {})
        ai_signal = dict(payload.get("ai_signal", {}) or {})
        account = dict(payload.get("account", {}) or {})

        direction = str(execution.get("direction") or "neutral")
        prediction = "HOLD"
        if direction == "long":
            prediction = "BUY"
        elif direction == "short":
            prediction = "SELL"

        signal = str(ai_signal.get("signal") or "").lower()
        if signal == "long":
            prediction = "BUY"
        elif signal == "short":
            prediction = "SELL"
        elif signal in {"neutral", "disabled"} and not bool(execution.get("allowed", False)):
            prediction = "HOLD"

        confidence = max(
            _number(ai_signal.get("confidence"), 0.0),
            min(_number(execution.get("score"), 0.0) / 5.0, 1.0),
        )
        zone_state = str(context.get("zone_state") or "pending")
        if not bool(execution.get("allowed", False)):
            zone_confirmation = "rejected" if zone_state in {"invalidated", "deleted", "rejected"} else "pending"
        else:
            zone_confirmation = "confirmed"

        execution_hint = str(context.get("configured_style") or execution.get("style") or "advanced")
        rrr_state = str(context.get("rrr_state") or "none")
        if rrr_state not in {"", "none"}:
            execution_hint = f"{execution_hint}:{rrr_state}"

        spread = _number(payload.get("indicator_values", {}).get("spread_points"), 0.0)
        exposure = _number(account.get("risk_exposure_pct"), 0.0)
        risk_hint = "normal"
        if exposure >= 25.0:
            risk_hint = "account exposure is elevated; reduce size or wait."
        elif spread >= 30.0:
            risk_hint = "spread is elevated; prefer waiting for tighter execution."

        reasons = [
            str(execution.get("rationale") or "").strip(),
            str(ai_signal.get("summary") or "").strip(),
            str(context.get("reason") or "").strip(),
        ]
        reason = " ".join(part for part in reasons if part)

        return {
            "prediction": prediction,
            "confidence": round(confidence, 3),
            "reason": reason or "No actionable setup.",
            "zone_confirmation": zone_confirmation,
            "execution_hint": execution_hint,
            "risk_hint": risk_hint,
            "model_status": str(ai_signal.get("status") or "warming_up"),
            "signal_training_mode": str(ai_signal.get("training_mode") or "heuristic"),
        }

    def _news_filter(self, news: dict[str, Any]) -> dict[str, Any]:
        return {
            "trading_blocked": bool(news.get("trading_blocked", False)),
            "reason": str(news.get("reason") or "No blocking news event."),
            "upcoming_events": list(news.get("upcoming_events") or news.get("events") or []),
        }

    def _phase_outputs(self, market_structure: dict[str, Any] | None = None) -> dict[str, Any]:
        market_structure = dict(market_structure or {})
        return {
            "phase_2": {
                "status": "Collecting",
                "learning_ready": False,
                "feature_row_count": 0,
                "covered_phases": ["structure", "zones", "execution"],
            },
            "swings": list(market_structure.get("swings") or []),
            "events": list(market_structure.get("events") or []),
            "phase_3": {"fib_setups": []},
            "phase_4": {"imbalances": []},
            "phase_5": {"candlestick_patterns": []},
            "phase_6": {
                "strategy_mode": "monitor",
                "execution_timeframe": "1M",
                "breakout_levels": {},
                "grid_levels": [],
                "summary": "News execution plan is waiting for live event data.",
            },
        }
