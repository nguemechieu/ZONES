from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server


INGEST_REQUESTS = Counter(
    "zones_ingest_requests_total", "Total ingest requests")
INGEST_FAILURES = Counter(
    "zones_ingest_failures_total", "Total ingest failures")
COMMANDS_TOTAL = Counter("zones_commands_total",
                         "Total commands processed", ["action", "status"])
PIPE_CLIENTS = Gauge("zones_pipe_clients_active", "Active pipe clients")
WS_CLIENTS = Gauge("zones_websocket_clients_active",
                   "Active websocket clients")
KILL_SWITCH = Gauge("zones_kill_switch_active",
                    "Whether the global kill-switch is active")
REQUEST_LATENCY = Histogram("zones_request_latency_seconds",
                            "Request processing latency", ["transport", "action"])


def start_metrics_server(port: int = 9108) -> None:
    start_http_server(port)
