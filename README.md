# ZONES

<p >
  <img src="./src/assets/Zones.png" alt="ZONES logo" width="720">
</p>

<p >
  MT4 trading system with a Python dashboard, named-pipe DLL bridge, and customer-specific SMC / ICT market structure logic.
</p>

## What ZONES Is

ZONES is a hybrid MT4 + Python trading application built around customer-defined market structure rules.

Current foundation in this repo includes:

- ZigZag-driven `Temp Zones`
- Fractal-promoted `Main Zones`
- `S1 / S2 / S3` main-zone strength classes
- `HH / LH / LL / HL / EQHH / EQLL` structure labeling
- `BOS`, `CHOC`, and `RRR` event flow
- candle-body buy/sell mode logic
- support, resistance, and liquidity mapping
- multi-timeframe analysis for `1H`, `5M`, and `1M`
- browser dashboard with structured route views
- TradingView Advanced Chart page with live symbol switching, public drawing tools, and ZONES projection overlays
- system status page for runtime settings, remote DB control, AI training, and feedback capture
- editable allowed-session control on the system page for the execution gate
- local MT4 bridge using `ZonesBridge.dll` and Windows named pipes
- local SQLite by default, with optional remote PostgreSQL support

## Architecture

The repo currently uses this flow:

1. `MT4 EA` collects candles, account data, and symbol context.
2. `ZonesBridge.dll` sends requests through a local named pipe.
3. `zones.py` runs the Python service and dashboard.
4. `supply_demand_ea` analyzes structure, zones, execution filters, and phase outputs.
5. The dashboard renders readable HTML views for live monitoring.
6. The MT4 chart fetches the latest analyzed overlay from Python, so chart zones and backend decisions come from the same ZigZag / Fractal report.

Key files:

- Python entrypoint: `zones.py`
- Engine: `supply_demand_ea/analysis.py`
- Browser dashboard: `supply_demand_ea/dashboard.py`
- Live bridge service: `supply_demand_ea/bridge.py`
- Pipe server: `supply_demand_ea/ipc.py`
- MT4 EA: `MQL4/Experts/Zones/Zones.mq4`
- MT4 include: `MQL4/Include/ZonesBridge.mqh`
- DLL source: `bridge_dll/ZonesBridgeDll.cpp`
- Prebuilt x86 debug DLL: `bridge_dll/bin/x86/Debug/ZonesBridge.dll`
- PDF rulebook summary: `docs/zones_pdf_rulebook.md`

## Customer Rulebook Status

The Python engine has been refactored around the provided PDF requirements and now models:

- temp-zone creation from ZigZag structure points
- main-zone promotion from Fractal confirmation
- discrete main-zone strengths instead of generic scores only
- body-based zone mode detection
- `CHOC` deletion of unconfirmed temp zones
- `RRR` stages: `respect`, `reject`, `retest`, `close_confirm`
- structural invalidation language and structural trailing references
- MT4 chart rendering from the same analyzed ZigZag / Fractal overlay that powers the browser dashboard

Supporting docs:

- `docs/zones_pdf_rulebook.md`
- `docs/supply_demand_ea_phase1.md`
- `docs/live_mt4_bridge.md`
- `docs/mt4_dll_bridge.md`

## Run The App

Start the Python service:

```powershell
python zones.py
```

Open the browser dashboard:

```text
http://127.0.0.1:8787
```

Useful routes:

- `/`
- `/chart`
- `/system`
- `/api/analysis`
- `/api/reports`
- `/api/symbols`
- `/api/commands`
- `/api/health`
- `/api/schema`
- `/api/system/status`
- `/api/chart`

Browser routes render structured HTML by default.

For raw JSON, add:

```text
?format=json
```

## Browser Chart And MT4 Commands

Open the chart page:

```text
http://127.0.0.1:8787/chart
```

What it includes:

- candlestick chart for live or waiting candle data
- TradingView Advanced Chart widget as the main browser chart surface
- drawn zone overlays from the ZONES engine
- tracked-symbol and custom-symbol switching on the chart page
- TradingView symbol override input for provider-specific symbols like `FX:EURUSD` or `OANDA:XAUUSD`
- timeframe switching for available feeds
- pending command queue view
- execution history view
- browser form that queues MT4 commands through the existing DLL bridge flow
- auto-filled entry, SL, and TP from the current setup, with manual adjustment before queueing
- basic validation so empty lot, price, ticket, or alert message inputs are rejected before hitting MT4

The browser command panel can queue:

- `market_buy`
- `market_sell`
- `buy_limit`
- `sell_limit`
- `buy_stop`
- `sell_stop`
- `modify_ticket`
- `close_ticket`
- `delete_ticket`
- `close_all`
- `alert`

Those commands are picked up by the MT4 EA when it polls the local bridge.

## MT4 Setup

For the current local bridge, MT4 uses DLL imports instead of `WebRequest`.

1. Copy `bridge_dll/bin/x86/Debug/ZonesBridge.dll` into your MT4 `MQL4/Libraries` folder as `ZonesBridge.dll`.
2. Copy or compile `MQL4/Experts/Zones/Zones.mq4` in MetaEditor.
3. Ensure `MQL4/Include/ZonesBridge.mqh` is available.
4. In MT4, enable `Allow DLL imports`.
5. Start `python zones.py`.
6. Attach the `ZONES` EA to a chart.

Notes:

- MT4 must use the `32-bit` DLL build.
- The Python app should be running before the EA starts posting data.
- The dashboard can ingest all symbols from Market Watch while drawing on the attached chart.
- When `PostAllMarketWatchSymbols` is enabled, the EA now polls command queues across Market Watch symbols too, so browser orders are not limited to the attached chart symbol.
- The attached MT4 chart now draws zones, swings, and structure markers from the Python analysis snapshot instead of a second local swing algorithm.
- If you update the DLL source, rebuild the x86 DLL and replace `MQL4/Libraries/ZonesBridge.dll` before testing in MT4.

## Build The DLL

The DLL project is in `bridge_dll`.

Open that folder in VS Code or Visual Studio and build the x86 target.

Helpful files:

- `bridge_dll/CMakeLists.txt`
- `bridge_dll/CMakePresets.json`
- `bridge_dll/build_msvc.bat`
- `bridge_dll/build_mingw.bat`
- `bridge_dll/README.md`

Expected output:

```text
bridge_dll/bin/x86/Debug/ZonesBridge.dll
```

## Database

Default database:

```text
SQLite
```

Default file:

```text
logs/zones.sqlite
```

Optional remote database:

```powershell
$env:ZONES_DATABASE_URL = "postgresql://user:password@host:5432/zones"
python zones.py
```

SQLite URLs also work:

```powershell
$env:ZONES_DATABASE_URL = "sqlite:///C:/path/to/zones.db"
```

The browser system page can also switch the runtime repository without editing environment variables:

- open `/system`
- paste a SQLite or PostgreSQL URL
- save runtime settings

The same page also exposes live zone sizing controls:

- `Temp Zone Min Thickness`
- `Temp Zone Max Thickness`
- `Main Zone Min Thickness`
- `Main Zone Max Thickness`

## AI Training And Signal

ZONES now includes a lightweight trainable signal model for runtime status and signal guidance.

What it does today:

- trains from recorded trade feedback when enough samples exist
- falls back to bootstrap training from stored reports and execution decisions
- scores the latest live report with a current AI signal and confidence
- exposes model state on `/system` and `/api/system/status`

To use it:

1. ingest live MT4 reports or let the app collect reports normally
2. open `/system`
3. record feedback rows for wins, losses, and PnL
4. click `Train Signal Model`

## Tests

Run the test suite:

```powershell
python -m unittest discover -s tests -v
```

The current tests cover:

- multi-timeframe analysis
- live ingest contracts
- named-pipe health and ingest processing
- command queue flow
- browser HTML route rendering
- temp-to-main promotion
- `RRR` stage generation
- candle-body mode logic
- `CHOC` deletion behavior

## Repo Notes

A few legacy files and folders still exist in the repo from earlier project history, but the current active application path is:

- `zones.py`
- `supply_demand_ea/`
- `MQL4/Experts/Zones/`
- `MQL4/Include/`
- `bridge_dll/`
- `docs/`
- `tests/`

## License

See `LICENSE` and `LICENSE.md`.
