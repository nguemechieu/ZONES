# MT4 Python Architecture

## Current Architecture

- `MQL4/Experts/ZONES.mq4` is the active MT4 EA.
- MT4 owns:
  - market data extraction
  - ZigZag and Fractal driven zone detection
  - H1 structure checkpointing
  - 5M zone refinement
  - live zone monitoring and invalidation
  - execution-state evaluation for `instant` and `advanced`
  - chart object rendering
  - trade command execution inside MT4
- Python owns:
  - snapshot normalization and persistence
  - advisory AI scoring and metadata
  - dashboard and debugging views
  - command queue persistence and bridge diagnostics

## Bridge Decision

- Primary bridge: localhost WebSocket on `ws://127.0.0.1:8090/ws`
- Legacy compatibility: named-pipe server remains available on the Python side
- Migration decision:
  - WebSocket is the clean primary path for MT4 because it avoids a DLL-only dependency
  - named pipes are kept for backward compatibility and existing tooling, but MT4 now works safely even if Python is offline

## Zone Model

- `TEMP` zones come from H1 ZigZag swing points.
- `MAIN` zones require Fractal confirmation on the same clustered area.
- Main-zone strength:
  - `S1`: 1 Fractal + 1 ZigZag
  - `S2`: 1 Fractal + 2+ ZigZags
  - `S3`: 2+ Fractals + 2+ ZigZags
- Placement flow:
  - H1 defines the structure anchor and candle-body start
  - 5M refines thickness using repeated body-touch and wick interaction
  - zones stretch forward on chart toward current price
- Zone lifecycle:
  - TEMP can promote to MAIN as Fractal confirmation arrives
  - zones can move to `active`, `respected`, `rejected`, `invalidated`, or `deleted`

## Execution Styles

- `instant`
  - MT4 can act immediately when price is near an eligible zone and bias is aligned
- `advanced`
  - MT4 requires lower-timeframe confirmation
  - supports `respect`, `reject`, `retest`, and BOS context
  - lower-timeframe confirmation is configurable with `M5` or `1M`
  - retest count is capped by EA input
  - retest entry can use immediate touch or candle-close behavior

`EnableAutoExecution` is off by default. MT4 still computes execution context and can execute queued commands even when auto execution is disabled.

## MT4 to Python Payload

MT4 now sends:

- account and symbol metadata
- `chart_data` and `timeframes` for `1H`, `5M`, and `1M`
- `market_structure`
  - bias
  - labels
  - swings
  - events such as `BOS` and `CHOC`
- `zones`
  - kind
  - family
  - strength
  - counts for ZigZag, Fractal, touches, and retests
  - origin data
  - status and mode bias
- `execution_context`
- `execution_decision`
- `indicator_values`
- bridge diagnostics

## Python to MT4 Response

`post_snapshot` now returns a structured advisory response:

- `ai_prediction`: `BUY`, `SELL`, or `HOLD`
- `ai_confidence`
- `ai_reason`
- `ai_zone_confirmation`
- `ai_execution_hint`
- `ai_risk_hint`
- `ai_model_status`

MT4 treats this as advisory. Python does not execute trades directly.

## Local Run

1. Start Python:

```powershell
python zones.py
```

2. Attach `MQL4/Experts/ZONES.mq4` in MT4.

3. Confirm the WebSocket bridge:

- dashboard: `http://127.0.0.1:8787`
- bridge: `ws://127.0.0.1:8090/ws`

## Debugging Bridge Failures

- In MT4:
  - check Experts log for `ZONES bridge` messages
  - the corner label shows bridge error state when Python is unavailable
  - the EA keeps local zone analysis active even if the bridge is down
- In Python:
  - check `logs/zones.sqlite` for persisted reports
  - check `logs/ai_decisions.jsonl` for decision audit entries
  - check `/api/health` on the dashboard

## Known TODOs

- Compile and smoke-test the updated EA inside MetaEditor / MT4
- Tighten advanced-execution BOS and MSS logic with live broker data
- Add dedicated tests for the named-pipe bridge parity path
- Extend the dashboard to surface the new MT4 `execution_context` fields more directly
