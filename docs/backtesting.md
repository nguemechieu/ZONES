# ZONES Backtesting

The browser backtester is available at:

```text
http://127.0.0.1:8787/backtest
```

It runs against the same latest symbol payload used by the chart page. The selected timeframe reads candles from `chart_data[TF]` and filters zones from the engine's `zones` list.

## Strategy

The first version uses a deterministic zone-touch model:

1. Find an eligible demand, supply, support, or resistance zone on the selected timeframe.
2. Wait for a candle to touch that zone.
3. Enter at the next candle open.
4. Set stop-loss beyond the zone edge, plus the optional stop buffer.
5. Set take-profit from the configured risk-reward multiple.
6. Exit at stop-loss, take-profit, or max hold bars.

If stop-loss and take-profit are both touched in the same candle, the backtester applies stop-loss first. That keeps results conservative.

## Controls

- `symbol`: selected MT4-ingested symbol.
- `timeframe`: candle feed to test, such as `1M`, `5M`, or `1H`.
- `initial_balance`: starting account balance for normalized simulation.
- `risk_per_trade_pct`: account percent risked on a full stop-loss.
- `risk_reward`: target multiple relative to zone-based risk.
- `max_hold_bars`: bars to hold before a time exit.
- `max_trades`: maximum simulated trades.
- `min_strength`: minimum zone strength.
- `zone_family`: `all`, `main`, or `temp`.
- `zone_kind`: `all`, `demand`, `supply`, `support`, or `resistance`.
- `stop_buffer`: extra price buffer beyond the zone edge.

## Metrics

The backtest page reports:

- return percentage and net PnL
- trade count, wins, losses, and win rate
- profit factor
- max drawdown percentage
- net R and expectancy R
- per-trade entry, stop, target, exit, reason, R multiple, PnL, and equity

Raw JSON is available at:

```text
http://127.0.0.1:8787/api/backtest?symbol=EURUSD&timeframe=5M&format=json
```

## Limitations

This first pass does not include spread, slippage, swaps, commissions, broker pip value, or partial fills. It normalizes position size so every stop-loss equals the configured account risk percentage.
