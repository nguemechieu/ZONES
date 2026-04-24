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
    long_lots = 0.0
    short_lots = 0.0
    long_pnl = 0.0
    short_pnl = 0.0
    for position in positions:
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol") or "UNKNOWN").upper()
        direction = str(
            position.get("direction")
            or position.get("side")
            or position.get("type")
            or position.get("order_type")
            or ""
        ).lower()
        lots = _number(position.get("lots") or position.get("volume"), 0.0)
        pnl = _number(position.get("pnl") or position.get("profit"), 0.0)
        is_short = direction in {"short", "sell", "1"} or "sell" in direction
        item = by_symbol.setdefault(
            symbol,
            {
                "symbol": symbol,
                "count": 0,
                "long_count": 0,
                "short_count": 0,
                "lots": 0.0,
                "long_lots": 0.0,
                "short_lots": 0.0,
                "net_lots": 0.0,
                "floating_pnl": 0.0,
            },
        )
        item["count"] += 1
        item["lots"] += lots
        item["floating_pnl"] += pnl
        if is_short:
            short_lots += lots
            short_pnl += pnl
            item["short_count"] += 1
            item["short_lots"] += lots
            item["net_lots"] -= lots
        else:
            long_lots += lots
            long_pnl += pnl
            item["long_count"] += 1
            item["long_lots"] += lots
            item["net_lots"] += lots

    exposure = list(by_symbol.values())
    max_symbol_lots = max((_number(item.get("lots"), 0.0) for item in exposure), default=0.0)
    total_lots = sum(_number(item.get("lots"), 0.0) for item in exposure)
    concentration = 0.0 if total_lots <= 0 else max_symbol_lots / total_lots
    weights = [
        (_number(item.get("lots"), 0.0) / total_lots)
        for item in exposure
        if total_lots > 0
    ]
    hhi = sum(weight * weight for weight in weights)
    effective_bets = 0.0 if hhi <= 0 else 1.0 / hhi
    margin_level = 0.0 if margin <= 0 else equity / margin * 100
    margin_utilization = 0.0 if equity <= 0 else margin / equity
    free_margin_ratio = 0.0 if equity <= 0 else free_margin / equity
    daily_return = 0.0 if balance <= 0 else floating_pnl / balance
    gross_exposure_lots = long_lots + short_lots
    net_exposure_lots = long_lots - short_lots
    long_short_ratio = 0.0 if short_lots <= 0 else long_lots / short_lots
    leverage_proxy = 0.0 if equity <= 0 else gross_exposure_lots / max(equity / 10000.0, 1.0)
    var_95_proxy = abs(floating_pnl) + (gross_exposure_lots * max(balance, equity, 1.0) * 0.0005)
    stress_loss_2pct = gross_exposure_lots * max(balance, equity, 1.0) * 0.02

    return {
        "account_id": account.get("account_id", "demo"),
        "symbol": payload.get("symbol", "EURUSD") if isinstance(payload, dict) else "EURUSD",
        "fund_summary": {
            "nav": round(equity, 2),
            "aum_proxy": round(max(balance, equity), 2),
            "daily_return_pct": round(daily_return * 100, 3),
            "floating_pnl": round(floating_pnl, 2),
            "open_position_count": len(positions),
        },
        "risk_metrics": {
            "gross_exposure_lots": round(gross_exposure_lots, 2),
            "net_exposure_lots": round(net_exposure_lots, 2),
            "long_lots": round(long_lots, 2),
            "short_lots": round(short_lots, 2),
            "long_short_ratio": round(long_short_ratio, 3),
            "leverage_proxy": round(leverage_proxy, 3),
            "margin_level_pct": round(margin_level, 2),
            "margin_utilization_pct": round(margin_utilization * 100, 2),
            "free_margin_ratio_pct": round(free_margin_ratio * 100, 2),
            "concentration_risk": round(concentration, 3),
            "hhi_concentration": round(hhi, 3),
            "effective_bets": round(effective_bets, 2),
            "var_95_proxy": round(var_95_proxy, 2),
            "stress_loss_2pct_proxy": round(stress_loss_2pct, 2),
        },
        "pnl_attribution": {
            "long_pnl": round(long_pnl, 2),
            "short_pnl": round(short_pnl, 2),
            "floating_pnl": round(floating_pnl, 2),
        },
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
