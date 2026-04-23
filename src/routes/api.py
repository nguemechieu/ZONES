from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


# ============================================================
# ROUTE CONSTANTS
# ============================================================

API_ANALYSIS = "/api/analysis"
API_CHART = "/api/chart"
API_REPORTS = "/api/reports"
API_SYMBOLS = "/api/symbols"
API_COMMANDS = "/api/commands"
API_HEALTH = "/api/health"
API_SCHEMA = "/api/schema"
API_SYSTEM_STATUS = "/api/system/status"
API_PORTFOLIO = "/api/portfolio"


# ============================================================
# REQUEST MODELS
# ============================================================

@dataclass(slots=True)
class RouteQuery:
    account_id: str = ""
    symbol: str = ""
    timeframe: str = "5M"
    limit: int = 5
    format: str = "html"


@dataclass(slots=True)
class QueueCommandRequest:
    account_id: str
    symbol: str
    command_type: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CommandResultRequest:
    command_id: str
    status: str
    message: str
    extras: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PortfolioQuery:
    account_id: str = ""
    symbol: str = ""


# ============================================================
# RESPONSE MODELS
# ============================================================

@dataclass(slots=True)
class ApiEnvelope:
    status: str = "ok"
    title: str = ""
    subtitle: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class HealthResponse:
    status: str
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnalysisResponse:
    symbol: str
    account_id: str
    created_at: str
    execution_decision: dict[str, Any]
    ai_signal: dict[str, Any]
    account: dict[str, Any]
    zones: list[dict[str, Any]]
    liquidity_map: list[dict[str, Any]]
    trade_ideas: list[dict[str, Any]]
    chart_data: dict[str, Any]
    phase_outputs: dict[str, Any]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChartResponse:
    symbol: str
    account_id: str
    timeframe: str
    candles: list[dict[str, Any]]
    zones: list[dict[str, Any]]
    ai_signal: dict[str, Any]
    execution_decision: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ReportsResponse:
    items: list[dict[str, Any]]
    limit: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SymbolsResponse:
    account_id: str
    items: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CommandsResponse:
    account_id: str
    symbol: str
    pending: list[dict[str, Any]] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PortfolioSummary:
    balance: float = 0.0
    equity: float = 0.0
    free_margin: float = 0.0
    margin: float = 0.0
    open_positions: int = 0
    long_positions: int = 0
    short_positions: int = 0
    gross_lots: float = 0.0
    net_lots: float = 0.0
    floating_pnl: float = 0.0
    floating_return_pct: float = 0.0
    margin_usage_pct: float = 0.0
    risk_exposure_pct: float = 0.0
    largest_symbol_concentration_pct: float = 0.0


@dataclass(slots=True)
class PortfolioResponse:
    status: str
    account_id: str
    symbol: str
    summary: PortfolioSummary
    by_symbol: list[dict[str, Any]] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    report_stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


# ============================================================
# BUILDERS
# ============================================================

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def build_analysis_response(payload: dict[str, Any]) -> AnalysisResponse:
    account = payload.get("account", {}) or {}
    return AnalysisResponse(
        symbol=str(payload.get("symbol", "")),
        account_id=str(account.get("account_id", "")),
        created_at=str(payload.get("created_at", "")),
        execution_decision=dict(payload.get("execution_decision", {})),
        ai_signal=dict(payload.get("ai_signal", {})),
        account=dict(account),
        zones=list(payload.get("zones", [])),
        liquidity_map=list(payload.get("liquidity_map", [])),
        trade_ideas=list(payload.get("trade_ideas", [])),
        chart_data=dict(payload.get("chart_data", {})),
        phase_outputs=dict(payload.get("phase_outputs", {})),
        metadata=dict(payload.get("metadata", {})),
    )


def build_chart_response(payload: dict[str, Any], timeframe: str) -> ChartResponse:
    account = payload.get("account", {}) or {}
    zones = [
        zone for zone in payload.get("zones", [])
        if isinstance(zone, dict) and zone.get("timeframe") == timeframe
    ]
    return ChartResponse(
        symbol=str(payload.get("symbol", "")),
        account_id=str(account.get("account_id", "")),
        timeframe=timeframe,
        candles=list(payload.get("chart_data", {}).get(timeframe, [])),
        zones=zones,
        ai_signal=dict(payload.get("ai_signal", {})),
        execution_decision=dict(payload.get("execution_decision", {})),
    )


def build_reports_response(items: list[dict[str, Any]], limit: int) -> ReportsResponse:
    return ReportsResponse(items=items, limit=limit)


def build_symbols_response(account_id: str, items: list[dict[str, Any]]) -> SymbolsResponse:
    return SymbolsResponse(account_id=account_id or "all", items=items)


def build_commands_response(account_id: str, symbol: str, snapshot: dict[str, Any]) -> CommandsResponse:
    return CommandsResponse(
        account_id=account_id or "all",
        symbol=symbol or "all",
        pending=list(snapshot.get("pending", [])),
        history=list(snapshot.get("history", [])),
    )


def build_health_response(diagnostics: dict[str, Any]) -> HealthResponse:
    return HealthResponse(
        status=str(diagnostics.get("health", "unknown")),
        diagnostics=dict(diagnostics),
    )


def build_portfolio_response(
    payload: dict[str, Any],
    reports: list[dict[str, Any]] | None = None,
) -> PortfolioResponse:
    account = payload.get("account", {}) or {}
    positions = payload.get("positions", []) or []
    symbol = str(payload.get("symbol", ""))

    equity = _safe_float(account.get("equity"))
    balance = _safe_float(account.get("balance"))
    margin = _safe_float(account.get("margin"))
    free_margin = _safe_float(account.get("free_margin"))
    risk_exposure_pct = _safe_float(account.get("risk_exposure_pct"))
    open_positions = _safe_int(account.get("open_positions"))

    long_count = 0
    short_count = 0
    gross_lots = 0.0
    net_lots = 0.0
    floating_pnl = 0.0
    by_symbol: dict[str, dict[str, Any]] = {}

    for pos in positions:
        if not isinstance(pos, dict):
            continue

        pos_symbol = str(pos.get("symbol", "") or symbol)
        order_type = _safe_int(pos.get("type"), -1)
        lots = _safe_float(pos.get("lots"))
        profit = _safe_float(pos.get("profit"))

        if pos_symbol not in by_symbol:
            by_symbol[pos_symbol] = {
                "symbol": pos_symbol,
                "positions": 0,
                "long_positions": 0,
                "short_positions": 0,
                "gross_lots": 0.0,
                "net_lots": 0.0,
                "floating_pnl": 0.0,
            }

        signed_lots = 0.0
        if order_type == 0:
            long_count += 1
            signed_lots = lots
            by_symbol[pos_symbol]["long_positions"] += 1
        elif order_type == 1:
            short_count += 1
            signed_lots = -lots
            by_symbol[pos_symbol]["short_positions"] += 1

        gross_lots += abs(lots)
        net_lots += signed_lots
        floating_pnl += profit

        row = by_symbol[pos_symbol]
        row["positions"] += 1
        row["gross_lots"] += abs(lots)
        row["net_lots"] += signed_lots
        row["floating_pnl"] += profit

    by_symbol_rows = sorted(
        by_symbol.values(),
        key=lambda item: abs(
            float(item["floating_pnl"])) + float(item["gross_lots"]),
        reverse=True,
    )

    concentration_pct = 0.0
    if gross_lots > 0 and by_symbol_rows:
        concentration_pct = max(
            (float(row["gross_lots"]) / gross_lots) * 100.0 for row in by_symbol_rows)

    margin_usage_pct = (margin / equity * 100.0) if equity > 0 else 0.0
    floating_return_pct = (floating_pnl / balance *
                           100.0) if balance > 0 else 0.0

    risk_flags: list[str] = []
    if margin_usage_pct >= 50:
        risk_flags.append("High margin usage")
    if concentration_pct >= 50:
        risk_flags.append("High symbol concentration")
    if risk_exposure_pct >= 30:
        risk_flags.append("Elevated account exposure")
    if floating_pnl < 0 and abs(floating_return_pct) >= 3:
        risk_flags.append("Meaningful floating drawdown")

    allowed = 0
    blocked = 0
    for item in reports or []:
        if not isinstance(item, dict):
            continue
        decision = item.get("execution_decision", {}) or {}
        if decision.get("allowed"):
            allowed += 1
        else:
            blocked += 1

    summary = PortfolioSummary(
        balance=balance,
        equity=equity,
        free_margin=free_margin,
        margin=margin,
        open_positions=open_positions,
        long_positions=long_count,
        short_positions=short_count,
        gross_lots=gross_lots,
        net_lots=net_lots,
        floating_pnl=floating_pnl,
        floating_return_pct=floating_return_pct,
        margin_usage_pct=margin_usage_pct,
        risk_exposure_pct=risk_exposure_pct,
        largest_symbol_concentration_pct=concentration_pct,
    )

    return PortfolioResponse(
        status="ok",
        account_id=str(account.get("account_id", "")),
        symbol=symbol,
        summary=summary,
        by_symbol=by_symbol_rows,
        risk_flags=risk_flags,
        report_stats={
            "sample_size": len(reports or []),
            "allowed_count": allowed,
            "blocked_count": blocked,
        },
    )


# ============================================================
# SCHEMA DESCRIPTION
# ============================================================

def api_schema() -> dict[str, Any]:
    return {
        "routes": {
            API_ANALYSIS: "Live structured analysis payload",
            API_CHART: "Candlestick and zone payload for one timeframe",
            API_REPORTS: "Recent stored reports",
            API_SYMBOLS: "Tracked symbols in memory",
            API_COMMANDS: "Pending commands and command history",
            API_HEALTH: "Diagnostics and service health",
            API_SCHEMA: "API schema and route descriptions",
            API_SYSTEM_STATUS: "Database, runtime settings, model state, diagnostics",
            API_PORTFOLIO: "Portfolio exposure, floating PnL, concentration, report stats",
        },
        "pipe_actions": [
            "fetch_next_command",
            "fetch_chart_snapshot",
            "send_command_result",
            "queue_command",
        ],
        "notes": [
            "HTML rendering stays in dashboard.py",
            "Transport handling stays in named_pipe_server.py and websocket bridge",
            "api.py defines the shared contract and JSON response models",
        ],
    }
