from __future__ import annotations

from typing import Any


def _number(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _text(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _round(value: float, places: int = 5) -> float:
    return round(float(value), places)


def _normalize_candles(payload: dict[str, Any], timeframe: str) -> list[dict[str, Any]]:
    chart_data = payload.get("chart_data", {}) if isinstance(payload, dict) else {}
    candles = chart_data.get(timeframe, []) if isinstance(chart_data, dict) else []
    normalized: list[dict[str, Any]] = []

    for index, candle in enumerate(candles if isinstance(candles, list) else []):
        if not isinstance(candle, dict):
            continue
        close = _number(candle.get("close"), 0.0)
        open_price = _number(candle.get("open"), close)
        high = _number(candle.get("high"), max(open_price, close))
        low = _number(candle.get("low"), min(open_price, close))
        normalized.append(
            {
                "index": index,
                "timestamp": _text(candle.get("timestamp"), str(index)),
                "open": open_price,
                "high": max(high, open_price, close),
                "low": min(low, open_price, close),
                "close": close,
            }
        )

    return normalized


def _normalize_zones(
        payload: dict[str, Any],
        timeframe: str,
        *,
        family: str,
        kind: str,
        min_strength: float,
) -> list[dict[str, Any]]:
    zones: list[dict[str, Any]] = []
    raw_zones = payload.get("zones", []) if isinstance(payload, dict) else []
    family_filter = family.lower()
    kind_filter = kind.lower()

    for index, zone in enumerate(raw_zones if isinstance(raw_zones, list) else []):
        if not isinstance(zone, dict):
            continue
        zone_timeframe = _text(zone.get("timeframe"), timeframe).upper()
        if zone_timeframe != timeframe.upper():
            continue
        if _text(zone.get("status"), "fresh").lower() == "deleted":
            continue

        zone_family = _text(zone.get("family"), "main").lower()
        zone_kind = _text(zone.get("kind"), "demand").lower()
        strength = _number(zone.get("strength"), 1.0)
        if family_filter != "all" and zone_family != family_filter:
            continue
        if kind_filter != "all" and zone_kind != kind_filter:
            continue
        if strength < min_strength:
            continue

        lower = _number(zone.get("lower") or zone.get("low"), 0.0)
        upper = _number(zone.get("upper") or zone.get("high"), lower)
        zones.append(
            {
                "id": _text(zone.get("id"), f"zone-{index}"),
                "timeframe": zone_timeframe,
                "kind": zone_kind,
                "family": zone_family,
                "strength": strength,
                "strength_label": _text(zone.get("strength_label"), f"S{int(strength)}"),
                "lower": min(lower, upper),
                "upper": max(lower, upper),
                "origin_index": _integer(zone.get("origin_index"), 0),
                "mode_bias": _text(zone.get("mode_bias"), "neutral"),
            }
        )

    return zones


def _zone_direction(zone: dict[str, Any]) -> str:
    return "long" if zone.get("kind") in {"demand", "support"} else "short"


def _touches_zone(candle: dict[str, Any], zone: dict[str, Any]) -> bool:
    return _number(candle.get("low")) <= _number(zone.get("upper")) and _number(candle.get("high")) >= _number(zone.get("lower"))


def _choose_zone(candle: dict[str, Any], zones: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    touched = [
        zone
        for zone in zones
        if _integer(zone.get("origin_index"), 0) <= index and _touches_zone(candle, zone)
    ]
    if not touched:
        return None
    touched.sort(
        key=lambda item: (
            _number(item.get("strength"), 0.0),
            1 if item.get("family") == "main" else 0,
            _integer(item.get("origin_index"), 0),
        ),
        reverse=True,
    )
    return touched[0]


def _exit_trade(
        *,
        candles: list[dict[str, Any]],
        entry_index: int,
        entry_price: float,
        direction: str,
        stop_loss: float,
        take_profit: float,
        max_hold_bars: int,
) -> tuple[int, dict[str, Any], str]:
    final_index = min(len(candles) - 1, entry_index + max_hold_bars)
    for index in range(entry_index, final_index + 1):
        candle = candles[index]
        high = _number(candle.get("high"))
        low = _number(candle.get("low"))
        if direction == "long":
            hit_stop = low <= stop_loss
            hit_target = high >= take_profit
        else:
            hit_stop = high >= stop_loss
            hit_target = low <= take_profit

        if hit_stop and hit_target:
            return index, candle, "stop_loss"
        if hit_stop:
            return index, candle, "stop_loss"
        if hit_target:
            return index, candle, "take_profit"

    return final_index, candles[final_index], "time_exit"


def build_backtest_analysis(
        payload: dict[str, Any],
        *,
        timeframe: str = "5M",
        initial_balance: float = 10000.0,
        risk_per_trade_pct: float = 1.0,
        risk_reward: float = 2.0,
        max_hold_bars: int = 48,
        max_trades: int = 50,
        min_strength: float = 1.0,
        zone_family: str = "all",
        zone_kind: str = "all",
        stop_buffer: float = 0.0,
) -> dict[str, Any]:
    """Run a deterministic zone-touch backtest against the current candle payload."""
    timeframe = _text(timeframe, "5M").upper()
    initial_balance = max(_number(initial_balance, 10000.0), 1.0)
    risk_per_trade_pct = min(max(_number(risk_per_trade_pct, 1.0), 0.01), 25.0)
    risk_reward = max(_number(risk_reward, 2.0), 0.1)
    max_hold_bars = max(_integer(max_hold_bars, 48), 1)
    max_trades = max(_integer(max_trades, 50), 1)
    min_strength = max(_number(min_strength, 1.0), 0.0)
    stop_buffer = max(_number(stop_buffer, 0.0), 0.0)

    candles = _normalize_candles(payload, timeframe)
    zones = _normalize_zones(
        payload,
        timeframe,
        family=_text(zone_family, "all"),
        kind=_text(zone_kind, "all"),
        min_strength=min_strength,
    )

    equity = initial_balance
    peak_equity = initial_balance
    max_drawdown = 0.0
    equity_curve = [
        {
            "trade": 0,
            "equity": _round(equity, 2),
            "drawdown_pct": 0.0,
        }
    ]
    trades: list[dict[str, Any]] = []
    index = 0

    while index < len(candles) - 1 and len(trades) < max_trades:
        signal_candle = candles[index]
        zone = _choose_zone(signal_candle, zones, index)
        if zone is None:
            index += 1
            continue

        entry_index = index + 1
        entry_candle = candles[entry_index]
        direction = _zone_direction(zone)
        entry_price = _number(entry_candle.get("open"), _number(signal_candle.get("close")))

        if direction == "long":
            stop_loss = _number(zone.get("lower")) - stop_buffer
            risk_distance = entry_price - stop_loss
            if risk_distance <= 0:
                index += 1
                continue
            take_profit = entry_price + risk_distance * risk_reward
        else:
            stop_loss = _number(zone.get("upper")) + stop_buffer
            risk_distance = stop_loss - entry_price
            if risk_distance <= 0:
                index += 1
                continue
            take_profit = entry_price - risk_distance * risk_reward

        exit_index, exit_candle, exit_reason = _exit_trade(
            candles=candles,
            entry_index=entry_index,
            entry_price=entry_price,
            direction=direction,
            stop_loss=stop_loss,
            take_profit=take_profit,
            max_hold_bars=max_hold_bars,
        )
        exit_price = _number(exit_candle.get("close"), entry_price)
        if exit_reason == "stop_loss":
            exit_price = stop_loss
        elif exit_reason == "take_profit":
            exit_price = take_profit

        pnl_points = exit_price - entry_price if direction == "long" else entry_price - exit_price
        r_multiple = pnl_points / risk_distance if risk_distance > 0 else 0.0
        risk_amount = equity * (risk_per_trade_pct / 100.0)
        pnl_amount = risk_amount * r_multiple
        equity += pnl_amount
        peak_equity = max(peak_equity, equity)
        drawdown_pct = 0.0 if peak_equity <= 0 else (peak_equity - equity) / peak_equity * 100.0
        max_drawdown = max(max_drawdown, drawdown_pct)

        trade = {
            "number": len(trades) + 1,
            "symbol": _text(payload.get("symbol"), ""),
            "timeframe": timeframe,
            "direction": direction,
            "zone_kind": zone.get("kind"),
            "zone_family": zone.get("family"),
            "zone_strength": zone.get("strength_label"),
            "signal_index": index,
            "entry_index": entry_index,
            "exit_index": exit_index,
            "entry_time": entry_candle.get("timestamp"),
            "exit_time": exit_candle.get("timestamp"),
            "entry": _round(entry_price),
            "stop_loss": _round(stop_loss),
            "take_profit": _round(take_profit),
            "exit": _round(exit_price),
            "exit_reason": exit_reason,
            "pnl_points": _round(pnl_points),
            "r_multiple": _round(r_multiple, 3),
            "pnl_amount": _round(pnl_amount, 2),
            "equity": _round(equity, 2),
        }
        trades.append(trade)
        equity_curve.append(
            {
                "trade": len(trades),
                "equity": _round(equity, 2),
                "drawdown_pct": _round(drawdown_pct, 3),
            }
        )
        index = max(exit_index + 1, entry_index + 1)

    wins = [trade for trade in trades if _number(trade.get("pnl_amount")) > 0]
    losses = [trade for trade in trades if _number(trade.get("pnl_amount")) < 0]
    gross_profit = sum(_number(trade.get("pnl_amount")) for trade in wins)
    gross_loss = abs(sum(_number(trade.get("pnl_amount")) for trade in losses))
    net_pnl = equity - initial_balance
    total_r = sum(_number(trade.get("r_multiple")) for trade in trades)
    average_r = total_r / len(trades) if trades else 0.0
    profit_factor = 0.0 if gross_loss <= 0 else gross_profit / gross_loss
    if gross_profit > 0 and gross_loss == 0:
        profit_factor = gross_profit

    summary = {
        "symbol": _text(payload.get("symbol"), ""),
        "timeframe": timeframe,
        "initial_balance": _round(initial_balance, 2),
        "ending_balance": _round(equity, 2),
        "net_pnl": _round(net_pnl, 2),
        "return_pct": _round(net_pnl / initial_balance * 100.0, 3),
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": _round((len(wins) / len(trades) * 100.0) if trades else 0.0, 2),
        "profit_factor": _round(profit_factor, 3),
        "max_drawdown_pct": _round(max_drawdown, 3),
        "net_r": _round(total_r, 3),
        "expectancy_r": _round(average_r, 3),
        "average_trade": _round(net_pnl / len(trades), 2) if trades else 0.0,
    }

    return {
        "status": "ok" if candles and zones else "insufficient_data",
        "strategy": "zone_touch_next_open",
        "assumptions": [
            "Entry occurs at the next candle open after price touches an eligible zone.",
            "If stop and target are both touched in one candle, stop-loss is applied first.",
            "Position size is normalized so each stop-loss risks the configured account percent.",
            "Spread, slippage, swaps, commissions, and broker pip values are not included.",
        ],
        "parameters": {
            "timeframe": timeframe,
            "initial_balance": _round(initial_balance, 2),
            "risk_per_trade_pct": _round(risk_per_trade_pct, 3),
            "risk_reward": _round(risk_reward, 3),
            "max_hold_bars": max_hold_bars,
            "max_trades": max_trades,
            "min_strength": _round(min_strength, 3),
            "zone_family": _text(zone_family, "all").lower(),
            "zone_kind": _text(zone_kind, "all").lower(),
            "stop_buffer": _round(stop_buffer),
        },
        "data": {
            "candles": len(candles),
            "eligible_zones": len(zones),
        },
        "summary": summary,
        "equity_curve": equity_curve,
        "trades": trades,
    }
