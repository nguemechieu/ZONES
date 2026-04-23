import unittest

from src.execution.backtesting import build_backtest_analysis


class BacktestingTests(unittest.TestCase):
    def test_zone_touch_backtest_records_winning_trade(self) -> None:
        payload = {
            "symbol": "EURUSD",
            "chart_data": {
                "5M": [
                    {"timestamp": "2026-04-23T10:00:00Z", "open": 1.1000, "high": 1.1010, "low": 1.0995, "close": 1.1005},
                    {"timestamp": "2026-04-23T10:05:00Z", "open": 1.1005, "high": 1.1018, "low": 1.1000, "close": 1.1010},
                    {"timestamp": "2026-04-23T10:10:00Z", "open": 1.1010, "high": 1.1040, "low": 1.1008, "close": 1.1038},
                ]
            },
            "zones": [
                {
                    "timeframe": "5M",
                    "kind": "demand",
                    "family": "main",
                    "strength": 2,
                    "strength_label": "S2",
                    "lower": 1.0990,
                    "upper": 1.1000,
                    "origin_index": 0,
                    "status": "fresh",
                }
            ],
        }

        result = build_backtest_analysis(
            payload,
            timeframe="5M",
            initial_balance=10000,
            risk_per_trade_pct=1,
            risk_reward=2,
            max_hold_bars=5,
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["summary"]["trades"], 1)
        self.assertEqual(result["summary"]["wins"], 1)
        self.assertEqual(result["summary"]["ending_balance"], 10200.0)
        self.assertEqual(result["trades"][0]["exit_reason"], "take_profit")
        self.assertEqual(result["trades"][0]["r_multiple"], 2.0)

    def test_backtest_reports_insufficient_data_without_zones(self) -> None:
        result = build_backtest_analysis(
            {
                "symbol": "EURUSD",
                "chart_data": {"5M": [{"open": 1.0, "high": 1.1, "low": 0.9, "close": 1.0}]},
                "zones": [],
            },
            timeframe="5M",
        )

        self.assertEqual(result["status"], "insufficient_data")
        self.assertEqual(result["summary"]["trades"], 0)


if __name__ == "__main__":
    unittest.main()
