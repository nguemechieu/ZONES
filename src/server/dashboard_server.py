from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from logging import Logger
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote, parse_qs, urlencode, urlparse, urlsplit, urlunsplit

from src.db.repository.learning_repository import LearningRepository
from src.execution.system_state import (
    RuntimeSettingsStore,
    SignalModelService,
    coerce_bool,
    coerce_float,
    coerce_int,
    mask_database_url,
)
from src.execution.portfolio import build_portfolio_analysis
from src.server.bridge import LiveFeedService
from src.server.engine_config import EngineConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ASSET_DIR = PROJECT_ROOT / "src" / "assets"
FAVICON_PATH = ASSET_DIR / "Zones.ico"
BRAND_LOGO_PATH = ASSET_DIR / "Zones.png"
ASSET_ROUTES = {
    "/favicon.ico": (FAVICON_PATH, "image/x-icon"),
    "/assets/favicon.ico": (FAVICON_PATH, "image/x-icon"),
    "/assets/Zones.ico": (FAVICON_PATH, "image/x-icon"),
    "/assets/Zones.png": (BRAND_LOGO_PATH, "image/png"),
    "/assets/zones-logo.png": (BRAND_LOGO_PATH, "image/png"),
    "/src/assets/Zones.png": (BRAND_LOGO_PATH, "image/png"),
}


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
    return list(dict.fromkeys(chat_ids))


def _mask_secret(value: str, visible: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return f"{text[:visible]}{'*' * 8}"


def _compose_database_url(raw_url: str, username: str = "", password: str = "") -> str:
    url = str(raw_url or "").strip()
    user = str(username or "").strip()
    secret = str(password or "")
    if not url:
        return ""
    if not user and not secret:
        return url
    parsed = urlsplit(url)
    if not parsed.scheme or not parsed.netloc or parsed.scheme.startswith("sqlite"):
        return url
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    auth = ""
    if user:
        auth = quote(user, safe="")
        if secret:
            auth += ":" + quote(secret, safe="")
        auth += "@"
    return urlunsplit((parsed.scheme, f"{auth}{host}{port}", parsed.path, parsed.query, parsed.fragment))


def _discover_telegram_chat_ids(token: str) -> tuple[list[int], str]:
    clean_token = str(token or "").strip()
    if not clean_token:
        return [], "Telegram token is empty."
    url = f"https://api.telegram.org/bot{clean_token}/getUpdates"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return [], f"Telegram rejected the token or request: HTTP {exc.code}."
    except (urllib.error.URLError, TimeoutError) as exc:
        return [], f"Telegram discovery failed: {exc}."
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [], f"Telegram discovery failed: {exc}."

    if not payload.get("ok"):
        description = str(payload.get("description") or "Telegram returned an error.")
        return [], description

    chat_ids: list[int] = []
    for update in payload.get("result", []):
        if not isinstance(update, dict):
            continue
        for key in ("message", "edited_message", "channel_post", "my_chat_member"):
            event = update.get(key)
            if isinstance(event, dict):
                chat = event.get("chat")
                if isinstance(chat, dict) and chat.get("id") is not None:
                    try:
                        chat_ids.append(int(chat["id"]))
                    except (TypeError, ValueError):
                        pass

    unique_ids = list(dict.fromkeys(chat_ids))
    if unique_ids:
        return unique_ids, f"Discovered {len(unique_ids)} Telegram chat id(s)."
    return [], "No Telegram chat id found yet. Send a message to the bot, then save settings again."


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
        ("/portfolio", "Portfolio"),
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


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _timeframe_sort_key(timeframe: str) -> tuple[int, str]:
    order = {"1M": 0, "5M": 1, "15M": 2, "30M": 3, "1H": 4, "4H": 5, "1D": 6}
    return (order.get(str(timeframe).upper(), 99), str(timeframe))


def _chart_href(
        *,
        account_id: str,
        symbol: str,
        timeframe: str,
        tv_symbol: str = "",
) -> str:
    params = {
        "account_id": account_id,
        "symbol": symbol,
        "timeframe": timeframe,
    }
    if tv_symbol:
        params["tv_symbol"] = tv_symbol
    return "/chart?" + urlencode(params)


def _zone_chart_style(zone: dict[str, Any]) -> tuple[str, str]:
    kind = str(zone.get("kind", "")).lower()
    family = str(zone.get("family", "")).lower()
    if kind == "demand":
        return ("rgba(57, 217, 138, 0.16)", "#39d98a" if family == "main" else "#66e2a3")
    if kind == "supply":
        return ("rgba(255, 107, 107, 0.16)", "#ff6b6b" if family == "main" else "#ff8a8a")
    if kind == "support":
        return ("rgba(95, 209, 255, 0.12)", "#5fd1ff")
    if kind == "resistance":
        return ("rgba(246, 183, 60, 0.12)", "#f6b73c")
    return ("rgba(233, 241, 248, 0.08)", "#c8d5e4")


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
    return mapping.get(str(timeframe).upper(), "5")


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
    html = f"""<div class="tradingview-widget-container tradingview-stage">
  <div class="tradingview-widget-container__widget"></div>
  <div class="tradingview-widget-copyright">
    <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">Advanced chart by TradingView</a>
  </div>
  <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
{json.dumps(widget_config, indent=2)}
  </script>
</div>"""
    return html, tv_symbol


def _candlestick_terminal_svg(payload: dict[str, Any], timeframe: str) -> str:
    chart_data = payload.get("chart_data", {})
    candles = chart_data.get(timeframe, []) if isinstance(chart_data, dict) else []
    if not isinstance(candles, list) or not candles:
        return "<div class='empty'>No candle data is available for this timeframe yet.</div>"

    visible = [candle for candle in candles[-72:] if isinstance(candle, dict)]
    if not visible:
        return "<div class='empty'>No valid candle rows are available for this timeframe yet.</div>"

    visible_start = max(0, len(candles) - len(visible))
    zones = [
        zone
        for zone in payload.get("zones", [])
        if isinstance(zone, dict)
        and str(zone.get("timeframe", timeframe)).upper() == timeframe
        and str(zone.get("status", "")).lower() != "deleted"
    ]

    highs = [_to_float(candle.get("high"), _to_float(candle.get("close"), 0.0)) for candle in visible]
    lows = [_to_float(candle.get("low"), _to_float(candle.get("close"), 0.0)) for candle in visible]
    for zone in zones:
        highs.append(_to_float(zone.get("upper"), max(highs or [1.0])))
        lows.append(_to_float(zone.get("lower"), min(lows or [1.0])))

    max_price = max(highs or [1.0])
    min_price = min(lows or [0.0])
    price_range = max(max_price - min_price, 0.0001)
    padding = price_range * 0.08
    max_price += padding
    min_price -= padding

    width = 1180
    height = 540
    left = 74
    right = 24
    top = 24
    bottom = 48
    plot_width = width - left - right
    plot_height = height - top - bottom
    candle_gap = plot_width / max(len(visible), 1)
    body_width = max(4.0, min(16.0, candle_gap * 0.58))

    def y(price: float) -> float:
        return top + (max_price - price) / max(max_price - min_price, 1e-9) * plot_height

    grid_markup: list[str] = []
    for step in range(6):
        price = max_price - (max_price - min_price) * step / 5.0
        y_pos = y(price)
        grid_markup.append(
            f"<line x1='{left}' y1='{y_pos:.2f}' x2='{width - right}' y2='{y_pos:.2f}' "
            "stroke='rgba(141, 164, 189, 0.14)' stroke-width='1' />"
            f"<text x='10' y='{y_pos + 4:.2f}' fill='#8da4bd' font-size='12'>{price:.5f}</text>"
        )

    zone_markup: list[str] = []
    for zone in zones:
        origin_index = int(_to_float(zone.get("origin_index"), visible_start))
        rect_left_index = max(0, origin_index - visible_start)
        rect_x = left + rect_left_index * candle_gap
        rect_width = max(16.0, plot_width - (rect_x - left))
        upper = _to_float(zone.get("upper"), max_price)
        lower = _to_float(zone.get("lower"), min_price)
        top_y = min(y(upper), y(lower))
        rect_height = max(5.0, abs(y(lower) - y(upper)))
        fill, stroke = _zone_chart_style(zone)
        label = " ".join(
            item
            for item in (
                str(zone.get("family", "")).upper(),
                str(zone.get("kind", "")).upper(),
                str(zone.get("strength_label", "")),
            )
            if item
        )
        zone_markup.append(
            f"<rect x='{rect_x:.2f}' y='{top_y:.2f}' width='{rect_width:.2f}' "
            f"height='{rect_height:.2f}' fill='{fill}' stroke='{stroke}' stroke-width='1.4' rx='7' />"
            f"<text x='{rect_x + 8:.2f}' y='{top_y + 16:.2f}' fill='{stroke}' font-size='12'>"
            f"{escape(label)}</text>"
        )

    candle_markup: list[str] = []
    label_interval = max(1, len(visible) // 7)
    for index, candle in enumerate(visible):
        open_price = _to_float(candle.get("open"), _to_float(candle.get("close"), 0.0))
        high_price = _to_float(candle.get("high"), max(open_price, _to_float(candle.get("close"), open_price)))
        low_price = _to_float(candle.get("low"), min(open_price, _to_float(candle.get("close"), open_price)))
        close_price = _to_float(candle.get("close"), open_price)
        bullish = close_price >= open_price
        color = "#39d98a" if bullish else "#ff6b6b"
        center_x = left + index * candle_gap + candle_gap / 2.0
        body_top = min(y(open_price), y(close_price))
        body_height = max(2.0, abs(y(open_price) - y(close_price)))
        candle_markup.append(
            f"<line x1='{center_x:.2f}' y1='{y(high_price):.2f}' x2='{center_x:.2f}' "
            f"y2='{y(low_price):.2f}' stroke='{color}' stroke-width='1.6' />"
            f"<rect x='{center_x - body_width / 2:.2f}' y='{body_top:.2f}' "
            f"width='{body_width:.2f}' height='{body_height:.2f}' rx='3' fill='{color}' opacity='0.92' />"
        )
        if index % label_interval == 0:
            timestamp = str(candle.get("timestamp", ""))
            label = timestamp[11:16] if len(timestamp) >= 16 else timestamp[-5:]
            candle_markup.append(
                f"<text x='{center_x - 16:.2f}' y='{height - 16:.2f}' fill='#8da4bd' font-size='11'>"
                f"{escape(label)}</text>"
            )

    last_close = _to_float(visible[-1].get("close"), 0.0)
    return (
        f"<svg viewBox='0 0 {width} {height}' role='img' "
        f"aria-label='Candlestick terminal for {escape(str(payload.get('symbol', '')))} {escape(timeframe)}'>"
        f"<rect x='0' y='0' width='{width}' height='{height}' fill='rgba(6, 14, 27, 0.64)' rx='18' />"
        + "".join(grid_markup)
        + "".join(zone_markup)
        + "".join(candle_markup)
        + f"<line x1='{left}' y1='{y(last_close):.2f}' x2='{width - right}' y2='{y(last_close):.2f}' "
        "stroke='rgba(246, 183, 60, 0.7)' stroke-width='1' stroke-dasharray='6 5' />"
        f"<text x='{width - right - 104:.2f}' y='{y(last_close) - 7:.2f}' fill='#f6b73c' font-size='12'>"
        f"Last {last_close:.5f}</text>"
        "</svg>"
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
    .terminal-header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 14px;
    }
    .terminal-shell {
      background: linear-gradient(180deg, rgba(6, 14, 27, 0.78), rgba(10, 21, 40, 0.94));
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      overflow-x: auto;
    }
    .terminal-shell svg {
      display: block;
      width: 100%;
      min-width: 900px;
      height: auto;
    }
    .tradingview-stage {
      width: 100%;
      min-height: 640px;
      border: 1px solid var(--line);
      border-radius: 18px;
      overflow: hidden;
      background: rgba(6, 14, 27, 0.82);
    }
    .tradingview-widget-container__widget {
      width: 100%;
      height: 600px;
    }
    .tradingview-widget-copyright {
      padding: 8px 12px 10px;
      color: var(--muted);
      font-size: 0.78rem;
    }
    .tradingview-widget-copyright a {
      color: var(--accent);
      text-decoration: none;
    }
    .metrics-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .metric {
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
      background: var(--panel-alt);
    }
    .metric-value {
      font-size: 1.35rem;
      font-weight: 800;
      margin-top: 6px;
    }
    .chart-toolbar {
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      margin-top: 14px;
    }
    .timeframe-tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .timeframe-tabs a {
      color: var(--text);
      text-decoration: none;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(17, 37, 59, 0.9);
      border: 1px solid var(--line);
      font-size: 0.86rem;
    }
    .timeframe-tabs a.active {
      color: var(--accent);
      border-color: rgba(246, 183, 60, 0.46);
    }
    .zone-list {
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }
    .zone-item {
      border: 1px solid var(--line);
      background: var(--panel-alt);
      border-radius: 14px;
      padding: 12px 14px;
    }
    @media (max-width: 960px) {
      .hero { grid-template-columns: 1fr; }
      .shell { padding: 18px; }
      .terminal-header { display: block; }
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
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation("/")}</nav>
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/Zones.png" alt="ZONES logo">
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

    account_id = str(payload.get("account", {}).get("account_id", ""))
    current_symbol = str(payload.get("symbol", "")).upper()
    chart_data = payload.get("chart_data", {})
    available_timeframes = (
        sorted([str(item) for item in chart_data.keys()], key=_timeframe_sort_key)
        if isinstance(chart_data, dict)
        else []
    )
    selected_timeframe = (
        timeframe
        if timeframe in available_timeframes
        else (available_timeframes[0] if available_timeframes else "5M")
    )

    tracked_symbols = payload.get("tracked_symbols", [])
    symbol_options = sorted(
        {
            str(item.get("symbol", "")).upper()
            for item in tracked_symbols
            if isinstance(item, dict) and item.get("symbol")
        }
        | ({current_symbol} if current_symbol else set())
    )
    if not symbol_options:
        symbol_options = [current_symbol or "EURUSD"]

    symbol_options_html = "".join(
        f"<option value='{escape(item, quote=True)}' {'selected' if item == current_symbol else ''}>"
        f"{escape(item)}</option>"
        for item in symbol_options
    )
    timeframe_tabs = "".join(
        f"<a class='{'active' if item == selected_timeframe else ''}' "
        f"href='{escape(_chart_href(account_id=account_id, symbol=current_symbol, timeframe=item, tv_symbol=tv_symbol_override), quote=True)}'>"
        f"{escape(item)}</a>"
        for item in available_timeframes
    )
    if not timeframe_tabs:
        timeframe_tabs = "<span class='pill'>No timeframe feeds yet</span>"

    tradingview_html, resolved_tv_symbol = _tradingview_widget_html(
        symbol=current_symbol,
        timeframe=selected_timeframe,
        symbol_options=symbol_options,
        tv_symbol_override=tv_symbol_override,
    )
    terminal_svg = _candlestick_terminal_svg(payload, selected_timeframe)
    selected_zones = [
        zone
        for zone in payload.get("zones", [])
        if isinstance(zone, dict)
        and str(zone.get("timeframe", selected_timeframe)).upper() == selected_timeframe
        and str(zone.get("status", "")).lower() != "deleted"
    ]
    zone_items = "".join(
        "<div class='zone-item'>"
        f"<strong>{escape(str(zone.get('family', '')).upper())} "
        f"{escape(str(zone.get('kind', '')).upper())} "
        f"{escape(str(zone.get('strength_label', zone.get('strength', ''))))}</strong>"
        f"<div class='muted'>{_format_scalar(zone.get('lower'))} - {_format_scalar(zone.get('upper'))}</div>"
        f"<div class='muted'>Status: {escape(str(zone.get('status', '-')))} | "
        f"Mode: {escape(str(zone.get('mode_bias', '-')))} | "
        f"Origin: {escape(str(zone.get('origin_index', '-')))}</div>"
        "</div>"
        for zone in selected_zones
    ) or "<div class='zone-item'>No zones available for this timeframe.</div>"

    candles = chart_data.get(selected_timeframe, []) if isinstance(chart_data, dict) else []
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
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
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
        <div class="muted">Selected symbol and timeframe drive the candle terminal and ZONES overlay.</div>
        <div style="margin-top:8px;">
          <span class="pill">Symbol: {escape(current_symbol or "-")}</span>
          <span class="pill">Timeframe: {escape(selected_timeframe)}</span>
          <span class="pill">Zones: {len(selected_zones)}</span>
          <span class="pill">TV Symbol: {escape(resolved_tv_symbol)}</span>
        </div>
        <div class="chart-toolbar">
          <form method="get" action="/chart">
            <input type="hidden" name="account_id" value="{escape(account_id, quote=True)}">
            <input type="hidden" name="timeframe" value="{escape(selected_timeframe, quote=True)}">
            <input type="hidden" name="tv_symbol" value="{escape(tv_symbol_override, quote=True)}">
            <label>Tracked Symbol
              <select name="symbol">{symbol_options_html}</select>
            </label>
            <button type="submit">Load Symbol</button>
          </form>
          <form method="get" action="/chart">
            <input type="hidden" name="account_id" value="{escape(account_id, quote=True)}">
            <input type="hidden" name="timeframe" value="{escape(selected_timeframe, quote=True)}">
            <label>Custom Symbol<input type="text" name="symbol" value="{escape(current_symbol, quote=True)}" placeholder="EURUSD"></label>
            <label>TradingView Symbol<input type="text" name="tv_symbol" value="{escape(tv_symbol_override or current_symbol, quote=True)}" placeholder="FX:EURUSD"></label>
            <button type="submit">Open Custom Chart</button>
          </form>
        </div>
        <div class="timeframe-tabs">{timeframe_tabs}</div>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">Queue Command</h2>
        <form method="post" action="/api/commands">
          <input type="hidden" name="account_id" value="{escape(account_id, quote=True)}">
          <input type="hidden" name="symbol" value="{escape(current_symbol, quote=True)}">
          <input type="hidden" name="timeframe" value="{escape(selected_timeframe, quote=True)}">
          <input type="hidden" name="tv_symbol" value="{escape(tv_symbol_override, quote=True)}">
          <label>Account ID<input type="text" value="{escape(account_id)}" disabled></label>
          <label>Symbol<input type="text" value="{escape(current_symbol)}" disabled></label>
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

    <section class="card" style="margin-bottom:18px;">
      <div class="terminal-header">
        <div>
          <h2 style="margin:0 0 6px;">TradingView Market Chart</h2>
          <div class="muted">External TradingView chart for the selected symbol, with public drawing tools and studies.</div>
        </div>
        <span class="pill">{escape(resolved_tv_symbol)}</span>
      </div>
      {tradingview_html}
    </section>

    <section class="card" style="margin-bottom:18px;">
      <div class="terminal-header">
        <div>
          <h2 style="margin:0 0 6px;">ZONES Candle Terminal</h2>
          <div class="muted">Candles and overlays come from the selected symbol payload served by the local ZONES engine.</div>
        </div>
        <div>
          <span class="pill">Demand</span>
          <span class="pill">Supply</span>
          <span class="pill">Support</span>
          <span class="pill">Resistance</span>
        </div>
      </div>
      <div class="terminal-shell">{terminal_svg}</div>
      <div class="zone-list">{zone_items}</div>
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
    tracked_symbols = status.get("tracked_symbols", [])
    symbol_options = sorted(
        {
            str(item.get("symbol", "")).upper()
            for item in tracked_symbols
            if isinstance(item, dict) and item.get("symbol")
        }
        | {str(runtime.get("chart_symbol", "EURUSD")).upper()}
    )
    symbol_options_html = "".join(
        f"<option value='{escape(item, quote=True)}' {'selected' if item == str(runtime.get('chart_symbol', '')).upper() else ''}>"
        f"{escape(item)}</option>"
        for item in symbol_options
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>System | ZONES</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
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
          <span class="pill">Telegram: {escape(str(runtime.get("telegram_status", "not configured")))}</span>
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
          <tr><th>Telegram Chats</th><td>{escape(str(runtime.get("telegram_chat_ids", "")) or "-")}</td></tr>
        </tbody></table>
      </div>
    </section>

    <section class="grid">
      <div class="card">
        <h2 style="margin-top:0;">Runtime Settings</h2>
        <form method="post" action="/api/system/settings">
          <h3 style="margin:0;">Database</h3>
          <label>Database URL or Host
            <input type="text" name="database_url" value="{escape(str(runtime.get('database_url_input', runtime.get('database_url', ''))), quote=True)}" placeholder="sqlite:///data/zones.db or postgresql://host:5432/zones">
          </label>
          <label>Database Username
            <input type="text" name="database_username" value="{escape(str(runtime.get('database_username', '')), quote=True)}">
          </label>
          <label>Database Password
            <input type="password" name="database_password" value="" placeholder="Leave blank to keep current password">
          </label>
          <div class="muted">Stored password: {escape(_mask_secret(str(runtime.get('database_password', ''))) or 'not set')}</div>
          <div class="muted">Current target: {escape(str(runtime.get('database_masked_url') or database.get('masked_target', '-')))}</div>

          <h3>Telegram</h3>
          <label class="check-item"><input type="checkbox" name="telegram_enabled" {'checked' if runtime.get('telegram_enabled') else ''}> Enable Telegram notifications</label>
          <label>Telegram Bot Token
            <input type="password" name="telegram_bot_token" value="" placeholder="Leave blank to keep current token">
          </label>
          <div class="muted">Stored token: {escape(_mask_secret(str(runtime.get('telegram_bot_token', ''))) or 'not set')}</div>
          <label>Telegram Chat IDs
            <input type="text" name="telegram_chat_ids" value="{escape(str(runtime.get('telegram_chat_ids', '')), quote=True)}" placeholder="Auto-discovered after user messages bot">
          </label>
          <div class="muted">{escape(str(runtime.get('telegram_status', 'Send a message to the bot, then save settings to discover chat id.')))}</div>

          <h3>Chart Symbol</h3>
          <label>Default Chart Symbol
            <select name="chart_symbol">{symbol_options_html}</select>
          </label>
          <label>Custom Chart Symbol
            <input type="text" name="chart_symbol_custom" value="" placeholder="EURUSD, GBPUSD, XAUUSD">
          </label>

          <h3>Execution Filters</h3>
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
        <div style="margin-top:12px;">
          <a class="button" href="/chart?symbol={escape(str(runtime.get('chart_symbol', 'EURUSD')), quote=True)}">Open Selected Symbol Chart</a>
        </div>
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


def _portfolio_page_html(portfolio: dict[str, Any]) -> str:
    fund = portfolio.get("fund_summary", {}) if isinstance(portfolio, dict) else {}
    risk = portfolio.get("risk_metrics", {}) if isinstance(portfolio, dict) else {}
    pnl = portfolio.get("pnl_attribution", {}) if isinstance(portfolio, dict) else {}
    exposure = portfolio.get("exposure_by_symbol", []) if isinstance(portfolio, dict) else []
    notes = portfolio.get("risk_notes", []) if isinstance(portfolio, dict) else []
    metrics = [
        ("NAV", fund.get("nav", portfolio.get("equity", 0.0))),
        ("Daily Return %", fund.get("daily_return_pct", 0.0)),
        ("Gross Lots", risk.get("gross_exposure_lots", portfolio.get("total_lots", 0.0))),
        ("Net Lots", risk.get("net_exposure_lots", 0.0)),
        ("Leverage Proxy", risk.get("leverage_proxy", 0.0)),
        ("Margin Level %", risk.get("margin_level_pct", portfolio.get("margin_level_pct", 0.0))),
        ("Concentration", risk.get("concentration_risk", portfolio.get("concentration_risk", 0.0))),
        ("VaR 95 Proxy", risk.get("var_95_proxy", 0.0)),
    ]
    metric_cards = "".join(
        "<div class='metric'>"
        f"<div class='muted'>{escape(label)}</div>"
        f"<div class='metric-value'>{_format_scalar(value)}</div>"
        "</div>"
        for label, value in metrics
    )
    exposure_rows = "".join(
        "<tr>"
        f"<td>{escape(str(item.get('symbol', '-')))}</td>"
        f"<td>{_format_scalar(item.get('count', 0))}</td>"
        f"<td>{_format_scalar(item.get('long_lots', 0.0))}</td>"
        f"<td>{_format_scalar(item.get('short_lots', 0.0))}</td>"
        f"<td>{_format_scalar(item.get('net_lots', 0.0))}</td>"
        f"<td>{_format_scalar(item.get('floating_pnl', 0.0))}</td>"
        "</tr>"
        for item in exposure if isinstance(item, dict)
    ) or "<tr><td colspan='6'>No open exposure</td></tr>"
    note_items = "".join(f"<li>{escape(str(note))}</li>" for note in notes) or "<li>No risk notes.</li>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portfolio | ZONES</title>
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation("/portfolio")}</nav>
    <section class="hero">
      <div class="card">
        <h1 style="margin-top:0;">Hedge Fund Portfolio Analysis</h1>
        <div class="muted">Risk, exposure, concentration, leverage proxy, and PnL attribution from the latest account snapshot.</div>
        <div style="margin-top:12px;">
          <span class="pill">Account: {escape(str(portfolio.get("account_id", "-")))}</span>
          <span class="pill">Symbol Context: {escape(str(portfolio.get("symbol", "-")))}</span>
          <span class="pill">Positions: {_format_scalar(fund.get("open_position_count", portfolio.get("open_position_count", 0)))}</span>
        </div>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">Risk Notes</h2>
        <ul>{note_items}</ul>
        <a class="button" href="/api/portfolio?format=json">Raw Metrics</a>
      </div>
    </section>
    <section class="card">
      <div class="metrics-grid">{metric_cards}</div>
    </section>
    <section class="grid" style="margin-top:18px;">
      <div class="card">
        <h2 style="margin-top:0;">Exposure By Symbol</h2>
        <table>
          <thead><tr><th>Symbol</th><th>Positions</th><th>Long Lots</th><th>Short Lots</th><th>Net Lots</th><th>PnL</th></tr></thead>
          <tbody>{exposure_rows}</tbody>
        </table>
      </div>
      <div class="card">
        <h2 style="margin-top:0;">PnL Attribution</h2>
        {_dict_table(pnl)}
        <h2>Risk Metrics</h2>
        {_dict_table(risk)}
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
  <link rel="icon" type="image/x-icon" href="/favicon.ico">
  <link rel="shortcut icon" href="/favicon.ico">
  <link rel="apple-touch-icon" href="/assets/zones-logo.png">
  <style>{_base_css()}</style>
</head>
<body>
  <div class="shell">
    <nav class="nav">{_route_navigation(current_path)}</nav>
    <section class="hero">
      <div class="card">
        <div class="brand">
          <img class="brand-logo" src="/assets/Zones.png" alt="ZONES logo">
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
        self._httpd: ThreadingHTTPServer | None = None
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
        database_settings = dict(stored.get("database", {})) if isinstance(stored.get("database"), dict) else {}
        telegram_settings = dict(stored.get("telegram", {})) if isinstance(stored.get("telegram"), dict) else {}
        chart_settings = dict(stored.get("chart", {})) if isinstance(stored.get("chart"), dict) else {}

        try:
            self._apply_runtime_settings(
                database_url=database_url,
                config_updates=config_updates,
                database_settings=database_settings,
                telegram_settings=telegram_settings,
                chart_settings=chart_settings,
                persist=False,
            )
            return self._runtime_snapshot(database_url)
        except Exception as exc:
            self.diagnostics["last_error"] = f"Runtime settings load failed: {exc}"
            return self._runtime_snapshot(database_url)

    def _runtime_snapshot(self, database_url: str) -> dict[str, Any]:
        current = getattr(self, "runtime_settings", {}) if isinstance(getattr(self, "runtime_settings", {}), dict) else {}
        database_url = str(database_url or current.get("database_url", ""))
        return {
            "database_url": database_url,
            "database_url_input": str(current.get("database_url_input", database_url)),
            "database_username": str(current.get("database_username", "")),
            "database_password": str(current.get("database_password", "")),
            "database_masked_url": mask_database_url(database_url),
            "telegram_enabled": coerce_bool(current.get("telegram_enabled"), False),
            "telegram_bot_token": str(current.get("telegram_bot_token", "")),
            "telegram_chat_ids": str(current.get("telegram_chat_ids", "")),
            "telegram_status": str(current.get("telegram_status", "not configured")),
            "chart_symbol": str(current.get("chart_symbol", getattr(self.config, "symbol", "EURUSD"))).upper(),
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
            database_settings: dict[str, Any] | None = None,
            telegram_settings: dict[str, Any] | None = None,
            chart_settings: dict[str, Any] | None = None,
            persist: bool,
    ) -> None:
        for key, value in config_updates.items():
            setattr(self.config, key, value)

        current = dict(self.runtime_settings)
        db_settings = dict(database_settings or {})
        raw_database_url = str(db_settings.get("url") or database_url or "").strip()
        database_username = str(db_settings.get("username", "")).strip()
        database_password = str(db_settings.get("password", ""))
        parsed_database_url = urlsplit(raw_database_url)
        if parsed_database_url.password and not database_password:
            database_password = unquote(parsed_database_url.password)
        if parsed_database_url.username and not database_username:
            database_username = unquote(parsed_database_url.username)
        if parsed_database_url.password or parsed_database_url.username:
            host = parsed_database_url.hostname or ""
            port = f":{parsed_database_url.port}" if parsed_database_url.port else ""
            raw_database_url = urlunsplit(
                (
                    parsed_database_url.scheme,
                    f"{host}{port}",
                    parsed_database_url.path,
                    parsed_database_url.query,
                    parsed_database_url.fragment,
                )
            )
        effective_database_url = _compose_database_url(
            raw_database_url,
            database_username,
            database_password,
        )

        if effective_database_url:
            current["database_url_input"] = raw_database_url
            current["database_username"] = database_username
            current["database_password"] = database_password

        telegram = dict(telegram_settings or {})
        telegram_token = str(
            telegram.get("bot_token", telegram.get("telegram_bot_token", current.get("telegram_bot_token", "")))
        ).strip()
        manual_chat_ids = _parse_chat_ids(
            telegram.get("chat_ids", telegram.get("telegram_chat_ids", current.get("telegram_chat_ids", "")))
        )
        telegram_enabled = coerce_bool(
            telegram.get("enabled", telegram.get("telegram_enabled", current.get("telegram_enabled", False))),
            False,
        )
        telegram_status = str(current.get("telegram_status", "not configured"))
        discovered_chat_ids: list[int] = []
        if telegram_token:
            discovered_chat_ids, telegram_status = _discover_telegram_chat_ids(telegram_token)
        chat_ids = list(dict.fromkeys([*manual_chat_ids, *discovered_chat_ids]))

        chart = dict(chart_settings or {})
        chart_symbol = str(chart.get("symbol", current.get("chart_symbol", self.config.symbol)) or self.config.symbol).upper()

        current.update(
            {
                "database_url": effective_database_url,
                "database_url_input": raw_database_url,
                "database_username": database_username,
                "database_password": database_password,
                "database_masked_url": mask_database_url(effective_database_url),
                "telegram_enabled": telegram_enabled,
                "telegram_bot_token": telegram_token,
                "telegram_chat_ids": ", ".join(str(item) for item in chat_ids),
                "telegram_status": telegram_status,
                "chart_symbol": chart_symbol,
            }
        )

        self.config.symbol = chart_symbol or self.config.symbol
        self.runtime_settings = current
        self.runtime_settings.update(self._runtime_snapshot(effective_database_url))

        if persist:
            self.settings_store.save(
                {
                    "database_url": effective_database_url,
                    "database": {
                        "url": raw_database_url,
                        "username": database_username,
                        "password": database_password,
                    },
                    "telegram": {
                        "enabled": telegram_enabled,
                        "bot_token": telegram_token,
                        "chat_ids": chat_ids,
                    },
                    "chart": {
                        "symbol": chart_symbol,
                    },
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

        safe_runtime = dict(runtime)
        safe_runtime["database_password"] = _mask_secret(str(safe_runtime.get("database_password", "")))
        safe_runtime["telegram_bot_token"] = _mask_secret(str(safe_runtime.get("telegram_bot_token", "")))
        safe_runtime["database_url"] = mask_database_url(str(safe_runtime.get("database_url", "")))
        safe_runtime["database_masked_url"] = mask_database_url(str(runtime.get("database_url", "")))

        return {
            "database": database,
            "runtime": safe_runtime,
            "signal_model": signal_model,
            "live_signal": live_signal,
            "diagnostics": dict(self.diagnostics),
            "tracked_symbols": self.feed_service.tracked_symbols(account_id),
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

                asset = ASSET_ROUTES.get(parsed.path)
                if asset is not None:
                    self._send_file(*asset)
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

                if parsed.path == "/portfolio":
                    payload = server._build_payload(account_id, symbol)
                    portfolio = build_portfolio_analysis(payload)
                    self._send_html(_portfolio_page_html(portfolio))
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

                if parsed.path == "/api/portfolio":
                    payload = server._build_payload(account_id, symbol)
                    portfolio = build_portfolio_analysis(payload)
                    self._send_route_payload(
                        title="Portfolio Analysis",
                        subtitle="Hedge fund style exposure, risk, concentration, and PnL metrics.",
                        payload=portfolio,
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
                                "/portfolio": "Hedge fund portfolio analysis",
                                "/system": "System status and runtime controls",
                                "POST /api/ingest": "Accept live MT4 terminal snapshots as JSON",
                                "/api/analysis": "Structured analysis payload",
                                "/api/chart": "Candlestick chart payload for one timeframe",
                                "/api/reports": "Recent stored reports",
                                "/api/symbols": "Tracked symbols",
                                "/api/commands": "Command queue snapshot",
                                "/api/portfolio": "Portfolio risk and exposure metrics",
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

                if parsed.path == "/api/ingest":
                    try:
                        content_length = int(self.headers.get("Content-Length", "0"))
                        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
                        payload = json.loads(raw.decode("utf-8"))
                        result = server.feed_service.ingest_payload(payload)
                        server.diagnostics["ingest_requests"] = (
                            int(server.diagnostics.get("ingest_requests", 0)) + 1
                        )
                        server.diagnostics["last_ingest_at"] = result["report"]["created_at"]
                        server.diagnostics["last_ingest_symbol"] = result["symbol"]
                        server.diagnostics["last_transport"] = "http"
                        server.diagnostics["last_error"] = ""
                    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                        server.diagnostics["ingest_failures"] = (
                            int(server.diagnostics.get("ingest_failures", 0)) + 1
                        )
                        server.diagnostics["last_error"] = str(exc)
                        self._send_json({"status": "error", "message": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                        return
                    except Exception as exc:
                        server.diagnostics["ingest_failures"] = (
                            int(server.diagnostics.get("ingest_failures", 0)) + 1
                        )
                        server.diagnostics["last_error"] = str(exc)
                        self._send_json({"status": "error", "message": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                        return

                    self._send_json(result, status=HTTPStatus.CREATED)
                    return

                form = self._read_form()

                if parsed.path == "/api/system/settings":
                    try:
                        database_url = str(form.get("database_url", [""])[0]).strip()
                        database_password = str(form.get("database_password", [""])[0])
                        if database_password == "":
                            database_password = str(server.runtime_settings.get("database_password", ""))
                        telegram_token = str(form.get("telegram_bot_token", [""])[0]).strip()
                        if telegram_token == "":
                            telegram_token = str(server.runtime_settings.get("telegram_bot_token", ""))
                        chart_symbol_custom = str(form.get("chart_symbol_custom", [""])[0]).strip().upper()
                        chart_symbol = chart_symbol_custom or str(form.get("chart_symbol", [server.config.symbol])[0]).strip().upper()
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
                            database_settings={
                                "url": database_url,
                                "username": str(form.get("database_username", [""])[0]).strip(),
                                "password": database_password,
                            },
                            telegram_settings={
                                "enabled": coerce_bool(form.get("telegram_enabled", ["off"])[0], False),
                                "bot_token": telegram_token,
                                "chat_ids": str(form.get("telegram_chat_ids", [""])[0]).strip(),
                            },
                            chart_settings={
                                "symbol": chart_symbol,
                            },
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
                    account_id = str(form.get("account_id", [""])[0])
                    symbol = str(form.get("symbol", [""])[0]).upper()
                    timeframe = str(form.get("timeframe", ["5M"])[0])
                    tv_symbol = str(form.get("tv_symbol", [""])[0])

                    def command_redirect(kind: str, text: str) -> str:
                        return "/chart?" + urlencode(
                            {
                                "account_id": account_id,
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "tv_symbol": tv_symbol,
                                kind: text,
                            }
                        )

                    try:
                        command_type = str(form.get("command_type", ["alert"])[0])

                        params: dict[str, Any] = {}
                        for key in ("lot", "price", "sl", "tp", "ticket", "filter_symbol", "comment", "message"):
                            raw = str(form.get(key, [""])[0]).strip()
                            if raw != "":
                                params[key] = raw

                        order_commands = {
                            "market_buy",
                            "market_sell",
                            "buy_limit",
                            "sell_limit",
                            "buy_stop",
                            "sell_stop",
                        }
                        pending_commands = {"buy_limit", "sell_limit", "buy_stop", "sell_stop"}
                        ticket_commands = {"modify_ticket", "close_ticket", "delete_ticket"}

                        if command_type in order_commands and coerce_float(params.get("lot"), 0.0) <= 0:
                            raise ValueError("Lot must be greater than 0.")
                        if command_type in pending_commands and coerce_float(params.get("price"), 0.0) <= 0:
                            raise ValueError("Price is required for pending orders.")
                        if command_type in ticket_commands and coerce_int(params.get("ticket"), 0) <= 0:
                            raise ValueError("Ticket is required for ticket commands.")
                        if command_type == "alert" and not params.get("message"):
                            raise ValueError("Message is required for alert commands.")

                        server.feed_service.enqueue_command(
                            account_id=account_id,
                            symbol=symbol,
                            command_type=command_type,
                            params=params,
                        )
                        self._redirect(command_redirect("message", "Command queued"))
                    except Exception as exc:
                        self._redirect(command_redirect("error", str(exc)))
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
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(body)
                    self.wfile.flush()
                except Exception as exc:
                    server.logger.warning("HTTP client disconnected before response completed: %s", exc)

            def _send_file(self, path: Path, content_type: str) -> None:
                if not path.exists():
                    self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                    return
                data = path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.send_header("X-Content-Type-Options", "nosniff")
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

    def serve(self, host: str = "127.0.0.1", port: int = 8787) -> None:
        handler = self.create_handler()

        httpd = ThreadingHTTPServer((host, port), handler)
        httpd.daemon_threads = True
        self._httpd = httpd
        try:
            httpd.serve_forever()
        finally:
            httpd.server_close()
            self._httpd = None

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
