from __future__ import annotations

from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def build_portfolio_analysis(payload: dict[str, Any]) -> dict[str, Any]:
    account = payload.get("account", {}) if isinstance(payload, dict) else {}
    positions = payload.get("positions", []) if isinstance(payload, dict) else []
    if not isinstance(positions, list):
        positions = []

    balance = _number(account.get("balance"), 0.0)
    equity = _number(account.get("equity"), balance)
    margin = _number(account.get("margin"), 0.0)
    free_margin = _number(account.get("free_margin"), equity - margin)
    floating_pnl = equity - balance

    by_symbol: dict[str, dict[str, Any]] = {}
    for position in positions:
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol") or "UNKNOWN").upper()
        item = by_symbol.setdefault(symbol, {"symbol": symbol, "count": 0, "lots": 0.0, "floating_pnl": 0.0})
        item["count"] += 1
        item["lots"] += _number(position.get("lots") or position.get("volume"), 0.0)
        item["floating_pnl"] += _number(position.get("pnl") or position.get("profit"), 0.0)

    exposure = list(by_symbol.values())
    max_symbol_lots = max((_number(item.get("lots"), 0.0) for item in exposure), default=0.0)
    total_lots = sum(_number(item.get("lots"), 0.0) for item in exposure)
    concentration = 0.0 if total_lots <= 0 else max_symbol_lots / total_lots
    margin_level = 0.0 if margin <= 0 else equity / margin * 100

    return {
        "account_id": account.get("account_id", "demo"),
        "symbol": payload.get("symbol", "EURUSD") if isinstance(payload, dict) else "EURUSD",
        "balance": balance,
        "equity": equity,
        "free_margin": free_margin,
        "margin": margin,
        "floating_pnl": round(floating_pnl, 2),
        "margin_level_pct": round(margin_level, 2),
        "open_position_count": len(positions),
        "total_lots": round(total_lots, 2),
        "concentration_risk": round(concentration, 3),
        "exposure_by_symbol": exposure,
        "risk_notes": _risk_notes(floating_pnl, balance, margin_level, concentration),
    }


def _risk_notes(floating_pnl: float, balance: float, margin_level: float, concentration: float) -> list[str]:
    notes: list[str] = []
    if balance and floating_pnl / balance <= -0.03:
        notes.append("Floating drawdown is greater than 3% of balance.")
    if margin_level and margin_level < 300:
        notes.append("Margin level is below the conservative 300% threshold.")
    if concentration > 0.7:
        notes.append("Exposure is concentrated in a single symbol.")
    if not notes:
        notes.append("No portfolio concentration or margin warnings detected.")
    return notes
