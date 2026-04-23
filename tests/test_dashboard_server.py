import unittest

from src.server.dashboard_server import _resolve_chart_symbol


class DashboardServerSymbolTests(unittest.TestCase):
    def test_resolve_chart_symbol_prefers_tradingview_symbol(self) -> None:
        self.assertEqual(_resolve_chart_symbol("EURUSD", "OANDA:XAUUSD"), "XAUUSD")

    def test_resolve_chart_symbol_uses_explicit_symbol_when_no_tv_override(self) -> None:
        self.assertEqual(_resolve_chart_symbol("GBPUSD", ""), "GBPUSD")

    def test_resolve_chart_symbol_extracts_pair_from_tradingview_only_input(self) -> None:
        self.assertEqual(_resolve_chart_symbol("", "FX:EURUSD"), "EURUSD")


if __name__ == "__main__":
    unittest.main()
