from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import EngineConfig
from .database import LearningRepository


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
    }
    return aliases.get(normalized, normalized or "5M")


class LiveFeedService:
    def __init__(self, config: EngineConfig, repository: LearningRepository) -> None:
        self.config = config
        self.repository = repository
        self._latest: dict[tuple[str, str], dict[str, Any]] = {}
        self._commands: list[dict[str, Any]] = []

    def latest_report(self, account_id: str | None = None, symbol: str | None = None) -> dict[str, Any] | None:
        account = account_id or self.config.account_id
        target_symbol = symbol or self.config.symbol
        payload = self._latest.get((account, target_symbol))
        if payload:
            return dict(payload)
        return self.repository.latest_report(account_id=account_id, symbol=symbol)

    def tracked_symbols(self, account_id: str | None = None) -> list[dict[str, Any]]:
        memory = [
            {"account_id": account, "symbol": symbol, "last_seen": payload.get("created_at", "")}
            for (account, symbol), payload in self._latest.items()
            if not account_id or account == account_id
        ]
        stored = self.repository.tracked_symbols(account_id)
        by_key: dict[tuple[str, str], dict[str, Any]] = {}
        for item in [*stored, *memory]:
            by_key[(str(item.get("account_id", "")), str(item.get("symbol", "")))] = item
        if not by_key:
            by_key[(self.config.account_id, self.config.symbol)] = {
                "account_id": self.config.account_id,
                "symbol": self.config.symbol,
                "last_seen": "",
            }
        return sorted(by_key.values(), key=lambda item: str(item.get("last_seen", "")), reverse=True)

    def ingest_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Ingest payload must be a JSON object.")
        report = self._normalize_payload(payload)
        account_id = str(report["account"]["account_id"])
        symbol = str(report["symbol"])
        self._latest[(account_id, symbol)] = report
        self.repository.save_report(report)
        return {"status": "ok", "account_id": account_id, "symbol": symbol, "report": report}

    def waiting_payload(self, account_id: str | None = None, symbol: str | None = None) -> dict[str, Any]:
        target_account = account_id or self.config.account_id
        target_symbol = symbol or self.config.symbol
        base_price = 1.085 if target_symbol.upper().endswith("USD") else 100.0
        candles = self._demo_candles(base_price)
        payload = {
            "created_at": _utc_now(),
            "symbol": target_symbol,
            "account": self._account_payload({"account_id": target_account}),
            "metadata": {
                "ingest": {"source": "waiting", "message": "Waiting for MT4 live feed data."},
                "custom_inputs": self.config.to_dict(),
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
            "news_filter": {"trading_blocked": False, "reason": "No live news filter data yet.", "upcoming_events": []},
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
            "chart_data": {"1H": candles[::5], "5M": candles, "1M": candles[-45:]},
            "phase_outputs": self._phase_outputs(),
        }
        return payload

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
                {"timestamp": "2026-04-22T12:00:00Z", "open": 1.0801, "high": 1.0810, "low": 1.0792, "close": 1.0806}
            ],
            "positions": [],
            "zones": [],
            "news": {"trading_blocked": False, "reason": "clear"},
        }

    def enqueue_command(
        self,
        *,
        account_id: str,
        symbol: str,
        command_type: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        command_type = command_type.strip()
        if not command_type:
            raise ValueError("Command type is required.")
        command = {
            "id": f"cmd-{len(self._commands) + 1}",
            "created_at": _utc_now(),
            "account_id": account_id or self.config.account_id,
            "symbol": symbol or self.config.symbol,
            "type": command_type,
            "status": "pending",
            "params": params,
            "message": "",
            "recorded_at": "",
        }
        self._commands.insert(0, command)
        self.repository.add_command(command)
        return command

    def command_snapshot(self, account_id: str | None = None, symbol: str | None = None) -> dict[str, Any]:
        commands = [
            item
            for item in [*self._commands, *self.repository.command_rows(account_id, symbol)]
            if (not account_id or item.get("account_id") == account_id)
            and (not symbol or item.get("symbol") == symbol)
        ]
        pending = [item for item in commands if item.get("status") == "pending"]
        history = [item for item in commands if item.get("status") != "pending"]
        return {"pending": pending[:50], "history": history[:50]}

    def _normalize_payload(self, raw: dict[str, Any]) -> dict[str, Any]:
        symbol = str(raw.get("symbol") or raw.get("instrument") or self.config.symbol).upper()
        timeframe = _normalize_timeframe(str(raw.get("timeframe") or raw.get("time_frame") or "5M"))
        candles = self._normalize_candles(raw.get("candles") or raw.get("rates") or raw.get("chart_data") or [])
        if not candles:
            candles = self._demo_candles(1.085)
        zones = self._normalize_zones(raw.get("zones") or raw.get("supply_demand_zones") or [], timeframe, candles)
        ideas = self._build_trade_ideas(zones, candles, timeframe)
        decision = self._execution_decision(ideas)
        payload = {
            "created_at": str(raw.get("created_at") or raw.get("time") or _utc_now()),
            "symbol": symbol,
            "account": self._account_payload(raw.get("account") or raw),
            "metadata": {
                "ingest": {"source": "live", "message": "Live payload accepted."},
                "custom_inputs": dict(raw.get("custom_inputs") or self.config.to_dict()),
            },
            "ai_summary": str(
                raw.get("ai_summary")
                or "Live report normalized. AI signal score is calculated from the current execution setup."
            ),
            "price_action": raw.get("price_action") or self._price_action(candles, timeframe),
            "trade_ideas": raw.get("trade_ideas") or ideas,
            "zones": zones,
            "liquidity_map": raw.get("liquidity_map") or [],
            "news_filter": self._news_filter(raw.get("news") or raw.get("news_filter") or {}),
            "execution_decision": raw.get("execution_decision") or decision,
            "chart_data": self._chart_data(raw.get("chart_data"), candles, timeframe),
            "phase_outputs": raw.get("phase_outputs") or self._phase_outputs(),
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
                    "timestamp": str(candle.get("timestamp") or candle.get("time") or (_utc_now() if index == 0 else "")),
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
        candles = []
        for index in range(72):
            angle = index / 7.0
            open_value = base_price + math.sin(angle) * 0.002 + index * 0.00001
            close_value = open_value + math.sin(angle * 1.7) * 0.0006
            high_value = max(open_value, close_value) + 0.00045
            low_value = min(open_value, close_value) - 0.00045
            candles.append(
                {
                    "timestamp": (now - timedelta(minutes=(71 - index) * 5)).isoformat(timespec="seconds"),
                    "open": round(open_value, 5),
                    "high": round(high_value, 5),
                    "low": round(low_value, 5),
                    "close": round(close_value, 5),
                    "volume": 100 + index,
                }
            )
        return candles

    def _chart_data(self, raw_chart_data: Any, candles: list[dict[str, Any]], timeframe: str) -> dict[str, list[dict[str, Any]]]:
        if isinstance(raw_chart_data, dict):
            normalized = {
                _normalize_timeframe(str(key)): self._normalize_candles(value)
                for key, value in raw_chart_data.items()
                if self._normalize_candles(value)
            }
            if normalized:
                return normalized
        return {timeframe: candles, "5M": candles, "1M": candles[-45:], "1H": candles[::5] or candles}

    def _normalize_zones(self, zones: Any, timeframe: str, candles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, zone in enumerate(zones if isinstance(zones, list) else []):
            if not isinstance(zone, dict):
                continue
            lower = _number(zone.get("lower") or zone.get("low"), 0.0)
            upper = _number(zone.get("upper") or zone.get("high"), lower)
            normalized.append(
                {
                    "timeframe": _normalize_timeframe(str(zone.get("timeframe") or timeframe)),
                    "kind": str(zone.get("kind") or zone.get("type") or "demand").lower(),
                    "family": str(zone.get("family") or "main").lower(),
                    "strength": int(_number(zone.get("strength"), 1)),
                    "strength_label": str(zone.get("strength_label") or "S1"),
                    "lower": min(lower, upper),
                    "upper": max(lower, upper),
                    "status": str(zone.get("status") or "fresh"),
                    "mode_bias": str(zone.get("mode_bias") or "neutral"),
                    "origin_index": int(_number(zone.get("origin_index"), index)),
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
                "status": "fresh",
                "mode_bias": "bullish",
                "origin_index": max(0, len(candles) - 30),
            },
            {
                "timeframe": timeframe,
                "kind": "supply",
                "family": "main",
                "strength": 2,
                "strength_label": "S2",
                "lower": round(last_close + 0.001, 5),
                "upper": round(last_close + 0.002, 5),
                "status": "fresh",
                "mode_bias": "bearish",
                "origin_index": max(0, len(candles) - 25),
            },
        ]

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
        ideas = []
        for zone in zones[:4]:
            direction = "long" if zone["kind"] in {"demand", "support"} else "short"
            entry = last_close
            risk = max(abs(entry - _number(zone["lower" if direction == "long" else "upper"], entry)), 0.001)
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
        allowed = score >= self.config.minimum_trade_score
        return {
            "allowed": allowed,
            "direction": idea.get("direction", "neutral"),
            "timeframe": idea.get("timeframe", "5M"),
            "score": score,
            "rationale": "Trade idea meets configured score threshold." if allowed else "Score below configured threshold.",
            "passed_checks": ["zone available"] if allowed else [],
            "blocked_reasons": [] if allowed else ["Score below threshold"],
            "entry": idea.get("entry", ""),
            "stop_loss": idea.get("stop_loss", ""),
            "take_profit": idea.get("take_profit", ""),
        }

    def _news_filter(self, news: dict[str, Any]) -> dict[str, Any]:
        return {
            "trading_blocked": bool(news.get("trading_blocked", False)),
            "reason": str(news.get("reason") or "No blocking news event."),
            "upcoming_events": list(news.get("upcoming_events") or news.get("events") or []),
        }

    def _phase_outputs(self) -> dict[str, Any]:
        return {
            "phase_2": {
                "status": "Collecting",
                "learning_ready": False,
                "feature_row_count": 0,
                "covered_phases": ["structure", "zones", "execution"],
            },
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
