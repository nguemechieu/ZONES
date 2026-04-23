import tempfile
import unittest
from pathlib import Path

from src.db.repository.learning_repository import LearningRepository
from src.server.bridge import LiveFeedService
from src.server.engine_config import EngineConfig


class BridgeServiceTests(unittest.TestCase):
    def _service(self) -> LiveFeedService:
        base_dir = Path("data") / "test_tmp"
        base_dir.mkdir(parents=True, exist_ok=True)
        database_path = (base_dir / f"bridge_{next(tempfile._get_candidate_names())}.sqlite").resolve()
        self.addCleanup(lambda: database_path.unlink(missing_ok=True))
        repository = LearningRepository(str(database_path))
        config = EngineConfig(symbol="EURUSD", account_id="123456", ai_enabled=True)
        return LiveFeedService(config, repository)

    def test_ingest_payload_accepts_mt4_timeframes_and_returns_ai_response(self) -> None:
        service = self._service()
        payload = {
            "source": "mt4-websocket",
            "symbol": "EURUSD",
            "timeframe": "5M",
            "account": {"account_id": "123456", "balance": 10000, "equity": 10020},
            "timeframes": {
                "1H": [
                    {"timestamp": "2026-04-23T10:00:00Z", "open": 1.0980, "high": 1.1010, "low": 1.0975, "close": 1.1005}
                ],
                "5M": [
                    {"timestamp": "2026-04-23T10:00:00Z", "open": 1.1000, "high": 1.1008, "low": 1.0996, "close": 1.1004},
                    {"timestamp": "2026-04-23T10:05:00Z", "open": 1.1004, "high": 1.1012, "low": 1.1001, "close": 1.1009},
                ],
                "1M": [
                    {"timestamp": "2026-04-23T10:05:00Z", "open": 1.1007, "high": 1.1010, "low": 1.1005, "close": 1.1009}
                ],
            },
            "market_structure": {
                "checkpoint_timeframe": "1H",
                "refinement_timeframe": "5M",
                "bias": "bullish",
                "labels": ["HH", "HL", "BOS"],
                "swings": [{"shift": 12, "kind": "low", "source": "zigzag", "label": "HL", "price": 1.0992}],
                "events": [{"event": "BOS", "direction": "bullish", "structure_label": "HH", "level": 1.1010}],
            },
            "zones": [
                {
                    "id": "demand_1",
                    "timeframe": "5M",
                    "anchor_timeframe": "1H",
                    "kind": "demand",
                    "family": "main",
                    "strength": 3,
                    "strength_label": "S3",
                    "lower": 1.0990,
                    "upper": 1.1000,
                    "body_start": 1.1000,
                    "status": "respected",
                    "mode_bias": "buying",
                    "origin_index": 8,
                    "zigzag_count": 2,
                    "fractal_count": 2,
                    "touch_count": 3,
                    "retest_count": 1,
                    "price_relation": "above",
                    "structure_label": "bullish",
                }
            ],
            "execution_context": {
                "configured_style": "advanced",
                "confirmation_timeframe": "1M",
                "rrr_state": "reject",
                "bos_direction": "bullish",
                "local_prediction": "BUY",
                "local_allowed": True,
                "zone_state": "respected",
            },
            "execution_decision": {
                "allowed": True,
                "direction": "long",
                "timeframe": "1M",
                "score": 3.8,
                "rationale": "Bullish main zone respected after BOS.",
                "style": "advanced",
            },
            "indicator_values": {"spread_points": 12},
        }

        result = service.ingest_payload(payload)
        report = result["report"]

        self.assertEqual(report["chart_data"]["5M"][0]["timestamp"], "2026-04-23T10:00:00Z")
        self.assertEqual(report["zones"][0]["strength_label"], "S3")
        self.assertEqual(report["market_structure"]["bias"], "bullish")
        self.assertEqual(result["ai_response"]["prediction"], "BUY")
        self.assertGreater(result["ai_response"]["confidence"], 0.0)

    def test_chart_snapshot_wire_uses_market_structure_swings_and_events(self) -> None:
        service = self._service()
        service.ingest_payload(
            {
                "symbol": "EURUSD",
                "account": {"account_id": "123456"},
                "timeframes": {"5M": [{"timestamp": "2026-04-23T10:00:00Z", "open": 1.1, "high": 1.101, "low": 1.099, "close": 1.1005}]},
                "market_structure": {
                    "bias": "bearish",
                    "swings": [{"shift": 6, "kind": "high", "source": "zigzag", "label": "LH", "price": 1.1015}],
                    "events": [{"event": "CHOC", "direction": "bearish", "structure_label": "LH", "level": 1.0995}],
                },
                "zones": [
                    {
                        "id": "supply_1",
                        "timeframe": "5M",
                        "anchor_timeframe": "1H",
                        "kind": "supply",
                        "family": "main",
                        "strength": 2,
                        "strength_label": "S2",
                        "lower": 1.1010,
                        "upper": 1.1020,
                        "status": "active",
                        "mode_bias": "selling",
                    }
                ],
            }
        )

        wire = service.chart_snapshot_wire("123456", "EURUSD", "5M")

        self.assertIn("zone|timeframe=5M|kind=supply", wire)
        self.assertIn("swing|origin_shift=6|kind=high|source=zigzag|label=LH", wire)
        self.assertIn("event|event=CHOC|structure_label=LH|direction=bearish", wire)


if __name__ == "__main__":
    unittest.main()
