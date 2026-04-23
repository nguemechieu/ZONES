from __future__ import annotations

import json
import logging
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging import Logger
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from src.db.repository.learning_repository import LearningRepository
from src.execution.system_state import (
    RuntimeSettingsStore,
    SignalModelService,
    coerce_bool,
    coerce_float,
    coerce_int,
    mask_database_url,
)
from src.server.bridge import LiveFeedService
from src.server.engine_config import EngineConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOGO_PATH = PROJECT_ROOT / "assets" / "Zones.ico"


# ============================================================
# Helper formatting
# ============================================================

def _parse_allowed_sessions(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        raw_items = [str(item).strip().lower() for item in value]
    else:
        raw_items = [part.strip().lower() for part in str(value or "").replace(";", ",").split(",")]
    sessions = [item for item in raw_items if item]
    if not sessions:
        return fallback
    return tuple(dict.fromkeys(sessions))


def _labelize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _format_scalar(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.4f}".rstrip("0").rstrip(".")
    return escape(str(value))


def _is_scalar(value: object) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _dict_table(data: dict[str, Any]) -> str:
    rows = "".join(
        f"<tr><th>{escape(_labelize(str(key)))}</th><td>{_format_scalar(value)}</td></tr>"
        for key, value in data.items()
    )
    return (
        "<table><thead><tr><th>Field</th><th>Value</th></tr></thead>"
        f"<tbody>{rows or '<tr><td colspan=\"2\">No fields</td></tr>'}</tbody></table>"
    )


def _render_value(value: object, *, level: int = 0) -> str:
    if _is_scalar(value):
        return f"<div class='scalar'>{_format_scalar(value)}</div>"

    if isinstance(value, list):
        if not value:
            return "<div class='empty'>No items</div>"

        if all(_is_scalar(item) for item in value):
            pills = "".join(f"<span class='pill'>{_format_scalar(item)}</span>" for item in value)
            return f"<div>{pills}</div>"

        if all(isinstance(item, dict) for item in value):
            columns: list[str] = []
            for item in value:
                for key in item:
                    key_name = str(key)
                    if key_name not in columns:
                        columns.append(key_name)

            header = "".join(f"<th>{escape(_labelize(column))}</th>" for column in columns)
            rows = []
            for item in value:
                cells = []
                for column in columns:
                    cell_value = item.get(column, "")
                    if _is_scalar(cell_value):
                        cells.append(f"<td>{_format_scalar(cell_value)}</td>")
                    else:
                        cells.append(
                            "<td><details><summary>Open</summary>"
                            + _render_value(cell_value, level=level + 1)
                            + "</details></td>"
                        )
                rows.append("<tr>" + "".join(cells) + "</tr>")
            return "<table><thead><tr>" + header + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"

        cards = []
        for index, item in enumerate(value, start=1):
            cards.append(
                "<section class='nested-card'>"
                f"<div class='nested-title'>Item {index}</div>"
                f"{_render_value(item, level=level + 1)}"
                "</section>"
            )
        return "".join(cards)

    if isinstance(value, dict):
        scalar_items = {key: item for key, item in value.items() if _is_scalar(item)}
        nested_items = {key: item for key, item in value.items() if not _is_scalar(item)}
        parts: list[str] = []
        if scalar_items:
            parts.append(_dict_table(scalar_items))
        for key, item in nested_items.items():
            parts.append(
                "<section class='nested-card'>"
                f"<div class='nested-title'>{escape(_labelize(str(key)))}</div>"
                f"{_render_value(item, level=level + 1)}"
                "</section>"
            )
        return "".join(parts) or "<div class='empty'>No data</div>"

    return f"<div class='scalar'>{escape(str(value))}</div>"


def _route_navigation(current_path: str) -> str:
    routes = [
        ("/", "Dashboard"),
        ("/chart", "Chart"),
        ("/system", "System"),
        ("/api/analysis", "Analysis"),
        ("/api/reports", "Reports"),
        ("/api/symbols", "Symbols"),
        ("/api/commands", "Commands"),
        ("/api/health", "Health"),
        ("/api/schema", "Schema"),
    ]
    return "".join(
        f"<a class='nav-link{' active' if current_path == path else ''}' href='{path}'>{label}</a>"
        for path, label in routes
    )


# ============================================================
# HTML templates
# ============================================================

def _base_css() -> str:
    return """
    :root {
      --bg: #08111e;
      --panel: rgba(9, 22, 41, 0.95);
      --panel-alt: rgba(17, 37, 59, 0.92);
      --text: #e9f1f8;
      --muted: #8da4bd;
      --line: rgba(141, 164, 189, 0.18);
      --accent: #f6b73c;
      --accent-alt: #5fd1ff;
      --success: #39d98a;
      --error: #ff6b6b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(246, 183, 60, 0.12), transparent 22%),
        radial-gradient(circle at left center, rgba(95, 209, 255, 0.12), transparent 24%),
        linear-gradient(180deg, #08111e 0%, #0b1930 100%);
      min-height: 100vh;
    }
    .shell { max-width: 1360px; margin: 0 auto; padding: 28px; }
    .nav {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 0 0 18px;
    }
    .nav-link {
      color: var(--text);
      text-decoration: none;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
      font-size: 0.92rem;
    }
    .nav-link.active { border-color: rgba(246, 183, 60, 0.45); color: var(--accent); }
    .card, .nested-card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
      backdrop-filter: blur(10px);
    }
    .nested-card { margin-top: 14px; background: var(--panel-alt); border-radius: 18px; }
    .grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
    .hero { display: grid; grid-template-columns: 2fr 1fr; gap: 18px; margin-bottom: 18px; }
    .brand { display: flex; align-items: center; gap: 16px; }
    .brand-logo {
      width: 96px;
      max-width: 100%;
      flex: 0 0 auto;
      filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.34));
    }
    .muted { color: var(--muted); }
    .pill {
      display: inline-block;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(246, 183, 60, 0.08);
      border: 1px solid rgba(246, 183, 60, 0.18);
      margin-right: 8px;
      margin-bottom: 8px;
      font-size: 0.82rem;
    }
    .button {
      display: inline-block;
      text-decoration: none;
      color: var(--text);
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border: 1px solid rgba(246, 183, 60, 0.28);
      border-radius: 14px;
      padding: 10px 14px;
      font-weight: 600;
      margin-right: 8px;
      margin-top: 8px;
    }
    .notice {
      padding: 14px 16px;
      border-radius: 16px;
      margin-bottom: 16px;
      border: 1px solid var(--line);
    }
    .success { background: rgba(57, 217, 138, 0.1); border-color: rgba(57, 217, 138, 0.32); }
    .error { background: rgba(255, 107, 107, 0.12); border-color: rgba(255, 107, 107, 0.32); }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      text-align: left;
      padding: 11px 0;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    th { color: var(--muted); }
    .scalar { padding: 2px 0; }
    .nested-title { margin-bottom: 10px; font-weight: 700; }
    .empty {
      padding: 16px;
      border-radius: 16px;
      background: rgba(17, 37, 59, 0.65);
      color: var(--muted);
    }
    input, select, textarea, button {
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--panel-alt);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
    }
    label { display: grid; gap: 6px; font-weight: 600; }
    form { display: grid; gap: 12px; }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border-color: rgba(246, 183, 60, 0.28);
      font-weight: 700;
    }
    .check-grid { display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
    .check-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--panel-alt);
    }
    .check-item input { width: auto; margin: 0; }
    @media (max-width: 960px) {
      .hero { grid-template-columns: 1fr; }
      .shell { padding: 18px; }
    }
    """


def _html_template(title: str, payload: dict[str, Any]) -> str:
    account = payload.get("account", {})
    execution = payload.get("execution_decision", {})
    ai_signal = payload.get("ai_signal", {})
    tracked = payload.get("tracked_symbols", [])
    tracked_html = "".join(
        f"<span class='pill'>{escape(str(item.get('symbol', '')))}</span>"
        for item in tracked if isinstance(item, dict) and item.get("symbol")
    ) or "<span class='pill'>No tracked symbols</span>"

    price_action = payload.get("price_action", [])
    pa_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('timeframe', '-')))}</td>"
        f"<td>{escape(str(item.get('bias', '-')))}</td>"
        f"<td>{escape(str(item.get('phase', '-')))}</td>"
        f"<td>{_format_scalar(item.get('momentum_score', 0.0))}</td>"
        "</tr>"
        for item in price_action if isinstance(item, dict)
    ) or "<tr><td colspan='4'>No price action data</td></tr>"

    ideas = payload.get("trade_ideas", [])
    idea_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('timeframe', '-')))}</td>"
        f"<td>{escape(str(item.get('direction', '-')))}</td>"
        f"<td>{_format_scalar(item.get('entry', ''))}</td>"
        f"<td>{_format_scalar(item.get('stop_loss', ''))}</td>"
        f"<td>{_format_scalar(item.get('take_profit', ''))}</td>"
        f"<td>{_format_scalar(item.get('score', 0.0))}</td>"
        "</tr>"
        for item in ideas if isinstance(item, dict)
    ) or "<tr><td colspan='6'>No trade ideas available</td></tr>"

    zones = payload.get("zones", [])
    zone_rows = "".join(
        "<tr>"
        f"<td>{escape(str(zone.get('timeframe', '-')))}</td>"
        f"<td>{escape(str(zone.get('kind', '-')))}</td>"
        f"<td>{escape(str(zone.get('family', '-')))}</td>"
        f"<td>{_format_scalar(zone.get('lower', ''))} - {_format_scalar(zone.get('upper', ''))}</td>"
        f"<td>{escape(str(zone.get('status', '-')))}</td>"
        "</tr>"
        for zone in zones if isinstance(zone, dict)
    ) or "<tr><td colspan='5'>No zones available</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation("/")}</nav>
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="./src/assets/Zones.png" alt="ZONES logo">
          <div>
            <h1 style="margin:0 0 8px;">ZONES</h1>
            <div class="muted">Live market structure, zones, execution filters, and AI signal view.</div>
          </div>
        </div>
        <div style="margin-top:14px;">
          <span class="pill">Symbol: {escape(str(payload.get("symbol", "-")))}</span>
          <span class="pill">Account: {escape(str(account.get("account_id", "-")))}</span>
          <span class="pill">Created: {escape(str(payload.get("created_at", "-")))}</span>
        </div>
        <div style="margin-top:8px;">{tracked_html}</div>
        <div style="margin-top:10px;">
          <a class="button" href="/chart">Open Chart</a>
          <a class="button" href="/system">Open System</a>
        </div>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">Execution Gate</h2>
        <div><strong>Allowed:</strong> {_format_scalar(execution.get("allowed", False))}</div>
        <div><strong>Direction:</strong> {escape(str(execution.get("direction", "-")))}</div>
        <div><strong>Timeframe:</strong> {escape(str(execution.get("timeframe", "-")))}</div>
        <div><strong>Score:</strong> {_format_scalar(execution.get("score", 0.0))}</div>
        <div style="margin-top:10px;" class="muted">{escape(str(execution.get("rationale", "")))}</div>
        <div style="margin-top:12px;"><strong>AI Signal:</strong> {escape(str(ai_signal.get("signal", "neutral")))}</div>
        <div class="muted">{escape(str(ai_signal.get("summary", "")))}</div>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2 style="margin-top:0;">Account</h2>
        <table><tbody>
          <tr><th>Balance</th><td>{_format_scalar(account.get("balance", 0.0))}</td></tr>
          <tr><th>Equity</th><td>{_format_scalar(account.get("equity", 0.0))}</td></tr>
          <tr><th>Free Margin</th><td>{_format_scalar(account.get("free_margin", 0.0))}</td></tr>
          <tr><th>Margin</th><td>{_format_scalar(account.get("margin", 0.0))}</td></tr>
          <tr><th>Daily PnL</th><td>{_format_scalar(account.get("daily_pnl", 0.0))}</td></tr>
          <tr><th>Open Positions</th><td>{_format_scalar(account.get("open_positions", 0))}</td></tr>
          <tr><th>Exposure %</th><td>{_format_scalar(account.get("risk_exposure_pct", 0.0))}</td></tr>
        </tbody></table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Timeframe Bias</h2>
        <table>
          <thead><tr><th>TF</th><th>Bias</th><th>Phase</th><th>Momentum</th></tr></thead>
          <tbody>{pa_rows}</tbody>
        </table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Trade Ideas</h2>
        <table>
          <thead><tr><th>TF</th><th>Dir</th><th>Entry</th><th>SL</th><th>TP</th><th>Score</th></tr></thead>
          <tbody>{idea_rows}</tbody>
        </table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Zones</h2>
        <table>
          <thead><tr><th>TF</th><th>Kind</th><th>Family</th><th>Range</th><th>Status</th></tr></thead>
          <tbody>{zone_rows}</tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>"""


def _chart_page_html(
        payload: dict[str, Any],
        *,
        timeframe: str,
        command_snapshot: dict[str, Any],
        tv_symbol_override: str = "",
        message: str = "",
        error: str = "",
) -> str:
    message_html = f"<div class='notice success'>{escape(message)}</div>" if message else ""
    error_html = f"<div class='notice error'>{escape(error)}</div>" if error else ""

    candles = payload.get("chart_data", {}).get(timeframe, [])
    candle_rows = "".join(
        "<tr>"
        f"<td>{escape(str(c.get('timestamp', '-')))}</td>"
        f"<td>{_format_scalar(c.get('open', ''))}</td>"
        f"<td>{_format_scalar(c.get('high', ''))}</td>"
        f"<td>{_format_scalar(c.get('low', ''))}</td>"
        f"<td>{_format_scalar(c.get('close', ''))}</td>"
        "</tr>"
        for c in candles[-30:] if isinstance(c, dict)
    ) or "<tr><td colspan='5'>No candle data</td></tr>"

    pending = command_snapshot.get("pending", [])
    pending_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('type', '-')))}</td>"
        f"<td>{escape(str(item.get('symbol', '-')))}</td>"
        f"<td>{escape(str(item.get('status', '-')))}</td>"
        f"<td>{escape(str(item.get('created_at', '-')))}</td>"
        "</tr>"
        for item in pending
    ) or "<tr><td colspan='4'>No pending commands</td></tr>"

    history = command_snapshot.get("history", [])
    history_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('type', '-')))}</td>"
        f"<td>{escape(str(item.get('symbol', '-')))}</td>"
        f"<td>{escape(str(item.get('status', '-')))}</td>"
        f"<td>{escape(str(item.get('message', '-')))}</td>"
        f"<td>{escape(str(item.get('recorded_at', '-')))}</td>"
        "</tr>"
        for item in history
    ) or "<tr><td colspan='5'>No command history</td></tr>"

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chart | ZONES</title>
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation("/chart")}</nav>
    {message_html}
    {error_html}

    <section class="hero">
      <div class="card">
        <h1 style="margin-top:0;">Chart</h1>
        <div class="muted">Selected timeframe: {escape(timeframe)}</div>
        <div style="margin-top:8px;">
          <span class="pill">Symbol: {escape(str(payload.get("symbol", "-")))}</span>
          <span class="pill">TV Symbol: {escape(tv_symbol_override or str(payload.get("symbol", "-")))}</span>
        </div>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">Queue Command</h2>
        <form method="post" action="/api/commands">
          <label>Account ID<input type="text" name="account_id" value="{escape(str(payload.get("account", {}).get("account_id", "")))}"></label>
          <label>Symbol<input type="text" name="symbol" value="{escape(str(payload.get("symbol", "")))}"></label>
          <label>Command Type
            <select name="command_type">
              <option value="alert">alert</option>
              <option value="market_buy">market_buy</option>
              <option value="market_sell">market_sell</option>
              <option value="buy_limit">buy_limit</option>
              <option value="sell_limit">sell_limit</option>
              <option value="buy_stop">buy_stop</option>
              <option value="sell_stop">sell_stop</option>
              <option value="close_ticket">close_ticket</option>
              <option value="delete_ticket">delete_ticket</option>
              <option value="modify_ticket">modify_ticket</option>
              <option value="close_all">close_all</option>
            </select>
          </label>
          <label>Lot<input type="text" name="lot"></label>
          <label>Price<input type="text" name="price"></label>
          <label>SL<input type="text" name="sl"></label>
          <label>TP<input type="text" name="tp"></label>
          <label>Ticket<input type="text" name="ticket"></label>
          <label>Filter Symbol<input type="text" name="filter_symbol"></label>
          <label>Comment<input type="text" name="comment"></label>
          <label>Message<textarea name="message" rows="3"></textarea></label>
          <button type="submit">Queue Command</button>
        </form>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2 style="margin-top:0;">Recent Candles</h2>
        <table>
          <thead><tr><th>Timestamp</th><th>Open</th><th>High</th><th>Low</th><th>Close</th></tr></thead>
          <tbody>{candle_rows}</tbody>
        </table>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Pending Commands</h2>
        <table>
          <thead><tr><th>Type</th><th>Symbol</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{pending_rows}</tbody>
        </table>
      </div>

      <div class="card" style="grid-column: 1 / -1;">
        <h2 style="margin-top:0;">Command History</h2>
        <table>
          <thead><tr><th>Type</th><th>Symbol</th><th>Status</th><th>Message</th><th>Recorded</th></tr></thead>
          <tbody>{history_rows}</tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>"""


def _system_page_html(status: dict[str, Any], message: str = "", error: str = "") -> str:
    database = status.get("database", {})
    runtime = status.get("runtime", {})
    signal_model = status.get("signal_model", {})
    live_signal = status.get("live_signal", {})
    diagnostics = status.get("diagnostics", {})

    message_html = f"<div class='notice success'>{escape(message)}</div>" if message else ""
    error_html = f"<div class='notice error'>{escape(error)}</div>" if error else ""

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>System | ZONES</title>
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation("/system")}</nav>
    {message_html}
    {error_html}

    <section class="hero">
      <div class="card">
        <h1 style="margin-top:0;">System Status</h1>
        <div class="muted">Database, runtime settings, signal model, and diagnostics.</div>
        <div style="margin-top:10px;">
          <span class="pill">DB: {escape(str(database.get("backend", "-")))}</span>
          <span class="pill">AI: {escape(str(signal_model.get("status", "warming_up")))}</span>
          <span class="pill">Signal: {escape(str(live_signal.get("signal", "neutral")))}</span>
          <span class="pill">Transport: {escape(str(diagnostics.get("transport", "-")))}</span>
        </div>
      </div>
      <div class="card">
        <table><tbody>
          <tr><th>Repository</th><td>{escape(str(database.get("masked_target", "-")))}</td></tr>
          <tr><th>Reports</th><td>{escape(str(database.get("report_count", 0)))}</td></tr>
          <tr><th>Feedback Rows</th><td>{escape(str(database.get("feedback_count", 0)))}</td></tr>
          <tr><th>Model Mode</th><td>{escape(str(signal_model.get("training_mode", "-")))}</td></tr>
          <tr><th>Model Samples</th><td>{escape(str(signal_model.get("sample_count", 0)))}</td></tr>
          <tr><th>Live Confidence</th><td>{escape(str(live_signal.get("confidence", 0.0)))}</td></tr>
        </tbody></table>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2 style="margin-top:0;">Runtime Settings</h2>
        <form method="post" action="/api/system/settings">
          <label>Database URL
            <input type="text" name="database_url" value="{escape(str(runtime.get('database_url', '')))}">
          </label>
          <div class="check-grid">
            <label class="check-item"><input type="checkbox" name="ai_enabled" {'checked' if runtime.get('ai_enabled') else ''}> AI enabled</label>
            <label class="check-item"><input type="checkbox" name="require_confirmation_signal" {'checked' if runtime.get('require_confirmation_signal') else ''}> Require confirmation</label>
            <label class="check-item"><input type="checkbox" name="require_htf_alignment" {'checked' if runtime.get('require_htf_alignment') else ''}> Require HTF alignment</label>
            <label class="check-item"><input type="checkbox" name="require_news_clearance" {'checked' if runtime.get('require_news_clearance') else ''}> Require news clearance</label>
            <label class="check-item"><input type="checkbox" name="require_liquidity_target" {'checked' if runtime.get('require_liquidity_target') else ''}> Require liquidity target</label>
          </div>
          <label>Minimum Trade Score<input type="number" step="0.1" name="minimum_trade_score" value="{escape(str(runtime.get('minimum_trade_score', 2.0)))}"></label>
          <label>Min Confluence Count<input type="number" step="1" name="min_confluence_count" value="{escape(str(runtime.get('min_confluence_count', 3)))}"></label>
          <label>ML Minimum Samples<input type="number" step="1" name="machine_learning_min_samples" value="{escape(str(runtime.get('machine_learning_min_samples', 20)))}"></label>
          <label>Temp Zone Min Thickness<input type="number" step="0.01" name="temp_zone_min_thickness" value="{escape(str(runtime.get('temp_zone_min_thickness', 0.18)))}"></label>
          <label>Temp Zone Max Thickness<input type="number" step="0.01" name="temp_zone_max_thickness" value="{escape(str(runtime.get('temp_zone_max_thickness', 0.95)))}"></label>
          <label>Main Zone Min Thickness<input type="number" step="0.01" name="main_zone_min_thickness" value="{escape(str(runtime.get('main_zone_min_thickness', 0.22)))}"></label>
          <label>Main Zone Max Thickness<input type="number" step="0.01" name="main_zone_max_thickness" value="{escape(str(runtime.get('main_zone_max_thickness', 1.35)))}"></label>
          <label>Entry Preference
            <select name="entry_preference">
              <option value="middle" {'selected' if runtime.get('entry_preference') == 'middle' else ''}>middle</option>
              <option value="furthest" {'selected' if runtime.get('entry_preference') == 'furthest' else ''}>furthest</option>
              <option value="closest" {'selected' if runtime.get('entry_preference') == 'closest' else ''}>closest</option>
            </select>
          </label>
          <label>Allowed Sessions<input type="text" name="allowed_sessions" value="{escape(str(runtime.get('allowed_sessions', '')))}"></label>
          <button type="submit">Save Runtime Settings</button>
        </form>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Train Signal Model</h2>
        <form method="post" action="/api/system/train">
          <label>Minimum Feedback Samples<input type="number" step="1" name="min_feedback_samples" value="3"></label>
          <button type="submit">Train Model</button>
        </form>

        <h2>Record Feedback</h2>
        <form method="post" action="/api/system/feedback">
          <label>Symbol<input type="text" name="symbol" value="EURUSD"></label>
          <label>Timeframe<input type="text" name="timeframe" value="5M"></label>
          <label>Setup Direction
            <select name="setup_direction">
              <option value="long">long</option>
              <option value="short">short</option>
            </select>
          </label>
          <label>Outcome
            <select name="outcome">
              <option value="win">win</option>
              <option value="loss">loss</option>
              <option value="breakeven">breakeven</option>
            </select>
          </label>
          <label>PnL<input type="number" step="0.01" name="pnl" value="0"></label>
          <label>Notes<textarea name="notes" rows="4"></textarea></label>
          <button type="submit">Save Feedback</button>
        </form>
      </div>

      <div class="card">
        <h2 style="margin-top:0;">Diagnostics</h2>
        {_render_value(diagnostics)}
      </div>
    </section>
  </div>
</body>
</html>"""


def _structured_route_html(
        *,
        title: str,
        subtitle: str,
        payload: dict[str, Any],
        current_path: str,
        json_href: str,
) -> str:
    summary_cards = []
    if "status" in payload:
        summary_cards.append(f"<div class='pill'>Status: {_format_scalar(payload['status'])}</div>")
    if "symbol" in payload:
        summary_cards.append(f"<div class='pill'>Symbol: {_format_scalar(payload['symbol'])}</div>")
    if "account_id" in payload:
        summary_cards.append(f"<div class='pill'>Account: {_format_scalar(payload['account_id'])}</div>")
    if "created_at" in payload:
        summary_cards.append(f"<div class='pill'>Updated: {_format_scalar(payload['created_at'])}</div>")

    rendered = _render_value(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} | ZONES</title>
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation(current_path)}</nav>
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/Zones.ico" alt="ZONES logo">
          <div>
            <h1 style="margin:0 0 8px;">{escape(title)}</h1>
            <div class="muted">{escape(subtitle)}</div>
          </div>
        </div>
        <div style="margin-top:14px;">{"".join(summary_cards) or "<span class='pill'>Structured browser view</span>"}</div>
      </div>
      <div class="card">
        <a class="button" href="/">Main Dashboard</a>
        <a class="button" href="{escape(json_href, quote=True)}">Raw JSON</a>
      </div>
    </section>
    <section class="card">
      {rendered}
    </section>
  </div>
</body>
</html>"""


# ============================================================
# Main server
# ============================================================

class DashboardServer:
    def __init__(
            self,
            config: EngineConfig | None = None,
            repository: LearningRepository | None = None,
            feed_service: LiveFeedService | None = None,
            diagnostics: dict[str, Any] | None = None,
            settings_store: RuntimeSettingsStore | None = None,
            signal_service: SignalModelService | None = None,
    ) -> None:
        self.logger=logging.getLogger("DashboardServer")
        self.config = config or EngineConfig()
        self.repository = repository or LearningRepository()
        self.feed_service = feed_service or LiveFeedService(self.config, self.repository)
        self.settings_store = settings_store or RuntimeSettingsStore()
        self.signal_service = signal_service or SignalModelService()
        self.diagnostics: dict[str, Any] = diagnostics or {
            "health": "ok",
            "ingest_requests": 0,
            "ingest_failures": 0,
            "last_ingest_at": "",
            "last_ingest_symbol": "",
            "last_error": "",
            "transport": "http+pipe+websocket",
            "last_transport": "",
        }
        self.runtime_settings: dict[str, Any] = {}
        self.runtime_settings = self._load_runtime_settings()

    # ============================================================
    # Runtime settings
    # ============================================================

    def _load_runtime_settings(self) -> dict[str, Any]:
        stored = self.settings_store.load()
        if not stored:
            return self._runtime_snapshot("")

        database_url = str(stored.get("database_url", "")).strip()
        config_updates = dict(stored.get("config", {})) if isinstance(stored.get("config"), dict) else {}

        try:
            self._apply_runtime_settings(
                database_url=database_url,
                config_updates=config_updates,
                persist=False,
            )
            return self._runtime_snapshot(database_url)
        except Exception as exc:
            self.diagnostics["last_error"] = f"Runtime settings load failed: {exc}"
            return self._runtime_snapshot(database_url)

    def _runtime_snapshot(self, database_url: str) -> dict[str, Any]:
        return {
            "database_url": database_url,
            "ai_enabled": getattr(self.config, "ai_enabled", True),
            "minimum_trade_score": getattr(self.config, "minimum_trade_score", 2.0),
            "min_confluence_count": getattr(self.config, "min_confluence_count", 3),
            "machine_learning_min_samples": getattr(self.config, "machine_learning_min_samples", 20),
            "require_confirmation_signal": getattr(self.config, "require_confirmation_signal", True),
            "require_htf_alignment": getattr(self.config, "require_htf_alignment", True),
            "require_news_clearance": getattr(self.config, "require_news_clearance", True),
            "require_liquidity_target": getattr(self.config, "require_liquidity_target", False),
            "temp_zone_min_thickness": getattr(self.config, "temp_zone_min_thickness", 0.18),
            "temp_zone_max_thickness": getattr(self.config, "temp_zone_max_thickness", 0.95),
            "main_zone_min_thickness": getattr(self.config, "main_zone_min_thickness", 0.22),
            "main_zone_max_thickness": getattr(self.config, "main_zone_max_thickness", 1.35),
            "entry_preference": getattr(self.config, "entry_preference", "middle"),
            "allowed_sessions": ",".join(
                getattr(self.config, "allowed_sessions", ("london", "new_york"))
            ),
        }

    def _apply_runtime_settings(
            self,
            *,
            database_url: str,
            config_updates: dict[str, Any],
            persist: bool,
    ) -> None:
        for key, value in config_updates.items():
            setattr(self.config, key, value)

        self.runtime_settings = self._runtime_snapshot(database_url)

        if persist:
            self.settings_store.save(
                {
                    "database_url": database_url,
                    "config": config_updates,
                }
            )

    # ============================================================
    # Status / payload builders
    # ============================================================

    def _system_status(
            self,
            account_id: str | None,
            symbol: str | None,
            payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = payload or self._build_payload(account_id, symbol)

        database = self.repository.connection_health()
        runtime = dict(self.runtime_settings)

        signal_model: dict[str, Any]
        if hasattr(self.signal_service, "status"):
            try:
                signal_model = dict(self.signal_service.status())
            except Exception as exc:
                signal_model = {"status": "error", "summary": str(exc)}
        elif hasattr(self.signal_service, "load_latest"):
            try:
                signal_model = dict(self.signal_service.load_latest())
            except Exception as exc:
                signal_model = {"status": "error", "summary": str(exc)}
        else:
            signal_model = {"status": "warming_up", "summary": "Signal service status unavailable"}

        live_signal = payload.get("ai_signal", {})

        if runtime.get("database_url"):
            database["masked_target"] = mask_database_url(runtime["database_url"])
        else:
            database["masked_target"] = mask_database_url(str(database.get("target", "")))

        return {
            "database": database,
            "runtime": runtime,
            "signal_model": signal_model,
            "live_signal": live_signal,
            "diagnostics": dict(self.diagnostics),
        }

    def _build_payload(
            self,
            account_id: str | None = None,
            symbol: str | None = None,
    ) -> dict[str, Any]:
        payload = self.feed_service.latest_report(account_id, symbol)
        if payload is None:
            payload = self.feed_service.waiting_payload(account_id, symbol)

        payload["alignment"] = payload.get("alignment") or {}
        payload["tracked_symbols"] = self.feed_service.tracked_symbols(account_id)

        if hasattr(self.signal_service, "score_report"):
            payload["ai_signal"] = self.signal_service.score_report(
                payload,
                self.config.to_dict() if hasattr(self.config, "to_dict") else self.config.__dict__,
            )
        else:
            payload["ai_signal"] = payload.get("ai_signal", {"signal": "neutral", "confidence": 0.0, "summary": ""})

        return payload

    # ============================================================
    # HTTP utilities
    # ============================================================

    def create_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                account_id = query.get("account_id", [None])[0]
                symbol = query.get("symbol", [None])[0]

                if parsed.path == "./src/assets/Zones.ico":
                    self._send_file(LOGO_PATH, "image/x-icon")
                    return

                if parsed.path == "/":
                    payload = server._build_payload(account_id, symbol)
                    self._send_html(_html_template("ZONES", payload))
                    return

                if parsed.path == "/chart":
                    timeframe = query.get("timeframe", ["5M"])[0]
                    tv_symbol_override = query.get("tv_symbol", [""])[0]
                    payload = server._build_payload(account_id, symbol)
                    command_snapshot = server.feed_service.command_snapshot(
                        payload.get("account", {}).get("account_id"),
                        payload.get("symbol"),
                    )
                    self._send_html(
                        _chart_page_html(
                            payload,
                            timeframe=timeframe,
                            command_snapshot=command_snapshot,
                            tv_symbol_override=tv_symbol_override,
                            message=query.get("message", [""])[0],
                            error=query.get("error", [""])[0],
                        )
                    )
                    return

                if parsed.path == "/system":
                    payload = server._build_payload(account_id, symbol)
                    status = server._system_status(account_id, symbol, payload)
                    self._send_html(
                        _system_page_html(
                            status,
                            message=query.get("message", [""])[0],
                            error=query.get("error", [""])[0],
                        )
                    )
                    return

                if parsed.path == "/api/analysis":
                    payload = server._build_payload(account_id, symbol)
                    self._send_route_payload(
                        title="Analysis View",
                        subtitle="Live structured analysis across market structure, zones, execution, and phase outputs.",
                        payload=payload,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/chart":
                    timeframe = query.get("timeframe", ["5M"])[0]
                    payload = server._build_payload(account_id, symbol)
                    chart_payload = {
                        "symbol": payload.get("symbol"),
                        "account_id": payload.get("account", {}).get("account_id"),
                        "timeframe": timeframe,
                        "candles": payload.get("chart_data", {}).get(timeframe, []),
                        "zones": [
                            zone for zone in payload.get("zones", [])
                            if zone.get("timeframe") == timeframe
                        ],
                        "ai_signal": payload.get("ai_signal", {}),
                        "execution_decision": payload.get("execution_decision", {}),
                    }
                    self._send_route_payload(
                        title="Chart Data",
                        subtitle="Candlestick and zone payload for the selected timeframe.",
                        payload=chart_payload,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/reports":
                    limit = coerce_int(query.get("limit", ["10"])[0], 10)
                    reports = server.repository.recent_reports(limit=limit)
                    self._send_route_payload(
                        title="Reports",
                        subtitle="Recent saved reports from the learning repository.",
                        payload={"items": reports, "limit": limit},
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/symbols":
                    items = server.feed_service.tracked_symbols(account_id)
                    self._send_route_payload(
                        title="Tracked Symbols",
                        subtitle="Symbols tracked by the live feed service.",
                        payload={"account_id": account_id, "items": items},
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/commands":
                    snapshot = server.feed_service.command_snapshot(account_id, symbol)
                    self._send_route_payload(
                        title="Command Queue",
                        subtitle="Pending commands and command execution history.",
                        payload=snapshot,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/health":
                    self._send_json(
                        {
                            "status": server.diagnostics.get("health", "unknown"),
                            "diagnostics": dict(server.diagnostics),
                        }
                    )
                    return

                if parsed.path == "/api/system/status":
                    payload = server._build_payload(account_id, symbol)
                    status = server._system_status(account_id, symbol, payload)
                    self._send_route_payload(
                        title="System Status",
                        subtitle="Runtime configuration, signal model state, diagnostics, and database health.",
                        payload=status,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/schema":
                    self._send_json(
                        {
                            "routes": {
                                "/": "Main dashboard",
                                "/chart": "Live chart and command panel",
                                "/system": "System status and runtime controls",
                                "/api/analysis": "Structured analysis payload",
                                "/api/chart": "Candlestick chart payload for one timeframe",
                                "/api/reports": "Recent stored reports",
                                "/api/symbols": "Tracked symbols",
                                "/api/commands": "Command queue snapshot",
                                "/api/health": "Diagnostics health payload",
                                "/api/system/status": "System status payload",
                                "/api/schema": "API schema",
                            }
                        }
                    )
                    return

                self.send_error(HTTPStatus.NOT_FOUND, "Route not found")

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                form = self._read_form()

                if parsed.path == "/api/system/settings":
                    try:
                        database_url = str(form.get("database_url", [""])[0]).strip()
                        config_updates = {
                            "ai_enabled": coerce_bool(form.get("ai_enabled", ["off"])[0], False),
                            "require_confirmation_signal": coerce_bool(form.get("require_confirmation_signal", ["off"])[0], False),
                            "require_htf_alignment": coerce_bool(form.get("require_htf_alignment", ["off"])[0], False),
                            "require_news_clearance": coerce_bool(form.get("require_news_clearance", ["off"])[0], False),
                            "require_liquidity_target": coerce_bool(form.get("require_liquidity_target", ["off"])[0], False),
                            "minimum_trade_score": coerce_float(form.get("minimum_trade_score", ["2.0"])[0], 2.0),
                            "min_confluence_count": coerce_int(form.get("min_confluence_count", ["3"])[0], 3),
                            "machine_learning_min_samples": coerce_int(form.get("machine_learning_min_samples", ["20"])[0], 20),
                            "temp_zone_min_thickness": coerce_float(form.get("temp_zone_min_thickness", ["0.18"])[0], 0.18),
                            "temp_zone_max_thickness": coerce_float(form.get("temp_zone_max_thickness", ["0.95"])[0], 0.95),
                            "main_zone_min_thickness": coerce_float(form.get("main_zone_min_thickness", ["0.22"])[0], 0.22),
                            "main_zone_max_thickness": coerce_float(form.get("main_zone_max_thickness", ["1.35"])[0], 1.35),
                            "entry_preference": str(form.get("entry_preference", ["middle"])[0]),
                            "allowed_sessions": _parse_allowed_sessions(
                                form.get("allowed_sessions", [""])[0],
                                ("london", "new_york"),
                            ),
                        }
                        server._apply_runtime_settings(
                            database_url=database_url,
                            config_updates=config_updates,
                            persist=True,
                        )
                        self._redirect("/system?message=Runtime+settings+saved")
                    except Exception as exc:
                        self._redirect(f"/system?error={urlencode({'e': str(exc)})[2:]}")
                    return

                if parsed.path == "/api/system/feedback":
                    try:
                        server.repository.record_feedback(
                            created_at="",
                            symbol=str(form.get("symbol", ["EURUSD"])[0]),
                            timeframe=str(form.get("timeframe", ["5M"])[0]),
                            setup_direction=str(form.get("setup_direction", ["long"])[0]),
                            outcome=str(form.get("outcome", ["win"])[0]),
                            pnl=coerce_float(form.get("pnl", ["0"])[0], 0.0),
                            notes=str(form.get("notes", [""])[0]),
                        )
                        self._redirect("/system?message=Feedback+saved")
                    except Exception as exc:
                        self._redirect(f"/system?error={urlencode({'e': str(exc)})[2:]}")
                    return

                if parsed.path == "/api/system/train":
                    try:
                        min_feedback_samples = coerce_int(form.get("min_feedback_samples", ["3"])[0], 3)
                        if hasattr(server.signal_service, "train_from_repository"):
                            server.signal_service.train_from_repository(
                                repository=server.repository,
                                min_feedback_samples=min_feedback_samples,
                            )
                        self._redirect("/system?message=Signal+model+trained")
                    except Exception as exc:
                        self._redirect(f"/system?error={urlencode({'e': str(exc)})[2:]}")
                    return

                if parsed.path == "/api/commands":
                    try:
                        account_id = str(form.get("account_id", [""])[0])
                        symbol = str(form.get("symbol", [""])[0])
                        command_type = str(form.get("command_type", ["alert"])[0])

                        params: dict[str, Any] = {}
                        for key in ("lot", "price", "sl", "tp", "ticket", "filter_symbol", "comment", "message"):
                            raw = str(form.get(key, [""])[0]).strip()
                            if raw != "":
                                params[key] = raw

                        server.feed_service.enqueue_command(
                            account_id=account_id,
                            symbol=symbol,
                            command_type=command_type,
                            params=params,
                        )
                        self._redirect("/chart?message=Command+queued")
                    except Exception as exc:
                        self._redirect(f"/chart?error={urlencode({'e': str(exc)})[2:]}")
                    return

                self.send_error(HTTPStatus.NOT_FOUND, "Route not found")

            def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)


            def _send_html(self, html: str, status: int = 200) -> None:
             body = html.encode("utf-8", errors="replace")
             try:
               self.send_response(status)
               self.send_header("Content-Type", "text/html; charset=utf-8")
               self.send_header("Content-Length", str(len(body)))
               self.send_header("Cache-Control", "no-cache")
               self.end_headers()
               self.wfile.write(body)
               self.wfile.flush()
             except Exception as exc:
                self.logger.warning("HTTP client disconnected before response completed: %s", exc)
            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.exists():
                    self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                    return
                data = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _redirect(self, location: str) -> None:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()

            def _read_form(self) -> dict[str, list[str]]:
                content_length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
                return parse_qs(raw)

            def _send_route_payload(
                    self,
                    *,
                    title: str,
                    subtitle: str,
                    payload: dict[str, Any],
                    parsed_path: str,
                    query: dict[str, list[str]],
            ) -> None:
                wants_json = str(query.get("format", ["html"])[0]).lower() == "json"
                if wants_json:
                    self._send_json(payload)
                    return

                query_copy = dict(query)
                query_copy["format"] = ["json"]
                flat_query = {key: values[-1] for key, values in query_copy.items() if values}
                json_href = parsed_path
                if flat_query:
                    json_href += "?" + urlencode(flat_query)

                html = _structured_route_html(
                    title=title,
                    subtitle=subtitle,
                    payload=payload,
                    current_path=parsed_path,
                    json_href=json_href,
                )
                self._send_html(html)

            def log_message(self, format: str, *args: Any) -> None:
                return

        return Handler

    # ============================================================
    # Server
    # ============================================================

    def serve(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        handler = self.create_handler()

        httpd = ThreadingHTTPServer((host, port), handler)
        httpd.daemon_threads = True
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()