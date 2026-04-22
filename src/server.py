from __future__ import annotations

import json
import os
import datetime
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse
from .portfolio import build_portfolio_analysis
from .bridge import LiveFeedService
from .config import EngineConfig
from .database import LearningRepository
from .system_state import (
    SignalModelService,
    RuntimeSettingsStore,
    coerce_bool,
    coerce_float,
    coerce_int,
    mask_database_url,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_asset(*candidates: str) -> Path:
  asset_dirs = (
    PROJECT_ROOT / "src" / "assets",
    PROJECT_ROOT / "assets",
    PROJECT_ROOT / "src" / "images",
    PROJECT_ROOT,
  )
  for asset_dir in asset_dirs:
    for candidate in candidates:
      candidate_path = asset_dir / candidate
      if candidate_path.exists():
        return candidate_path
  return asset_dirs[0] / candidates[0]


FAVICON_PATH = _resolve_asset("Zones.ico", "zones_ea.ico")
BRAND_LOGO_PATH = _resolve_asset("Zones.png", "zones_ea.png")


def _parse_allowed_sessions(value: Any, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        raw_items = [str(item).strip().lower() for item in value]
    else:
        raw_items = [part.strip().lower() for part in str(value or "").replace(";", ",").split(",")]
    sessions = [item for item in raw_items if item]
    if not sessions:
        return fallback
    # Preserve order while removing duplicates.
    return tuple(dict.fromkeys(sessions))


def _parse_chat_ids(value: Any) -> list[int]:
  if isinstance(value, list):
    items = value
  else:
    items = str(value or "").replace(";", ",").split(",")
  chat_ids: list[int] = []
  for item in items:
    text = str(item).strip()
    if not text:
      continue
    try:
      chat_ids.append(int(text))
    except ValueError:
      continue
  return chat_ids


def _html_template(title: str, payload: dict[str, Any]) -> str:
    execution = payload["execution_decision"]
    ingest = payload["metadata"].get("ingest", {"source": "waiting"})
    ai_signal = payload.get("ai_signal", {})
    execution_state = "ALLOWED" if execution["allowed"] else "BLOCKED"
    tracked_symbols = payload.get("tracked_symbols", [])
    phase_outputs = payload.get("phase_outputs", {})
    fib_setups = phase_outputs.get("phase_3", {}).get("fib_setups", [])
    imbalances = phase_outputs.get("phase_4", {}).get("imbalances", [])
    candlestick_patterns = phase_outputs.get("phase_5", {}).get("candlestick_patterns", [])
    news_plan = phase_outputs.get("phase_6", {})
    ml_state = phase_outputs.get("phase_2", {})
    tracked_symbols_html = "".join(
      f"<span class='pill'>{escape(str(item['symbol']))}</span>"
      for item in tracked_symbols
      if isinstance(item, dict) and item.get("symbol")
    ) or "<span class='pill'>No tracked symbols</span>"
    price_action_rows = "".join(
      f"<tr><td>{escape(str(item['timeframe']))}</td><td class='{ 'bull' if item['bias'] == 'bullish' else 'bear' if item['bias'] == 'bearish' else ''}'>{escape(str(item['bias']))}</td><td>{escape(str(item['phase']))}</td><td>{item['momentum_score']}</td></tr>"
      for item in payload["price_action"]
    ) or "<tr><td colspan='4'>No timeframe bias data</td></tr>"
    trade_idea_rows = "".join(
      f"<tr><td>{escape(str(idea['timeframe']))}</td><td>{escape(str(idea['direction']))}</td><td>{escape(str(idea.get('zone_label', '-') or '-'))}</td><td>{escape(str(idea.get('execution_style', '-')))}</td><td>{idea['entry']}</td><td>{idea['stop_loss']}</td><td>{idea['take_profit']}</td><td>{idea['score']}</td></tr>"
      for idea in payload["trade_ideas"]
    ) or "<tr><td colspan='8'>No trade ideas available</td></tr>"
    zone_rows = "".join(
      f"<tr><td>{escape(str(zone['timeframe']))}</td><td>{escape(str(zone['kind']))}</td><td>{escape(str(zone.get('family', '-')))}</td><td>{escape(str(zone.get('strength_label', zone['strength'])))}</td><td>{zone['lower']} - {zone['upper']}</td><td>{escape(str(zone.get('status', 'fresh')))}</td><td>{escape(str(zone.get('mode_bias', '-')))}</td></tr>"
      for zone in payload["zones"]
    ) or "<tr><td colspan='7'>No zones available</td></tr>"
    liquidity_rows = "".join(
      f"<tr><td>{escape(str(zone['timeframe']))}</td><td>{escape(str(zone['kind']))}</td><td>{zone['lower']} - {zone['upper']}</td></tr>"
      for zone in payload["liquidity_map"]
    ) or "<tr><td colspan='3'>No liquidity pools available</td></tr>"
    news_events_html = "".join(
      f"<span class='pill'>{escape(str(event['currency']))} {escape(str(event['impact']))} - {escape(str(event['title']))}</span>"
      for event in payload["news_filter"].get("upcoming_events", [])
    ) or "<span class='pill'>No upcoming events</span>"
    fib_rows = "".join(
      f"<tr><td>{escape(str(row['timeframe']))}</td><td>{escape(str(row['direction']))}</td><td>{escape(str(row['active_level']))}</td><td>{row['active_price']}</td><td>{row['confidence']}</td></tr>"
      for row in fib_setups
    ) or "<tr><td colspan='5'>No fib setup</td></tr>"
    imbalance_rows = "".join(
      f"<tr><td>{escape(str(row['timeframe']))}</td><td>{escape(str(row['kind']))}</td><td>{row['lower']} - {row['upper']}</td><td>{row['fill_score']}</td></tr>"
      for row in imbalances
    ) or "<tr><td colspan='4'>No imbalance</td></tr>"
    candle_rows = "".join(
      f"<tr><td>{escape(str(row['timeframe']))}</td><td>{escape(str(row['pattern']))}</td><td>{escape(str(row['direction']))}</td><td>{row['confidence']}</td></tr>"
      for row in candlestick_patterns
    ) or "<tr><td colspan='4'>No pattern</td></tr>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>
    :root {{
      --bg: #07111f;
      --panel: rgba(10, 24, 43, 0.92);
      --panel-alt: rgba(18, 38, 62, 0.9);
      --text: #e8f0f8;
      --muted: #8da4bd;
      --accent: #f6b73c;
      --bull: #39d98a;
      --bear: #ff6b6b;
      --line: rgba(141, 164, 189, 0.2);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(246, 183, 60, 0.14), transparent 24%),
        radial-gradient(circle at left center, rgba(57, 217, 138, 0.12), transparent 22%),
        linear-gradient(180deg, #08111e 0%, #0a1a2f 100%);
      min-height: 100vh;
    }}
    .shell {{
      max-width: 1280px;
      margin: 0 auto;
      padding: 28px;
    }}
    .hero {{
      display: grid;
      gap: 18px;
      grid-template-columns: 2fr 1fr 1fr;
      margin-bottom: 20px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 24px 64px rgba(0, 0, 0, 0.24);
      backdrop-filter: blur(10px);
    }}
    .hero h1 {{
      margin: 0 0 8px;
      font-size: 2rem;
      letter-spacing: 0.03em;
    }}
    .brand {{
      display: flex;
      align-items: flex-start;
      gap: 18px;
    }}
    .brand-logo {{
      width: 120px;
      max-width: 100%;
      flex: 0 0 auto;
      filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.34));
    }}
    .muted {{ color: var(--muted); }}
    .grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }}
    .pill {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: 0.78rem;
      background: var(--panel-alt);
      border: 1px solid var(--line);
      margin-right: 8px;
      margin-bottom: 8px;
    }}
    .bull {{ color: var(--bull); }}
    .bear {{ color: var(--bear); }}
    .allow {{ color: var(--bull); }}
    .block {{ color: var(--bear); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.93rem;
    }}
    th, td {{
      text-align: left;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); font-weight: 600; }}
    .section-title {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      gap: 12px;
    }}
    .callout {{
      padding: 14px;
      border-radius: 16px;
      background: rgba(246, 183, 60, 0.08);
      border: 1px solid rgba(246, 183, 60, 0.18);
    }}
    .action-link {{
      display: inline-block;
      margin-top: 12px;
      text-decoration: none;
      color: var(--text);
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border: 1px solid rgba(246, 183, 60, 0.28);
      border-radius: 14px;
      padding: 10px 14px;
      font-weight: 600;
    }}
    code {{
      white-space: pre-wrap;
      color: #cce7ff;
    }}
    ul {{
      margin: 8px 0 0;
      padding-left: 18px;
    }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .shell {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <div class="card">
        <div class="section-title">
          <div class="brand">
            <img class="brand-logo" src="/assets/zones-logo.png" alt="ZONES logo">
            <div>
              <h1>ZONES</h1>
              <div class="muted">SMC / ICT rulebook engine with live MT4 ingestion, DLL bridge support, execution filters, and AI hooks.</div>
            </div>
          </div>
          <div class="pill">{escape(str(payload["symbol"]))}</div>
        </div>
        <div class="callout">
          <strong>AI Summary:</strong> {escape(str(payload["ai_summary"]))}
        </div>
        <a class="action-link" href="/chart">Open Live Chart</a>
        <a class="action-link" href="/system" style="margin-left: 8px;">Open System Status</a>
        <div style="margin-top: 12px;">
          <span class="pill">Source: {escape(str(ingest.get("source", "demo")))}</span>
          <span class="pill">Account: {escape(str(payload["account"]["account_id"]))}</span>
          <span class="pill">Created: {escape(str(payload["created_at"] or "waiting"))}</span>
        </div>
        <div style="margin-top: 8px;">
          {tracked_symbols_html}
        </div>
      </div>
      <div class="card">
        <div class="section-title">
          <strong>Account</strong>
          <span class="muted">{escape(str(payload["account"]["status"]))}</span>
        </div>
        <div><strong>Balance:</strong> {payload["account"]["balance"]:.2f}</div>
        <div><strong>Equity:</strong> {payload["account"]["equity"]:.2f}</div>
        <div><strong>Free Margin:</strong> {payload["account"]["free_margin"]:.2f}</div>
        <div><strong>Margin:</strong> {payload["account"]["margin"]:.2f}</div>
        <div><strong>Daily PnL:</strong> {payload["account"]["daily_pnl"]:.2f}</div>
        <div><strong>Open Positions:</strong> {payload["account"]["open_positions"]}</div>
        <div><strong>Risk Exposure:</strong> {payload["account"]["risk_exposure_pct"]:.2f}%</div>
        <div><strong>Name:</strong> {escape(str(payload["account"]["name"] or "-"))}</div>
        <div><strong>Server:</strong> {escape(str(payload["account"]["server"] or "-"))}</div>
        <div><strong>Company:</strong> {escape(str(payload["account"]["company"] or "-"))}</div>
        <div><strong>Currency:</strong> {escape(str(payload["account"]["currency"] or "-"))}</div>
        <div><strong>Leverage:</strong> {escape(str(payload["account"]["leverage"] or "-"))}</div>
      </div>
      <div class="card">
        <div class="section-title">
          <strong>Execution Gate</strong>
          <span class="{'allow' if execution['allowed'] else 'block'}">{execution_state}</span>
        </div>
        <div><strong>Direction:</strong> {escape(str(execution["direction"]))}</div>
        <div><strong>Timeframe:</strong> {escape(str(execution["timeframe"]))}</div>
        <div><strong>Score:</strong> {execution["score"]}</div>
        <div><strong>AI Signal:</strong> {escape(str(ai_signal.get("signal", "neutral")))} ({ai_signal.get("confidence", 0.0)})</div>
        <div style="margin-top: 10px;" class="muted">{escape(str(execution["rationale"]))}</div>
        <div class="muted" style="margin-top: 10px;">{escape(str(ai_signal.get("summary", "")))}</div>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <div class="section-title">
          <strong>Timeframe Bias</strong>
          <span class="muted">1H / 5M / 1M</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Bias</th><th>Phase</th><th>Momentum</th></tr>
          </thead>
          <tbody>
            {price_action_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Trade Ideas</strong>
          <span class="muted">Zone respect + close confirmation</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Dir</th><th>Zone</th><th>Exec</th><th>Entry</th><th>SL</th><th>TP</th><th>Score</th></tr>
          </thead>
          <tbody>
            {trade_idea_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Private Rules</strong>
          <span class="muted">{len(execution["passed_checks"])} passed</span>
        </div>
        <div><strong>Passed</strong></div>
        <ul>{"".join(f"<li>{escape(str(item))}</li>" for item in execution["passed_checks"]) or "<li>None</li>"}</ul>
        <div style="margin-top: 12px;"><strong>Blocked By</strong></div>
        <ul>{"".join(f"<li>{escape(str(item))}</li>" for item in execution["blocked_reasons"]) or "<li>Nothing</li>"}</ul>
      </div>
    </section>

    <section class="grid" style="margin-top: 18px;">
      <div class="card">
        <div class="section-title">
          <strong>Zones</strong>
          <span class="muted">Supply, demand, support, resistance</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Type</th><th>Family</th><th>Strength</th><th>Range</th><th>Status</th><th>Mode</th></tr>
          </thead>
          <tbody>
            {zone_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Liquidity Map</strong>
          <span class="muted">Equal highs / lows</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Pool</th><th>Range</th></tr>
          </thead>
          <tbody>
            {liquidity_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>News Filter</strong>
          <span class="muted">{'Blocked' if payload['news_filter']['trading_blocked'] else 'Active'}</span>
        </div>
        <div>{escape(str(payload["news_filter"]["reason"]))}</div>
        <div style="margin-top: 10px;">
          {news_events_html}
        </div>
      </div>
    </section>

    <section class="grid" style="margin-top: 18px;">
      <div class="card">
        <div class="section-title">
          <strong>Bridge API</strong>
          <span class="muted">Live feed ready</span>
        </div>
        <div><strong>POST</strong> `/api/ingest`</div>
        <div><strong>GET</strong> `/api/analysis`</div>
        <div><strong>GET</strong> `/api/schema`</div>
        <div><strong>GET</strong> `/api/reports`</div>
      </div>
      <div class="card">
        <div class="section-title">
          <strong>Machine Learning Seed</strong>
          <span class="muted">Database-first</span>
        </div>
        <p class="muted">
          Every live MT4 run is stored in SQLite so later phases can learn from which BOS + retest + confirmation combinations actually perform.
        </p>
        <code>{json.dumps(payload["metadata"]["custom_inputs"], indent=2)}</code>
      </div>
    </section>

    <section class="grid" style="margin-top: 18px;">
      <div class="card">
        <div class="section-title">
          <strong>Phase 2</strong>
          <span class="muted">{ml_state.get('feature_row_count', 0)} feature rows</span>
        </div>
        <div><strong>Status:</strong> {escape(str(ml_state.get('status', 'Collecting')))}</div>
        <div><strong>Learning Ready:</strong> {ml_state.get('learning_ready', False)}</div>
        <div><strong>Covered Phases:</strong> {escape(", ".join(str(p) for p in ml_state.get('covered_phases', [])))}</div>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Phase 3 Fib</strong>
          <span class="muted">{len(fib_setups)} setups</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Dir</th><th>Level</th><th>Price</th><th>Conf</th></tr>
          </thead>
          <tbody>
            {fib_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Phase 4 FVG</strong>
          <span class="muted">{len(imbalances)} imbalances</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Type</th><th>Range</th><th>Fill</th></tr>
          </thead>
          <tbody>
            {imbalance_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="grid" style="margin-top: 18px;">
      <div class="card">
        <div class="section-title">
          <strong>Phase 5 Candles</strong>
          <span class="muted">{len(candlestick_patterns)} patterns</span>
        </div>
        <table>
          <thead>
            <tr><th>TF</th><th>Pattern</th><th>Dir</th><th>Conf</th></tr>
          </thead>
          <tbody>
            {candle_rows}
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-title">
          <strong>Phase 6 News EA</strong>
          <span class="muted">{escape(str(news_plan.get('strategy_mode', 'monitor')))}</span>
        </div>
        <div><strong>Execution TF:</strong> {escape(str(news_plan.get('execution_timeframe', '1M')))}</div>
        <div><strong>Buy Stop:</strong> {news_plan.get('breakout_levels', {}).get('buy_stop', '-')}</div>
        <div><strong>Sell Stop:</strong> {news_plan.get('breakout_levels', {}).get('sell_stop', '-')}</div>
        <div><strong>Grid Levels:</strong> {len(news_plan.get('grid_levels', []))}</div>
        <div style="margin-top: 10px;" class="muted">{escape(str(news_plan.get('summary', '')))}</div>
      </div>
    </section>
  </div>
  <div id="zones-refresh-bar" style="position:fixed;bottom:18px;right:22px;background:rgba(9,22,41,0.92);border:1px solid rgba(141,164,189,0.22);border-radius:999px;padding:8px 16px;font-size:0.82rem;color:#8da4bd;backdrop-filter:blur(8px);cursor:pointer;user-select:none;z-index:9999;" title="Click to refresh now" onclick="location.reload()">Refreshing in <span id="zones-countdown">15</span>s</div>
  <script>
  (function() {{
    var s = 15;
    var el = document.getElementById('zones-countdown');
    var id = setInterval(function() {{
      s--;
      if (el) el.textContent = s;
      if (s <= 0) {{ clearInterval(id); location.reload(); }}
    }}, 1000);
  }})();
  </script>
</body>
</html>"""


def _labelize(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").title()


def _format_scalar(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
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

        preview = value
        note = ""

        if all(_is_scalar(item) for item in preview):
            pills = "".join(f"<span class='pill'>{_format_scalar(item)}</span>" for item in preview)
            return note + f"<div>{pills}</div>"

        if all(isinstance(item, dict) for item in preview):
            columns: list[str] = []
            for item in preview:
                for key in item:
                    key_name = str(key)
                    if key_name not in columns:
                        columns.append(key_name)
            header = "".join(f"<th>{escape(_labelize(column))}</th>" for column in columns)
            rows = []
            for item in preview:
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
            return note + "<table><thead><tr>" + header + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"

        cards = []
        for index, item in enumerate(preview, start=1):
            cards.append(
                "<section class='nested-card'>"
                f"<div class='nested-title'>Item {index}</div>"
                f"{_render_value(item, level=level + 1)}"
                "</section>"
            )
        return note + "".join(cards)

    elif isinstance(value, dict):
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
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>
    :root {{
      --bg: #08111e;
      --panel: rgba(9, 22, 41, 0.94);
      --panel-alt: rgba(17, 37, 59, 0.92);
      --text: #e9f1f8;
      --muted: #8da4bd;
      --line: rgba(141, 164, 189, 0.18);
      --accent: #f6b73c;
      --accent-alt: #5fd1ff;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(246, 183, 60, 0.12), transparent 22%),
        radial-gradient(circle at left center, rgba(95, 209, 255, 0.12), transparent 24%),
        linear-gradient(180deg, #08111e 0%, #0b1930 100%);
      min-height: 100vh;
    }}
    .shell {{ max-width: 1320px; margin: 0 auto; padding: 28px; }}
    .hero {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .card, .nested-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
      backdrop-filter: blur(10px);
    }}
    .nested-card {{ margin-top: 14px; background: var(--panel-alt); border-radius: 18px; }}
    .nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 0 0 18px;
    }}
    .nav-link {{
      color: var(--text);
      text-decoration: none;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
      font-size: 0.92rem;
    }}
    .nav-link.active {{ border-color: rgba(246, 183, 60, 0.45); color: var(--accent); }}
    .hero h1 {{ margin: 0 0 8px; font-size: 2rem; }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .brand-logo {{
      width: 96px;
      max-width: 100%;
      flex: 0 0 auto;
      filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.34));
    }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-block;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(246, 183, 60, 0.08);
      border: 1px solid rgba(246, 183, 60, 0.18);
      margin-right: 8px;
      margin-bottom: 8px;
      font-size: 0.82rem;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      justify-content: flex-end;
      align-items: flex-start;
      flex-wrap: wrap;
    }}
    .button {{
      display: inline-block;
      text-decoration: none;
      color: var(--text);
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border: 1px solid rgba(246, 183, 60, 0.28);
      border-radius: 14px;
      padding: 10px 14px;
      font-weight: 600;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 11px 0;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); width: 28%; }}
    details summary {{ cursor: pointer; color: var(--accent-alt); }}
    .scalar {{ padding: 2px 0; }}
    .nested-title {{ margin-bottom: 10px; font-weight: 700; }}
    .route-note {{ margin-bottom: 10px; }}
    .content-card {{ margin-top: 18px; }}
    .empty {{
      padding: 16px;
      border-radius: 16px;
      background: rgba(17, 37, 59, 0.65);
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .shell {{ padding: 18px; }}
      .actions {{ justify-content: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation(current_path)}</nav>
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/zones-logo.png" alt="ZONES logo">
          <div>
            <h1>{escape(title)}</h1>
            <div class="muted">{escape(subtitle)}</div>
          </div>
        </div>
        <div style="margin-top: 14px;">{"".join(summary_cards) or "<span class='pill'>Structured browser view</span>"}</div>
      </div>
      <div class="card">
        <div class="actions">
          <a class="button" href="/">Main Dashboard</a>
          <a class="button" href="{escape(json_href, quote=True)}">Raw JSON</a>
        </div>
        <p class="muted" style="margin-top: 14px;">
          This route is rendered as an HTML browser view for readability. Add <code>format=json</code> to get the raw API response.
        </p>
      </div>
    </section>
    <section class="card content-card">
      {rendered}
    </section>
  </div>
  <div id="zones-refresh-bar" style="position:fixed;bottom:18px;right:22px;background:rgba(9,22,41,0.92);border:1px solid rgba(141,164,189,0.22);border-radius:999px;padding:8px 16px;font-size:0.82rem;color:#8da4bd;backdrop-filter:blur(8px);cursor:pointer;user-select:none;z-index:9999;" title="Click to refresh now" onclick="location.reload()">Refreshing in <span id="zones-countdown">15</span>s</div>
  <script>
  (function() {{
    var s = 15;
    var el = document.getElementById('zones-countdown');
    var id = setInterval(function() {{
      s--;
      if (el) el.textContent = s;
      if (s <= 0) {{ clearInterval(id); location.reload(); }}
    }}, 1000);
  }})();
  </script>
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
    _active_sess = {s.strip().lower() for s in str(runtime.get("allowed_sessions", "")).split(",") if s.strip()}
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>System Status | ZONES</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>
    :root {{
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
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(246, 183, 60, 0.12), transparent 22%),
        radial-gradient(circle at left center, rgba(95, 209, 255, 0.12), transparent 24%),
        linear-gradient(180deg, #08111e 0%, #0b1930 100%);
      min-height: 100vh;
    }}
    .shell {{ max-width: 1380px; margin: 0 auto; padding: 28px; }}
    .nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 18px; }}
    .nav a {{
      color: var(--text);
      text-decoration: none;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
    }}
    .hero {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      margin-bottom: 18px;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 18px;
    }}
    .brand-logo {{
      width: 120px;
      max-width: 100%;
      filter: drop-shadow(0 10px 22px rgba(0, 0, 0, 0.34));
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
      backdrop-filter: blur(10px);
    }}
    .grid {{
      display: grid;
      gap: 18px;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-block;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(246, 183, 60, 0.08);
      border: 1px solid rgba(246, 183, 60, 0.18);
      margin-right: 8px;
      margin-bottom: 8px;
      font-size: 0.82rem;
    }}
    .notice {{
      padding: 14px 16px;
      border-radius: 16px;
      margin-bottom: 16px;
      border: 1px solid var(--line);
    }}
    .success {{ background: rgba(57, 217, 138, 0.1); border-color: rgba(57, 217, 138, 0.32); }}
    .error {{ background: rgba(255, 107, 107, 0.12); border-color: rgba(255, 107, 107, 0.32); }}
    form {{ display: grid; gap: 12px; }}
    label {{ display: grid; gap: 6px; font-weight: 600; }}
    input, select, textarea, button {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--panel-alt);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
    }}
    button {{
      cursor: pointer;
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border-color: rgba(246, 183, 60, 0.28);
      font-weight: 700;
    }}
    .inline {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .check-grid {{
      display: grid;
      gap: 8px;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    }}
    .check-item {{
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--panel-alt);
    }}
    .check-item input {{
      width: auto;
      margin: 0;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); width: 36%; }}
    @media (max-width: 960px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .shell {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav class="nav">
      <a href="/">Dashboard</a>
      <a href="/system">System Status</a>
      <a href="/api/system/status?format=json">Raw JSON</a>
      <a href="/api/health">Health</a>
    </nav>
    {message_html}
    {error_html}
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/zones-logo.png" alt="ZONES logo">
          <div>
            <h1>System Status</h1>
            <div class="muted">Manage database connectivity, runtime filters, AI training, and live signal readiness from one page.</div>
          </div>
        </div>
        <div style="margin-top: 14px;">
          <span class="pill">DB: {escape(str(database.get('backend', '-')))}</span>
          <span class="pill">AI: {escape(str(signal_model.get('status', 'warming_up')))}</span>
          <span class="pill">Signal: {escape(str(live_signal.get('signal', 'neutral')))}</span>
          <span class="pill">Transport: {escape(str(diagnostics.get('transport', '-')))}</span>
        </div>
      </div>
      <div class="card">
        <table>
          <tbody>
            <tr><th>Repository</th><td>{escape(str(database.get('masked_target', '-')))}</td></tr>
            <tr><th>Reports</th><td>{escape(str(database.get('report_count', 0)))}</td></tr>
            <tr><th>Feedback Rows</th><td>{escape(str(database.get('feedback_count', 0)))}</td></tr>
            <tr><th>Model Mode</th><td>{escape(str(signal_model.get('training_mode', '-')))}</td></tr>
            <tr><th>Model Samples</th><td>{escape(str(signal_model.get('sample_count', 0)))}</td></tr>
            <tr><th>Live Confidence</th><td>{escape(str(live_signal.get('confidence', 0.0)))}</td></tr>
            <tr><th>Telegram</th><td>{'enabled' if runtime.get('telegram_enabled') else 'disabled'}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section class="grid">
      <div class="card">
        <h2>Database</h2>
        <table>
          <tbody>
            <tr><th>Status</th><td>{escape(str(database.get('status', '-')))}</td></tr>
            <tr><th>Backend</th><td>{escape(str(database.get('backend', '-')))}</td></tr>
            <tr><th>Target</th><td>{escape(str(database.get('masked_target', '-')))}</td></tr>
            <tr><th>Snapshots</th><td>{escape(str(database.get('snapshot_count', 0)))}</td></tr>
            <tr><th>Driver Error</th><td>{escape(str(database.get('error', '-')))}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <h2>AI Model</h2>
        <table>
          <tbody>
            <tr><th>Status</th><td>{escape(str(signal_model.get('status', '-')))}</td></tr>
            <tr><th>Mode</th><td>{escape(str(signal_model.get('training_mode', '-')))}</td></tr>
            <tr><th>Bias</th><td>{escape(str(signal_model.get('signal_bias', 'neutral')))}</td></tr>
            <tr><th>Trained At</th><td>{escape(str(signal_model.get('trained_at', '-')))}</td></tr>
            <tr><th>Summary</th><td>{escape(str(signal_model.get('summary', '-')))}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <h2>Live Signal</h2>
        <table>
          <tbody>
            <tr><th>Status</th><td>{escape(str(live_signal.get('status', '-')))}</td></tr>
            <tr><th>Signal</th><td>{escape(str(live_signal.get('signal', 'neutral')))}</td></tr>
            <tr><th>Confidence</th><td>{escape(str(live_signal.get('confidence', 0.0)))}</td></tr>
            <tr><th>Mode</th><td>{escape(str(live_signal.get('training_mode', '-')))}</td></tr>
            <tr><th>Summary</th><td>{escape(str(live_signal.get('summary', '-')))}</td></tr>
          </tbody>
        </table>
      </div>
    </section>
    <section class="grid" style="margin-top: 18px;">
      <div class="card">
        <h2>Runtime Settings</h2>
        <form method="post" action="/api/system/settings">
          <label>
            Remote Or Local Database URL
            <input type="text" name="database_url" value="{escape(str(runtime.get('database_url', '')))}" placeholder="sqlite:///C:/path/to/zones.db or postgresql://user:pass@host:5432/zones">
          </label>
          <div class="check-grid">
            <label class="check-item"><input type="checkbox" name="ai_enabled" {'checked' if runtime.get('ai_enabled') else ''}> AI enabled</label>
            <label class="check-item"><input type="checkbox" name="require_confirmation_signal" {'checked' if runtime.get('require_confirmation_signal') else ''}> Require confirmation</label>
            <label class="check-item"><input type="checkbox" name="require_htf_alignment" {'checked' if runtime.get('require_htf_alignment') else ''}> Require 1H alignment</label>
            <label class="check-item"><input type="checkbox" name="require_news_clearance" {'checked' if runtime.get('require_news_clearance') else ''}> Require news clearance</label>
            <label class="check-item"><input type="checkbox" name="require_liquidity_target" {'checked' if runtime.get('require_liquidity_target') else ''}> Require liquidity target</label>
          </div>
          <label>
            Minimum Trade Score
            <input type="number" step="0.1" name="minimum_trade_score" value="{escape(str(runtime.get('minimum_trade_score', 2.0)))}">
          </label>
          <label>
            Minimum Confluence Count
            <input type="number" step="1" name="min_confluence_count" value="{escape(str(runtime.get('min_confluence_count', 3)))}">
          </label>
          <label>
            Machine Learning Minimum Samples
            <input type="number" step="1" name="machine_learning_min_samples" value="{escape(str(runtime.get('machine_learning_min_samples', 20)))}">
          </label>
          <label>
            Temp Zone Min Thickness
            <input type="number" step="0.01" name="temp_zone_min_thickness" value="{escape(str(runtime.get('temp_zone_min_thickness', 0.18)))}">
          </label>
          <label>
            Temp Zone Max Thickness
            <input type="number" step="0.01" name="temp_zone_max_thickness" value="{escape(str(runtime.get('temp_zone_max_thickness', 0.95)))}">
          </label>
          <label>
            Main Zone Min Thickness
            <input type="number" step="0.01" name="main_zone_min_thickness" value="{escape(str(runtime.get('main_zone_min_thickness', 0.22)))}">
          </label>
          <label>
            Main Zone Max Thickness
            <input type="number" step="0.01" name="main_zone_max_thickness" value="{escape(str(runtime.get('main_zone_max_thickness', 1.35)))}">
          </label>
          <label>
            Entry Preference
            <select name="entry_preference">
              <option value="middle" {'selected' if runtime.get('entry_preference') == 'middle' else ''}>Middle</option>
              <option value="furthest" {'selected' if runtime.get('entry_preference') == 'furthest' else ''}>Furthest</option>
              <option value="closest" {'selected' if runtime.get('entry_preference') == 'closest' else ''}>Closest</option>
            </select>
          </label>
          <fieldset style="border:1px solid #444;border-radius:6px;padding:8px 12px;margin:4px 0;">
            <legend style="font-size:0.85em;padding:0 4px;">Allowed Sessions</legend>
            <label class="check-item"><input type="checkbox" name="allowed_sessions" value="sydney" {'checked' if 'sydney' in _active_sess else ''}> 🇦🇺 Sydney <small style="color:#888;">5 PM – 2 AM EST · AUD/NZD · lower volatility</small></label>
            <label class="check-item"><input type="checkbox" name="allowed_sessions" value="asia" {'checked' if 'asia' in _active_sess else ''}> 🇯🇵 Tokyo / Asia <small style="color:#888;">7 PM – 4 AM EST · JPY pairs · range-bound</small></label>
            <label class="check-item"><input type="checkbox" name="allowed_sessions" value="london" {'checked' if 'london' in _active_sess else ''}> 🇬🇧 London <small style="color:#888;">3 AM – 12 PM EST · EUR/GBP/USD · highest volume</small></label>
            <label class="check-item"><input type="checkbox" name="allowed_sessions" value="new_york" {'checked' if 'new_york' in _active_sess else ''}> 🇺🇸 New York <small style="color:#888;">8 AM – 5 PM EST · USD news · London overlap</small></label>
          </fieldset>
          <h3 style="margin: 6px 0 2px;">Telegram Bot</h3>
          <label class="check-item"><input type="checkbox" name="telegram_enabled" {'checked' if runtime.get('telegram_enabled') else ''}> Enable Telegram control and notifications</label>
          <label>
            Telegram Bot Token
            <input type="password" name="telegram_bot_token" value="{escape(str(runtime.get('telegram_bot_token', '')))}" placeholder="123456:ABCDEF...">
          </label>
          <label>
            Telegram Chat IDs
            <input type="text" name="telegram_chat_ids" value="{escape(str(runtime.get('telegram_chat_ids', '')))}" placeholder="123456789, 987654321">
          </label>
          <label>
            Telegram Poll Interval Seconds
            <input type="number" step="1" min="1" name="telegram_poll_interval_seconds" value="{escape(str(runtime.get('telegram_poll_interval_seconds', 2)))}">
          </label>
          <label>
            Telegram Default Account ID
            <input type="text" name="telegram_default_account_id" value="{escape(str(runtime.get('telegram_default_account_id', '')))}" placeholder="MT4 account id">
          </label>
          <label>
            Telegram Default Symbol
            <input type="text" name="telegram_default_symbol" value="{escape(str(runtime.get('telegram_default_symbol', '')))}" placeholder="EURUSD">
          </label>
          <label class="check-item"><input type="checkbox" name="telegram_notify_market_updates" {'checked' if runtime.get('telegram_notify_market_updates') else ''}> Notify new market updates automatically</label>
          <button type="submit">Save Runtime Settings</button>
        </form>
      </div>
      <div class="card">
        <h2>AI Training</h2>
        <p class="muted">Train the signal model from stored reports and any manually recorded trade feedback.</p>
        <form method="post" action="/api/system/train">
          <label>
            Minimum Feedback Samples
            <input type="number" step="1" name="min_feedback_samples" value="3">
          </label>
          <button type="submit">Train Signal Model</button>
        </form>
      </div>
      <div class="card">
        <h2>Record Feedback</h2>
        <form method="post" action="/api/system/feedback">
          <label>Symbol<input type="text" name="symbol" value="EURUSD"></label>
          <label>Timeframe<input type="text" name="timeframe" value="5M"></label>
          <label>Setup Direction
            <select name="setup_direction">
              <option value="long">Long</option>
              <option value="short">Short</option>
            </select>
          </label>
          <label>Outcome
            <select name="outcome">
              <option value="win">Win</option>
              <option value="loss">Loss</option>
              <option value="breakeven">Breakeven</option>
            </select>
          </label>
          <label>PnL<input type="number" step="0.01" name="pnl" value="0"></label>
          <label>Notes<textarea name="notes" rows="4" placeholder="Why this setup worked or failed"></textarea></label>
          <button type="submit">Save Feedback</button>
        </form>
      </div>
    </section>
  </div>
</body>
<footer style="text-align:center;padding:18px 0;color:var(--muted);font-size:0.82rem;">
  &copy; {escape(str(datetime.datetime.now().year))} ZONES. All rights reserved.
</html>"""


def _timeframe_sort_key(timeframe: str) -> tuple[int, str]:
    order = {"1M": 0, "5M": 1, "15M": 2, "1H": 3, "4H": 4, "1D": 5}
    return (order.get(timeframe, 99), timeframe)


def _zone_chart_style(zone: dict[str, Any]) -> tuple[str, str]:
    kind = str(zone.get("kind", ""))
    family = str(zone.get("family", ""))
    if kind == "demand":
        return ("rgba(57, 217, 138, 0.16)", "#39D98A" if family == "main" else "#66E2A3")
    if kind == "supply":
        return ("rgba(255, 107, 107, 0.16)", "#FF6B6B" if family == "main" else "#FF8A8A")
    if kind == "support":
        return ("rgba(95, 209, 255, 0.10)", "#5FD1FF")
    if kind == "resistance":
        return ("rgba(246, 183, 60, 0.10)", "#F6B73C")
    return ("rgba(255, 255, 255, 0.08)", "#C8D5E4")


def _candlestick_chart_svg(payload: dict[str, Any], timeframe: str) -> str:
    chart_data = payload.get("chart_data", {})
    candles = chart_data.get(timeframe, []) if isinstance(chart_data, dict) else []
    if not isinstance(candles, list) or not candles:
        return "<div class='empty'>No candle data is available for this timeframe yet.</div>"

    visible = candles[-60:]
    visible_start = len(candles) - len(visible)
    zones = [
        zone
        for zone in payload.get("zones", [])
        if zone.get("timeframe") == timeframe and zone.get("status") != "deleted"
    ]
    all_highs = [float(candle["high"]) for candle in visible]
    all_lows = [float(candle["low"]) for candle in visible]
    for zone in zones:
        all_highs.append(float(zone.get("upper", 0.0)))
        all_lows.append(float(zone.get("lower", 0.0)))

    max_price = max(all_highs)
    min_price = min(all_lows)
    padding = max((max_price - min_price) * 0.08, 0.0001)
    max_price += padding
    min_price -= padding

    width = 1100
    height = 500
    left = 68
    right = 18
    top = 22
    bottom = 44
    plot_width = width - left - right
    plot_height = height - top - bottom
    candle_gap = plot_width / max(len(visible), 1)
    body_width = max(4.0, candle_gap * 0.56)

    def y(price: float) -> float:
        return top + (max_price - price) / max(max_price - min_price, 1e-9) * plot_height

    grid_lines = []
    for step in range(6):
        price = max_price - (max_price - min_price) * step / 5.0
        y_pos = y(price)
        grid_lines.append(
            f"<line x1='{left}' y1='{y_pos:.2f}' x2='{width - right}' y2='{y_pos:.2f}' stroke='rgba(141, 164, 189, 0.14)' stroke-width='1' />"
            f"<text x='8' y='{y_pos + 4:.2f}' fill='#8DA4BD' font-size='11'>{price:.3f}</text>"
        )

    zone_markup = []
    for zone in zones:
        rect_left_index = max(0, int(zone.get("origin_index", 0)) - visible_start)
        rect_x = left + rect_left_index * candle_gap
        rect_width = max(12.0, plot_width - (rect_x - left))
        upper = float(zone.get("upper", 0.0))
        lower = float(zone.get("lower", 0.0))
        top_y = min(y(upper), y(lower))
        rect_height = max(4.0, abs(y(lower) - y(upper)))
        fill, stroke = _zone_chart_style(zone)
        label = f"{zone.get('family', '').upper()} {zone.get('kind', '').upper()} {zone.get('strength_label', '')}".strip()
        zone_markup.append(
            f"<rect x='{rect_x:.2f}' y='{top_y:.2f}' width='{rect_width:.2f}' height='{rect_height:.2f}' fill='{fill}' stroke='{stroke}' stroke-width='1.4' rx='8' />"
            f"<text x='{rect_x + 6:.2f}' y='{top_y + 15:.2f}' fill='{stroke}' font-size='11'>{escape(label)}</text>"
        )

    candle_markup = []
    label_interval = max(1, len(visible) // 6)
    for index, candle in enumerate(visible):
        open_price = float(candle["open"])
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])
        bullish = close_price >= open_price
        color = "#39D98A" if bullish else "#FF6B6B"
        center_x = left + index * candle_gap + candle_gap / 2.0
        body_top = min(y(open_price), y(close_price))
        body_height = max(2.0, abs(y(open_price) - y(close_price)))
        candle_markup.append(
            f"<line x1='{center_x:.2f}' y1='{y(high_price):.2f}' x2='{center_x:.2f}' y2='{y(low_price):.2f}' stroke='{color}' stroke-width='1.6' />"
            f"<rect x='{center_x - body_width / 2:.2f}' y='{body_top:.2f}' width='{body_width:.2f}' height='{body_height:.2f}' rx='4' fill='{color}' opacity='0.92' />"
        )
        if index % label_interval == 0:
            timestamp = str(candle.get("timestamp", ""))[11:16]
            candle_markup.append(
                f"<text x='{center_x - 16:.2f}' y='{height - 14:.2f}' fill='#8DA4BD' font-size='11'>{escape(timestamp)}</text>"
            )

    last_close = float(visible[-1]["close"])
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='Candlestick chart for {escape(timeframe)}'>"
        + "".join(grid_lines)
        + "".join(zone_markup)
        + "".join(candle_markup)
        + f"<line x1='{left}' y1='{y(last_close):.2f}' x2='{width - right}' y2='{y(last_close):.2f}' stroke='rgba(246, 183, 60, 0.65)' stroke-width='1' stroke-dasharray='6 5' />"
        + f"<text x='{width - right - 78:.2f}' y='{y(last_close) - 6:.2f}' fill='#F6B73C' font-size='11'>Last {last_close:.3f}</text>"
        + "</svg>"
    )


def _tradingview_symbol(symbol: str, override: str = "") -> str:
    candidate = (override or symbol or "").strip().upper()
    if not candidate:
        return "FX:EURUSD"
    if ":" in candidate:
        return candidate
    if len(candidate) == 6 and candidate.isalpha():
        return f"FX:{candidate}"
    if candidate in {"XAUUSD", "XAGUSD", "XPTUSD", "XPDUSD"}:
        return f"OANDA:{candidate}"
    return candidate


def _tradingview_interval(timeframe: str) -> str:
    mapping = {
        "1M": "1",
        "3M": "3",
        "5M": "5",
        "15M": "15",
        "30M": "30",
        "1H": "60",
        "4H": "240",
        "1D": "D",
    }
    return mapping.get(timeframe, "60")


def _tradingview_widget_html(
    *,
    symbol: str,
    timeframe: str,
    symbol_options: list[str],
    tv_symbol_override: str = "",
) -> tuple[str, str]:
    tv_symbol = _tradingview_symbol(symbol, tv_symbol_override)
    watchlist: list[str] = []
    seen: set[str] = set()
    for item in [symbol, *symbol_options]:
        mapped = _tradingview_symbol(str(item or ""))
        if mapped and mapped not in seen:
            seen.add(mapped)
            watchlist.append(mapped)
    if tv_symbol not in seen:
        watchlist.insert(0, tv_symbol)
    widget_config = {
        "autosize": True,
        "symbol": tv_symbol,
        "interval": _tradingview_interval(timeframe),
        "timezone": "exchange",
        "theme": "dark",
        "backgroundColor": "rgba(8, 17, 30, 1)",
        "style": "1",
        "locale": "en",
        "withdateranges": True,
        "hide_side_toolbar": False,
        "allow_symbol_change": True,
        "save_image": True,
        "details": True,
        "hotlist": True,
        "calendar": True,
        "studies": [
            "ROC@tv-basicstudies",
            "StochasticRSI@tv-basicstudies",
            "MASimple@tv-basicstudies",
        ],
        "watchlist": watchlist[:12],
        "show_popup_button": True,
        "popup_width": "1200",
        "popup_height": "760",
        "support_host": "https://www.tradingview.com",
    }
    html = f"""<div class="tradingview-widget-container chart-stage">
  <div class="tradingview-widget-container__widget"></div>
  <div class="tradingview-widget-copyright">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
      <span class="blue-text">Advanced chart by TradingView</span>
    </a>
  </div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
{json.dumps(widget_config, indent=2)}
  </script>
</div>"""
    return html, tv_symbol


def _command_table_rows(rows: list[dict[str, Any]], *, history: bool = False) -> str:
    if not rows:
        colspan = "5" if history else "4"
        return f"<tr><td colspan='{colspan}'>No items</td></tr>"
    html_rows = []
    for row in rows:
        if history:
            html_rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('type', '-')))}</td>"
                f"<td>{escape(str(row.get('symbol', '-')))}</td>"
                f"<td>{escape(str(row.get('status', '-')))}</td>"
                f"<td>{escape(str(row.get('message', '-')))}</td>"
                f"<td>{escape(str(row.get('recorded_at', '-')))}</td>"
                "</tr>"
            )
        else:
            html_rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('type', '-')))}</td>"
                f"<td>{escape(str(row.get('symbol', '-')))}</td>"
                f"<td>{escape(str(row.get('status', '-')))}</td>"
                f"<td>{escape(str(row.get('created_at', '-')))}</td>"
                "</tr>"
            )
    return "".join(html_rows)


def _preferred_trade_idea(payload: dict[str, Any], timeframe: str) -> dict[str, Any]:
    trade_ideas = payload.get("trade_ideas", [])
    if not isinstance(trade_ideas, list) or not trade_ideas:
        return {}
    directional = [
        idea for idea in trade_ideas
        if isinstance(idea, dict) and idea.get("timeframe") == timeframe and idea.get("direction") != "neutral"
    ]
    if directional:
        return directional[0]
    fallback_directional = [
        idea for idea in trade_ideas
        if isinstance(idea, dict) and idea.get("direction") != "neutral"
    ]
    if fallback_directional:
        return fallback_directional[0]
    return trade_ideas[0] if isinstance(trade_ideas[0], dict) else {}


def _chart_page_html(
    payload: dict[str, Any],
    *,
    timeframe: str,
    command_snapshot: dict[str, Any],
    tv_symbol_override: str = "",
    message: str = "",
    error: str = "",
) -> str:
    chart_data = payload.get("chart_data", {})
    available_timeframes = sorted(chart_data.keys(), key=_timeframe_sort_key) if isinstance(chart_data, dict) else []
    selected_timeframe = timeframe if timeframe in available_timeframes else (available_timeframes[0] if available_timeframes else "1H")
    account_id = str(payload.get("account", {}).get("account_id", ""))
    symbol = str(payload.get("symbol", ""))
    tracked_symbols = payload.get("tracked_symbols", [])
    symbol_options = sorted(
        {str(item.get("symbol", "")) for item in tracked_symbols if isinstance(item, dict) and item.get("symbol")}
        | ({symbol} if symbol else set())
    )
    preferred_idea = _preferred_trade_idea(payload, selected_timeframe)
    default_direction = str(preferred_idea.get("direction", "long"))
    default_command = "market_sell" if default_direction == "short" else "market_buy"
    default_entry = preferred_idea.get("entry", payload.get("execution_decision", {}).get("entry", ""))
    default_sl = preferred_idea.get("stop_loss", payload.get("execution_decision", {}).get("stop_loss", ""))
    default_tp = preferred_idea.get("take_profit", payload.get("execution_decision", {}).get("take_profit", ""))
    chart_svg = _candlestick_chart_svg(payload, selected_timeframe)
    tradingview_html, resolved_tv_symbol = _tradingview_widget_html(
        symbol=symbol,
        timeframe=selected_timeframe,
        symbol_options=symbol_options,
        tv_symbol_override=tv_symbol_override,
    )
    message_html = f"<div class='notice success'>{escape(message)}</div>" if message else ""
    error_html = f"<div class='notice error'>{escape(error)}</div>" if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chart | ZONES</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>
    :root {{
      --bg: #08111e;
      --panel: rgba(9, 22, 41, 0.95);
      --panel-alt: rgba(17, 37, 59, 0.92);
      --text: #e9f1f8;
      --muted: #8da4bd;
      --line: rgba(141, 164, 189, 0.18);
      --accent: #f6b73c;
      --success: #39d98a;
      --error: #ff6b6b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top right, rgba(246, 183, 60, 0.12), transparent 22%),
        radial-gradient(circle at left center, rgba(95, 209, 255, 0.12), transparent 24%),
        linear-gradient(180deg, #08111e 0%, #0b1930 100%);
      min-height: 100vh;
    }}
    .shell {{ max-width: 1460px; margin: 0 auto; padding: 28px; }}
    .nav {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 0 0 18px; }}
    .nav a {{
      color: var(--text);
      text-decoration: none;
      padding: 9px 14px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
    }}
    .hero, .grid {{
      display: grid;
      gap: 18px;
    }}
    .hero {{ grid-template-columns: 2fr 1fr; margin-bottom: 18px; }}
    .grid {{ grid-template-columns: minmax(0, 2fr) minmax(320px, 420px); }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 20px;
      box-shadow: 0 20px 48px rgba(0, 0, 0, 0.22);
      backdrop-filter: blur(10px);
    }}
    .brand {{ display: flex; align-items: center; gap: 18px; }}
    .brand-logo {{ width: 120px; max-width: 100%; filter: drop-shadow(0 10px 22px rgba(0,0,0,0.34)); }}
    .muted {{ color: var(--muted); }}
    .pill {{
      display: inline-block;
      padding: 7px 11px;
      border-radius: 999px;
      background: rgba(246, 183, 60, 0.08);
      border: 1px solid rgba(246, 183, 60, 0.18);
      margin-right: 8px;
      margin-bottom: 8px;
      font-size: 0.82rem;
    }}
    .notice {{
      padding: 14px 16px;
      border-radius: 16px;
      margin-bottom: 16px;
      border: 1px solid var(--line);
    }}
    .success {{ background: rgba(57, 217, 138, 0.1); border-color: rgba(57, 217, 138, 0.32); }}
    .error {{ background: rgba(255, 107, 107, 0.12); border-color: rgba(255, 107, 107, 0.32); }}
    .tf-links {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 14px; }}
    .tf-links a {{
      color: var(--text);
      text-decoration: none;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
    }}
    .tf-links a.active {{ color: var(--accent); border-color: rgba(246,183,60,0.36); }}
    .chart-stage {{
      background: linear-gradient(180deg, rgba(6, 14, 27, 0.78), rgba(10, 21, 40, 0.92));
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 12px;
      min-height: 720px;
      overflow: hidden;
    }}
    .tradingview-widget-container {{
      width: 100%;
      min-height: 720px;
    }}
    .tradingview-widget-container__widget {{
      width: 100%;
      height: 680px;
    }}
    .tradingview-widget-copyright {{
      margin-top: 8px;
      font-size: 0.78rem;
      color: var(--muted);
    }}
    .tradingview-widget-copyright a {{
      color: var(--accent);
      text-decoration: none;
    }}
    svg {{ width: 100%; min-width: 980px; height: auto; display: block; }}
    .projection {{
      margin-top: 18px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }}
    .projection .chart-stage {{
      min-height: auto;
      overflow-x: auto;
    }}
    .zone-list {{ display: grid; gap: 10px; margin-top: 14px; }}
    .zone-item {{
      border: 1px solid var(--line);
      background: var(--panel-alt);
      border-radius: 14px;
      padding: 12px 14px;
    }}
    .toolbar {{
      display: grid;
      gap: 14px;
      grid-template-columns: minmax(220px, 320px) minmax(220px, 1fr);
      margin-top: 14px;
    }}
    .toolbar form {{
      display: grid;
      gap: 10px;
      align-items: end;
    }}
    .toolbar button {{
      width: auto;
      min-width: 160px;
    }}
    form {{ display: grid; gap: 12px; }}
    label {{ display: grid; gap: 6px; font-weight: 600; }}
    input, select, textarea, button {{
      width: 100%;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: var(--panel-alt);
      color: var(--text);
      padding: 12px 14px;
      font: inherit;
    }}
    button {{
      cursor: pointer;
      background: linear-gradient(135deg, rgba(246, 183, 60, 0.2), rgba(95, 209, 255, 0.18));
      border-color: rgba(246, 183, 60, 0.28);
      font-weight: 700;
    }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{
      text-align: left;
      padding: 10px 0;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }}
    th {{ color: var(--muted); }}
    @media (max-width: 1100px) {{
      .hero, .grid {{ grid-template-columns: 1fr; }}
      .shell {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav class="nav">
      <a href="/">Dashboard</a>
      <a href="/chart">Chart</a>
      <a href="/system">System</a>
      <a href="/api/analysis">Analysis</a>
    </nav>
    {message_html}
    {error_html}
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/zones-logo.png" alt="ZONES logo">
          <div>
            <h1>Candlestick Chart</h1>
            <div class="muted">Live candles with ZONES overlays and direct MT4 browser command controls.</div>
          </div>
        </div>
        <div style="margin-top: 14px;">
          <span class="pill">Symbol: {escape(str(payload.get('symbol', '-')))}</span>
          <span class="pill">Account: {escape(str(payload.get('account', {}).get('account_id', '-')))}</span>
          <span class="pill">Execution: {escape(str(payload.get('execution_decision', {}).get('allowed', False)))}</span>
          <span class="pill">TradingView: {escape(resolved_tv_symbol)}</span>
        </div>
        <div class="toolbar">
          <form method="get" action="/chart">
            <input type="hidden" name="account_id" value="{escape(account_id)}">
            <input type="hidden" name="timeframe" value="{escape(selected_timeframe)}">
            <input type="hidden" name="tv_symbol" value="{escape(tv_symbol_override or resolved_tv_symbol)}">
            <label>Tracked Symbol
              <select name="symbol">
                {"".join(f"<option value='{escape(item, quote=True)}' {'selected' if item == symbol else ''}>{escape(item)}</option>" for item in symbol_options)}
              </select>
            </label>
            <button type="submit">Switch Chart Symbol</button>
          </form>
          <form method="get" action="/chart">
            <input type="hidden" name="account_id" value="{escape(account_id)}">
            <input type="hidden" name="timeframe" value="{escape(selected_timeframe)}">
            <label>TradingView Symbol
              <input type="text" name="tv_symbol" value="{escape(tv_symbol_override or resolved_tv_symbol)}" placeholder="FX:EURUSD or OANDA:XAUUSD">
            </label>
            <label>Custom Symbol
              <input type="text" name="symbol" value="{escape(symbol)}" placeholder="EURUSD">
            </label>
            <button type="submit">Load Custom Symbol</button>
          </form>
        </div>
        <div class="tf-links">
          {"".join(f"<a class='{'active' if tf == selected_timeframe else ''}' href='/chart?{urlencode({'account_id': account_id, 'symbol': symbol, 'timeframe': tf, 'tv_symbol': tv_symbol_override or resolved_tv_symbol})}'>{escape(tf)}</a>" for tf in available_timeframes)}
        </div>
      </div>
      <div class="card">
        <div><strong>AI Signal:</strong> {escape(str(payload.get('ai_signal', {}).get('signal', 'neutral')))}</div>
        <div><strong>Confidence:</strong> {escape(str(payload.get('ai_signal', {}).get('confidence', 0.0)))}</div>
        <div><strong>Summary:</strong> <span class="muted">{escape(str(payload.get('ai_signal', {}).get('summary', '')))}</span></div>
        <p class="muted" style="margin-top: 12px;">TradingView Advanced Chart is the main tool surface here. The ZONES projection below keeps the engine's exact zone rendering visible for comparison.</p>
      </div>
    </section>
    <section class="grid">
      <div class="card">
        {tradingview_html}
        <div class="projection">
          <h2>ZONES Projection</h2>
          <div class="muted" style="margin-bottom: 10px;">Internal engine rendering for exact ZONES zones and candle relationships on {escape(selected_timeframe)}.</div>
          <div class="chart-stage">{chart_svg}</div>
        </div>
        <div class="zone-list">
          {"".join(
            f"<div class='zone-item'><strong>{escape(str(zone.get('family', '')).upper())} {escape(str(zone.get('kind', '')).upper())} {escape(str(zone.get('strength_label', '')))}</strong><br><span class='muted'>{escape(str(zone.get('lower', '-')))} - {escape(str(zone.get('upper', '-')))} | Mode: {escape(str(zone.get('mode_bias', '-')))} | Status: {escape(str(zone.get('status', '-')))}</span></div>"
            for zone in payload.get('zones', []) if zone.get('timeframe') == selected_timeframe
          ) or "<div class='zone-item'>No zones available for this timeframe.</div>"}
        </div>
      </div>
      <div class="card">
        <h2>Queue MT4 Command</h2>
        <form method="post" action="/api/commands/browser">
          <input type="hidden" name="account_id" value="{escape(str(payload.get('account', {}).get('account_id', '')))}">
          <input type="hidden" name="symbol" value="{escape(str(payload.get('symbol', '')))}">
          <input type="hidden" name="timeframe" value="{escape(selected_timeframe)}">
          <input type="hidden" name="tv_symbol" value="{escape(tv_symbol_override or resolved_tv_symbol)}">
          <label>Command Type
            <select name="command_type">
              <option value="market_buy" {'selected' if default_command == 'market_buy' else ''}>Market Buy</option>
              <option value="market_sell" {'selected' if default_command == 'market_sell' else ''}>Market Sell</option>
              <option value="buy_limit">Buy Limit</option>
              <option value="sell_limit">Sell Limit</option>
              <option value="buy_stop">Buy Stop</option>
              <option value="sell_stop">Sell Stop</option>
              <option value="modify_ticket">Modify Ticket</option>
              <option value="close_ticket">Close Ticket</option>
              <option value="delete_ticket">Delete Ticket</option>
              <option value="close_all">Close All</option>
              <option value="alert">Alert</option>
            </select>
          </label>
          <label>Lot<input type="number" step="0.01" name="lot" value="0.10"></label>
          <label>Price<input type="number" step="0.00001" name="price" value="{escape(str(default_entry))}" placeholder="Auto-filled from setup, adjustable"></label>
          <label>Stop Loss<input type="number" step="0.00001" name="sl" value="{escape(str(default_sl))}"></label>
          <label>Take Profit<input type="number" step="0.00001" name="tp" value="{escape(str(default_tp))}"></label>
          <label>Ticket<input type="number" step="1" name="ticket" placeholder="For close, delete, or modify"></label>
          <label>Filter Symbol<input type="text" name="filter_symbol" value="{escape(str(payload.get('symbol', '')))}"></label>
          <label>Comment<input type="text" name="comment" value="ZONES browser command"></label>
          <label>Message<input type="text" name="message" placeholder="Used by alert"></label>
          <button type="submit">Send To MT4 Queue</button>
        </form>
        <p class="muted" style="margin-top: 10px;">Entry, stop loss, and take profit are auto-filled from the current ZONES setup when available, and you can adjust them before queuing the command.</p>
        <h2 style="margin-top: 20px;">Pending Commands</h2>
        <table>
          <thead><tr><th>Type</th><th>Symbol</th><th>Status</th><th>Created</th></tr></thead>
          <tbody>{_command_table_rows(command_snapshot.get("pending", []), history=False)}</tbody>
        </table>
        <h2 style="margin-top: 20px;">Execution History</h2>
        <table>
          <thead><tr><th>Type</th><th>Symbol</th><th>Status</th><th>Message</th><th>Recorded</th></tr></thead>
          <tbody>{_command_table_rows(command_snapshot.get("history", []), history=True)}</tbody>
        </table>
      </div>
    </section>
  </div>
</body>
</html>"""


class Server:
    def __init__(
        self,
        config: EngineConfig | None = None,
        repository: LearningRepository | None = None,
        feed_service: LiveFeedService | None = None,
        diagnostics: dict[str, Any] | None = None,
        settings_store: RuntimeSettingsStore | None = None,
        signal_service: SignalModelService | None = None,
    ) -> None:
        self.config = config or EngineConfig()
        self.repository = repository or LearningRepository(Path("logs/zones.sqlite"))
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
            "transport": "http+pipe",
        }
        self.runtime_settings = self._load_runtime_settings()

    def _load_runtime_settings(self) -> dict[str, Any]:
      stored = self.settings_store.load()
      if not stored:
        return self._runtime_snapshot("")
      database_url = str(stored.get("database_url", "")).strip()
      config_updates = dict(stored.get("config", {})) if isinstance(stored.get("config"), dict) else {}
      telegram_updates = dict(stored.get("telegram", {})) if isinstance(stored.get("telegram"), dict) else {}
      try:
        self._apply_runtime_settings(
          database_url=database_url,
          config_updates=config_updates,
          telegram_updates=telegram_updates,
          persist=False,
        )
        return self._runtime_snapshot(database_url)
      except Exception as exc:
        self.diagnostics["last_error"] = f"Runtime settings load failed: {exc}"
        return self._runtime_snapshot(database_url)

    def _runtime_snapshot(self, database_url: str) -> dict[str, Any]:
      return {
        "database_url": database_url,
        "ai_enabled": self.config.ai_enabled,
        "minimum_trade_score": self.config.minimum_trade_score,
        "min_confluence_count": self.config.min_confluence_count,
        "machine_learning_min_samples": self.config.machine_learning_min_samples,
        "entry_preference": self.config.entry_preference,
        "allowed_sessions": ", ".join(self.config.allowed_sessions),
        "temp_zone_min_thickness": self.config.temp_zone_min_thickness,
        "temp_zone_max_thickness": self.config.temp_zone_max_thickness,
        "main_zone_min_thickness": self.config.main_zone_min_thickness,
        "main_zone_max_thickness": self.config.main_zone_max_thickness,
        "require_confirmation_signal": self.config.require_confirmation_signal,
        "require_htf_alignment": self.config.require_htf_alignment,
        "require_news_clearance": self.config.require_news_clearance,
        "require_liquidity_target": self.config.require_liquidity_target,
        "telegram_enabled": bool(self.runtime_settings.get("telegram_enabled", False)) if hasattr(self, "runtime_settings") else False,
        "telegram_bot_token": str(self.runtime_settings.get("telegram_bot_token", "")) if hasattr(self, "runtime_settings") else "",
        "telegram_chat_ids": str(self.runtime_settings.get("telegram_chat_ids", "")) if hasattr(self, "runtime_settings") else "",
        "telegram_poll_interval_seconds": int(self.runtime_settings.get("telegram_poll_interval_seconds", 2)) if hasattr(self, "runtime_settings") else 2,
        "telegram_default_account_id": str(self.runtime_settings.get("telegram_default_account_id", self.config.account_id)) if hasattr(self, "runtime_settings") else self.config.account_id,
        "telegram_default_symbol": str(self.runtime_settings.get("telegram_default_symbol", self.config.symbol)) if hasattr(self, "runtime_settings") else self.config.symbol,
        "telegram_notify_market_updates": bool(self.runtime_settings.get("telegram_notify_market_updates", False)) if hasattr(self, "runtime_settings") else False,
      }

    def _apply_runtime_settings(
        self,
        *,
        database_url: str,
        config_updates: dict[str, Any],
      telegram_updates: dict[str, Any] | None = None,
        persist: bool = True,
    ) -> None:
        clean_database_url = database_url.strip()
        config_values = dict(self.config.to_dict())
        config_values.update(config_updates)
        config_values["allowed_sessions"] = _parse_allowed_sessions(
            config_values.get("allowed_sessions"),
            self.config.allowed_sessions,
        )
        for key in ("fibonacci_levels", "fib_extension_levels"):
            if isinstance(config_values.get(key), list):
                config_values[key] = tuple(config_values[key])
        temp_min = float(config_values.get("temp_zone_min_thickness", self.config.temp_zone_min_thickness))
        temp_max = float(config_values.get("temp_zone_max_thickness", self.config.temp_zone_max_thickness))
        main_min = float(config_values.get("main_zone_min_thickness", self.config.main_zone_min_thickness))
        main_max = float(config_values.get("main_zone_max_thickness", self.config.main_zone_max_thickness))
        if temp_min <= 0 or temp_max <= 0 or main_min <= 0 or main_max <= 0:
            raise ValueError("Zone thickness values must be greater than zero.")
        if temp_min > temp_max:
            raise ValueError("Temp zone min thickness cannot be greater than temp zone max thickness.")
        if main_min > main_max:
            raise ValueError("Main zone min thickness cannot be greater than main zone max thickness.")
        new_config = EngineConfig(**config_values)
        new_repository = LearningRepository(database_url=clean_database_url or None)
        self.config = new_config
        self.repository = new_repository
        self.feed_service.config = new_config
        self.feed_service.repository = new_repository
        self.runtime_settings = self._runtime_snapshot(clean_database_url)
        merged_telegram = dict(self.runtime_settings)
        merged_telegram.update({
          "telegram_enabled": False,
          "telegram_bot_token": "",
          "telegram_chat_ids": "",
          "telegram_poll_interval_seconds": 2,
          "telegram_default_account_id": new_config.account_id,
          "telegram_default_symbol": new_config.symbol,
          "telegram_notify_market_updates": False,
        })
        if telegram_updates:
            merged_telegram["telegram_enabled"] = coerce_bool(
                telegram_updates.get("enabled", telegram_updates.get("telegram_enabled", False))
            )
            merged_telegram["telegram_bot_token"] = str(
                telegram_updates.get("bot_token", telegram_updates.get("telegram_bot_token", ""))
            ).strip()
            chat_ids = _parse_chat_ids(
                telegram_updates.get("chat_ids", telegram_updates.get("telegram_chat_ids", ""))
            )
            merged_telegram["telegram_chat_ids"] = ", ".join(str(item) for item in chat_ids)
            merged_telegram["telegram_poll_interval_seconds"] = max(
                1,
                coerce_int(
                    telegram_updates.get(
                        "poll_interval_seconds",
                        telegram_updates.get("telegram_poll_interval_seconds", 2),
                    ),
                    2,
                ),
            )
            merged_telegram["telegram_default_account_id"] = str(
                telegram_updates.get(
                    "default_account_id",
                    telegram_updates.get("telegram_default_account_id", new_config.account_id),
                )
                or new_config.account_id
            )
            merged_telegram["telegram_default_symbol"] = str(
                telegram_updates.get(
                    "default_symbol",
                    telegram_updates.get("telegram_default_symbol", new_config.symbol),
                )
                or new_config.symbol
            )
            merged_telegram["telegram_notify_market_updates"] = coerce_bool(
                telegram_updates.get(
                    "notify_market_updates",
                    telegram_updates.get("telegram_notify_market_updates", False),
                )
            )
        self.runtime_settings = merged_telegram
        if persist:
            telegram_chat_ids = _parse_chat_ids(self.runtime_settings.get("telegram_chat_ids", ""))
            self.settings_store.save(
                {
                    "database_url": clean_database_url,
                    "config": {
                        "ai_enabled": new_config.ai_enabled,
                        "minimum_trade_score": new_config.minimum_trade_score,
                        "min_confluence_count": new_config.min_confluence_count,
                        "machine_learning_min_samples": new_config.machine_learning_min_samples,
                        "entry_preference": new_config.entry_preference,
                        "allowed_sessions": list(new_config.allowed_sessions),
                        "temp_zone_min_thickness": new_config.temp_zone_min_thickness,
                        "temp_zone_max_thickness": new_config.temp_zone_max_thickness,
                        "main_zone_min_thickness": new_config.main_zone_min_thickness,
                        "main_zone_max_thickness": new_config.main_zone_max_thickness,
                        "require_confirmation_signal": new_config.require_confirmation_signal,
                        "require_htf_alignment": new_config.require_htf_alignment,
                        "require_news_clearance": new_config.require_news_clearance,
                        "require_liquidity_target": new_config.require_liquidity_target,
                    },
                      "telegram": {
                        "enabled": bool(self.runtime_settings.get("telegram_enabled", False)),
                        "bot_token": str(self.runtime_settings.get("telegram_bot_token", "")),
                        "chat_ids": telegram_chat_ids,
                        "poll_interval_seconds": coerce_int(
                          self.runtime_settings.get("telegram_poll_interval_seconds", 2),
                          2,
                        ),
                        "default_account_id": str(
                          self.runtime_settings.get("telegram_default_account_id", new_config.account_id)
                        ),
                        "default_symbol": str(self.runtime_settings.get("telegram_default_symbol", new_config.symbol)),
                        "notify_market_updates": bool(self.runtime_settings.get("telegram_notify_market_updates", False)),
                      },
                }
            )

    def _train_signal_model(self, min_feedback_samples: int = 3) -> dict[str, Any]:
        return self.signal_service.train(self.repository, min_feedback_samples=min_feedback_samples)

    def _record_feedback(self, form: dict[str, str]) -> None:
        self.repository.record_feedback(
            created_at=form.get("created_at") or self.diagnostics.get("last_ingest_at") or "",
            symbol=form.get("symbol") or self.config.symbol,
            timeframe=form.get("timeframe") or "5M",
            setup_direction=form.get("setup_direction") or "long",
            outcome=form.get("outcome") or "win",
            pnl=coerce_float(form.get("pnl"), 0.0),
            notes=form.get("notes") or "",
        )

    def _system_status(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        report_payload = payload or self._build_payload(account_id, symbol)
        database = self.repository.connection_health()
        database["masked_target"] = mask_database_url(str(database.get("target", "")))
        signal_model = self.signal_service.load_model()
        if not signal_model:
            signal_model = self._train_signal_model()
        live_signal = self.signal_service.score_report(report_payload, self.config.to_dict())
        return {
            "database": database,
            "runtime": dict(self.runtime_settings),
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
        payload["ai_signal"] = self.signal_service.score_report(payload, self.config.to_dict())
        return payload

    def create_handler(self) -> type[BaseHTTPRequestHandler]:
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                account_id = query.get("account_id", [None])[0]
                symbol = query.get("symbol", [None])[0]

                if parsed.path in {"/favicon.ico", "/assets/favicon.ico"}:
                    self._send_file(FAVICON_PATH, "image/x-icon")
                    return

                if parsed.path in {"/assets/zones-logo.png", "/assets/Zones.png"}:
                    logo_content_type = "image/png" if BRAND_LOGO_PATH.suffix.lower() == ".png" else "image/x-icon"
                    self._send_file(BRAND_LOGO_PATH, logo_content_type)
                    return

                if parsed.path == "/":
                    payload = server._build_payload(account_id, symbol)
                    html = _html_template("ZONES", payload)
                    self._send_html(html)
                    return

                if parsed.path == "/chart":
                    timeframe = query.get("timeframe", ["5M"])[0]
                    tv_symbol_override = query.get("tv_symbol", [""])[0]
                    payload = server._build_payload(account_id, symbol)
                    command_snapshot = server.feed_service.command_snapshot(
                        payload.get("account", {}).get("account_id"),
                        payload.get("symbol"),
                    )
                    html = _chart_page_html(
                        payload,
                        timeframe=timeframe,
                        command_snapshot=command_snapshot,
                        tv_symbol_override=tv_symbol_override,
                        message=query.get("message", [""])[0],
                        error=query.get("error", [""])[0],
                    )
                    self._send_html(html)
                    return

                if parsed.path == "/system":
                    payload = server._build_payload(account_id, symbol)
                    status = server._system_status(account_id, symbol, payload)
                    html = _system_page_html(
                        status,
                        message=query.get("message", [""])[0],
                        error=query.get("error", [""])[0],
                    )
                    self._send_html(html)
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
                    limit = int(query.get("limit", ["5"])[0])
                    payload = {
                        "items": server.repository.recent_reports(limit=limit),
                        "limit": limit,
                    }
                    self._send_route_payload(
                        title="Stored Reports",
                        subtitle="Recent analysis runs saved to the learning repository.",
                        payload=payload,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/symbols":
                    payload = {
                        "items": server.feed_service.tracked_symbols(account_id),
                        "account_id": account_id or "all",
                    }
                    self._send_route_payload(
                        title="Tracked Symbols",
                        subtitle="Symbols currently being tracked in memory for the selected account.",
                        payload=payload,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/commands":
                    payload = server.feed_service.command_snapshot(account_id, symbol)
                    payload["account_id"] = account_id or "all"
                    payload["symbol"] = symbol or "all"
                    self._send_route_payload(
                        title="Command Queue",
                        subtitle="Pending MT4 commands and recorded execution results.",
                        payload=payload,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/health":
                    self._send_route_payload(
                        title="System Health",
                        subtitle="Live diagnostics for the dashboard, named pipe, and ingest activity.",
                        payload=server.diagnostics,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/schema":
                    self._send_route_payload(
                        title="Payload Schema",
                        subtitle="Sample MT4 ingest payload shape for live feed integration.",
                        payload=server.feed_service.sample_ingest_schema(),
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/system/status":
                    payload = server._build_payload(account_id, symbol)
                    status = server._system_status(account_id, symbol, payload)
                    self._send_route_payload(
                        title="System Status",
                        subtitle="Runtime settings, database health, AI training, and live signal state.",
                        payload=status,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                if parsed.path == "/api/portfolio":
                    payload = server._build_payload(account_id, symbol)
                    portfolio = build_portfolio_analysis(payload)
                    self._send_route_payload(
                        title="Portfolio Analysis",
                        subtitle="Exposure, floating PnL, concentration risk, and account structure.",
                        payload=portfolio,
                        parsed_path=parsed.path,
                        query=query,
                    )
                    return

                self.send_error(HTTPStatus.NOT_FOUND, "Not found")








            def do_POST(self) -> None:  # noqa: N802
                account_value=""
                parsed = urlparse(self.path)
                api_key = os.getenv("ZONES_API_KEY")
                if api_key and self.headers.get("X-Api-Key") != api_key:
                    self._send_json({"status": "error", "message": "Unauthorized"}, status=HTTPStatus.UNAUTHORIZED)
                    return
                if parsed.path == "/api/ingest":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        raw = self.rfile.read(length)
                        payload = json.loads(raw.decode("utf-8"))
                        result = server.feed_service.ingest_payload(payload)
                        server.diagnostics["ingest_requests"] += 1
                        server.diagnostics["last_ingest_at"] = result["report"]["created_at"]
                        server.diagnostics["last_ingest_symbol"] = result["symbol"]
                        server.diagnostics["last_error"] = ""
                    except ValueError as exc:
                        server.diagnostics["ingest_failures"] += 1
                        server.diagnostics["last_error"] = str(exc)
                        self._send_json({"status": "error", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                        return
                    self._send_json(result, status=HTTPStatus.CREATED)
                    return
                if parsed.path == "/api/commands":
                    try:
                        length = int(self.headers.get("Content-Length", "0"))
                        raw = self.rfile.read(length)
                        payload = json.loads(raw.decode("utf-8"))
                        command = server.feed_service.enqueue_command(
                            account_id=str(payload.get("account_id", "")),
                            symbol=str(payload.get("symbol", "")),
                            command_type=str(payload.get("command_type", "")),
                            params=dict(payload.get("params", {})),
                        )
                    except ValueError as exc:
                        self._send_json({"status": "error", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                        return
                    self._send_json({"status": "ok", "command": command}, status=HTTPStatus.CREATED)
                    return
                if parsed.path == "/api/commands/browser":
                    form = self._read_form()
                    try:
                        symbol_name = str(form.get("symbol") or server.config.symbol)
                        account_value = str(form.get("account_id") or server.config.account_id)
                        command_type = str(form.get("command_type") or "")
                        params: dict[str, Any] = {}
                        for key in ("lot", "price", "sl", "tp", "ticket", "filter_symbol", "comment", "message"):
                            value = str(form.get(key, "")).strip()
                            if value:
                                params[key] = value

                        if not command_type:
                            raise ValueError("Command type is required.")

                        if command_type in {"market_buy", "market_sell", "buy_limit", "sell_limit", "buy_stop", "sell_stop"}:
                            lot_value = float(params.get("lot", "0") or "0")
                            if lot_value <= 0:
                                raise ValueError("Lot must be greater than 0.")

                        if command_type in {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}:
                            price_value = float(params.get("price", "0") or "0")
                            if price_value <= 0:
                                raise ValueError("Price is required for pending orders.")

                        if command_type in {"modify_ticket", "close_ticket", "delete_ticket"}:
                            ticket_value = int(float(params.get("ticket", "0") or "0"))
                            if ticket_value <= 0:
                                raise ValueError("Ticket is required for ticket-based commands.")

                        if command_type == "alert" and not params.get("message"):
                            raise ValueError("Message is required for alert commands.")

                        server.feed_service.enqueue_command(
                            account_id=account_value,
                            symbol=symbol_name,
                            command_type=command_type,
                            params=params,
                        )
                    except Exception as exc:
                        redirect_query = urlencode(
                            {
                                "account_id": account_value,
                                "symbol": str(form.get("symbol", "")),
                                "timeframe": str(form.get("timeframe", "5M")),
                                "tv_symbol": str(form.get("tv_symbol", "")),
                                "error": str(exc),
                            }
                        )
                        self._redirect("/chart?" + redirect_query)
                        return
                    redirect_query = urlencode(
                        {
                            "account_id": account_value,
                            "symbol": symbol_name,
                            "timeframe": str(form.get("timeframe", "5M")),
                            "tv_symbol": str(form.get("tv_symbol", "")),
                            "message": "MT4 command queued",
                        }
                    )
                    self._redirect("/chart?" + redirect_query)
                    return
                if parsed.path == "/api/system/settings":
                    form = self._read_form()
                    try:
                        config_updates = {
                            "ai_enabled": coerce_bool(form.get("ai_enabled", "")),
                            "minimum_trade_score": coerce_float(
                                form.get("minimum_trade_score"),
                                server.config.minimum_trade_score,
                            ),
                            "min_confluence_count": coerce_int(
                                form.get("min_confluence_count"),
                                server.config.min_confluence_count,
                            ),
                            "machine_learning_min_samples": coerce_int(
                                form.get("machine_learning_min_samples"),
                                server.config.machine_learning_min_samples,
                            ),
                            "entry_preference": str(form.get("entry_preference") or server.config.entry_preference),
                            "allowed_sessions": (
                                form.get("allowed_sessions")
                                or list(server.config.allowed_sessions)
                            ),
                            "temp_zone_min_thickness": coerce_float(
                                form.get("temp_zone_min_thickness"),
                                server.config.temp_zone_min_thickness,
                            ),
                            "temp_zone_max_thickness": coerce_float(
                                form.get("temp_zone_max_thickness"),
                                server.config.temp_zone_max_thickness,
                            ),
                            "main_zone_min_thickness": coerce_float(
                                form.get("main_zone_min_thickness"),
                                server.config.main_zone_min_thickness,
                            ),
                            "main_zone_max_thickness": coerce_float(
                                form.get("main_zone_max_thickness"),
                                server.config.main_zone_max_thickness,
                            ),
                            "require_confirmation_signal": coerce_bool(form.get("require_confirmation_signal", "")),
                            "require_htf_alignment": coerce_bool(form.get("require_htf_alignment", "")),
                            "require_news_clearance": coerce_bool(form.get("require_news_clearance", "")),
                            "require_liquidity_target": coerce_bool(form.get("require_liquidity_target", "")),
                        }
                        server._apply_runtime_settings(
                            database_url=str(form.get("database_url", "")),
                            config_updates=config_updates,
                          telegram_updates={
                            "telegram_enabled": coerce_bool(form.get("telegram_enabled", "")),
                            "telegram_bot_token": str(form.get("telegram_bot_token", "")),
                            "telegram_chat_ids": str(form.get("telegram_chat_ids", "")),
                            "telegram_poll_interval_seconds": coerce_int(form.get("telegram_poll_interval_seconds"), 2),
                            "telegram_default_account_id": str(form.get("telegram_default_account_id", "")),
                            "telegram_default_symbol": str(form.get("telegram_default_symbol", "")),
                            "telegram_notify_market_updates": coerce_bool(form.get("telegram_notify_market_updates", "")),
                          },
                        )
                    except Exception as exc:
                        self._redirect("/system?" + urlencode({"error": str(exc)}))
                        return
                    self._redirect("/system?message=Runtime+settings+saved")
                    return
                if parsed.path == "/api/system/train":
                    form = self._read_form()
                    min_feedback_samples = coerce_int(form.get("min_feedback_samples"), 3)
                    server._train_signal_model(min_feedback_samples=min_feedback_samples)
                    self._redirect("/system?message=Signal+model+trained")
                    return
                if parsed.path == "/api/system/feedback":
                    form = self._read_form()
                    try:
                        server._record_feedback(form)
                    except Exception as exc:
                        self._redirect("/system?" + urlencode({"error": str(exc)}))
                        return
                    self._redirect("/system?message=Feedback+saved")
                    return
                self.send_error(HTTPStatus.NOT_FOUND, "Not found")

            def log_message(self, format: str, *args: object) -> None:
                return

            def _wants_html(self, query: dict[str, list[str]]) -> bool:
                fmt = query.get("format", [""])[0].lower()
                if fmt == "json":
                    return False
                if fmt == "html":
                    return True
                accept = self.headers.get("Accept", "").lower()
                return "text/html" in accept

            def _json_href(self, parsed_path: str, query: dict[str, list[str]]) -> str:
                flattened = {key: values[-1] for key, values in query.items() if values and key != "format"}
                flattened["format"] = "json"
                return parsed_path + "?" + urlencode(flattened)

            def _send_route_payload(
                self,
                *,
                title: str,
                subtitle: str,
                payload: dict[str, Any],
                parsed_path: str,
                query: dict[str, list[str]],
            ) -> None:
                if self._wants_html(query):
                    html = _structured_route_html(
                        title=title,
                        subtitle=subtitle,
                        payload=payload,
                        current_path=parsed_path,
                        json_href=self._json_href(parsed_path, query),
                    )
                    self._send_html(html)
                    return
                self._send_json(payload)

            def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
                body = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_html(self, html: str) -> None:
                body = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.exists():
                    self.send_error(HTTPStatus.NOT_FOUND, "Not found")
                    return
                body = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_form(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                parsed = parse_qs(raw, keep_blank_values=True)
                return {key: (values if len(values) > 1 else values[-1]) for key, values in parsed.items()}

            def _redirect(self, location: str) -> None:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()

        return Handler

    def serve(self, host: str = "127.0.0.1", port: int = 8787) -> None:
        httpd = ThreadingHTTPServer((host, port), self.create_handler())
        print(f"ZONES dashboard running at http://{host}:{port}")
        print("POST live MT4 terminal snapshots to /api/ingest and open / to monitor the account dashboard.")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()
