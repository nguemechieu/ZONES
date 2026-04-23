# ZONES Chart Terminal

The browser chart terminal is available at:

```text
http://127.0.0.1:8787/chart
```

It renders a local candlestick chart from the same payload used by the dashboard and overlays the selected symbol's ZONES directly on the candles.

## What The User Can Do

- Select an ingested MT4 symbol from the `Tracked Symbol` menu.
- Enter a custom symbol in the chart form, such as `EURUSD`, `GBPUSD`, or `XAUUSD`.
- Switch between available timeframe feeds, for example `1M`, `5M`, and `1H`.
- View supply, demand, support, and resistance zones as colored ranges on the local candle terminal.
- Compare the local ZONES terminal with the optional TradingView symbol override field.
- Queue MT4 commands from the same chart page after checking the selected symbol and zones.

## Data Flow

1. MT4 sends candle, account, symbol, and zone data through the named-pipe bridge.
2. `LiveFeedService` normalizes the payload and stores the latest report by account and symbol.
3. `/chart?symbol=SYMBOL&timeframe=TF` asks the dashboard for that symbol's latest payload.
4. The browser renders the candle terminal SVG from `chart_data[TF]`.
5. Zone overlays are filtered to the same timeframe and ignore zones marked `deleted`.

HTTP ingest clients can also post JSON snapshots to:

```text
POST http://127.0.0.1:8787/api/ingest
```

If no live MT4 report has arrived yet, the terminal uses the waiting payload so the page still renders and the user can verify the UI.

## Useful URLs

```text
http://127.0.0.1:8787/chart?symbol=EURUSD&timeframe=5M
http://127.0.0.1:8787/chart?symbol=XAUUSD&timeframe=1M
http://127.0.0.1:8787/api/chart?symbol=EURUSD&timeframe=5M&format=json
```

`/api/chart` returns the raw candles, zones, AI signal, and execution decision for integrations or troubleshooting.

## Visual Meaning

- Green ranges: demand zones.
- Red ranges: supply zones.
- Blue ranges: support.
- Amber ranges: resistance.
- Amber dashed line: last close.

The overlay comes from the ZONES engine payload, so changing the selected symbol or timeframe changes both candles and zones together.
