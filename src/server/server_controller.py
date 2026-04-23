import sys
import threading
import webbrowser
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal, QObject

# ---------------------------
# IMPORT YOUR SERVER MODULES
# ---------------------------
from src.db.repository.learning_repository import LearningRepository
from src.server.bridge import LiveFeedService
from src.server.dashboard_server import DashboardServer
from src.server.websocket_bridge import WebSocketBridgeServer
from src.pipe_server.name_pipe_server import NamedPipeBridgeServer
from src.execution.metrics import KILL_SWITCH, start_metrics_server
from src.execution.kill_switch import GlobalKillSwitch
from src.execution.audit import AuditLogger
from src.server.engine_config import EngineConfig

import asyncio
import logging
import os
from pathlib import Path


# ---------------------------
# SERVER CONTROLLER
# ---------------------------
class ServerController(QObject):
    server_stopped = Signal()

    def __init__(self):
        super().__init__()
        self.running = False
        self.thread = None
        self.loop = None
        self.dashboard = None

    def start_server(self):
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()

    def stop_server(self):
        if not self.running:
            return

        self.running = False

        try:
            if self.dashboard is not None:
                self.dashboard.stop()
        except Exception:
            pass

        try:
            KILL_SWITCH.set(1)
        except Exception:
            pass

        try:
            if self.loop:
                self.loop.call_soon_threadsafe(self.loop.stop)
        except Exception:
            pass

        self.server_stopped.emit()

    def _run_server(self):
        logging.basicConfig(
            level=os.getenv("ZONES_LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        logger = logging.getLogger("zones.gui.main")

        config = EngineConfig(
            symbol=os.getenv("ZONES_SYMBOL", "EURUSD"),
            account_id=os.getenv("ZONES_ACCOUNT_ID", ""),
            ai_enabled=os.getenv("ZONES_AI_ENABLED", "true").strip().lower() in ("1", "true", "yes", "on"),
        )

        dashboard_host = os.getenv("ZONES_DASHBOARD_HOST", "127.0.0.1")
        dashboard_port = int(os.getenv("ZONES_DASHBOARD_PORT", "8787"))
        ws_host = os.getenv("ZONES_WS_HOST", "127.0.0.1")
        ws_port = int(os.getenv("ZONES_WS_PORT", "8090"))

        repository = LearningRepository()
        feed_service = LiveFeedService(config, repository)

        diagnostics = {
            "health": "starting",
            "ingest_requests": 0,
            "ingest_failures": 0,
            "last_ingest_at": "",
            "last_ingest_symbol": "",
            "last_error": "",
            "transport": "http+pipe+websocket",
            "pipe_name": os.getenv("ZONES_PIPE_NAME", r"\\.\pipe\ZonesBridgePipe"),
            "last_transport": "",
            "dashboard_url": f"http://{dashboard_host}:{dashboard_port}",
            "websocket_url": f"ws://{ws_host}:{ws_port}",
        }

        kill_switch = GlobalKillSwitch()
        audit_logger = AuditLogger(os.getenv("ZONES_AUDIT_LOG", "logs/ai_decisions.jsonl"))

        pipe_server = NamedPipeBridgeServer(
            feed_service=feed_service,
            diagnostics=diagnostics,
            pipe_name=diagnostics["pipe_name"],
            kill_switch=kill_switch,
            audit_logger=audit_logger,
        )

        ws_server = WebSocketBridgeServer(
            feed_service=feed_service,
            diagnostics=diagnostics,
            kill_switch=kill_switch,
            audit_logger=audit_logger,
            host=ws_host,
            port=ws_port,
        )

        dashboard = DashboardServer(
            config=config,
            repository=repository,
            feed_service=feed_service,
            diagnostics=diagnostics,
        )
        self.dashboard = dashboard

        metrics_port = int(os.getenv("ZONES_METRICS_PORT", "9108"))
        start_metrics_server(metrics_port)
        logger.info("Prometheus metrics available on :%s", metrics_port)

        self.loop = asyncio.new_event_loop()

        def websocket_runner():
            try:
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(ws_server.start())
                logger.info("WebSocket bridge listening on ws://%s:%s", ws_host, ws_port)
                self.loop.run_forever()
            except Exception:
                logger.exception("WebSocket thread crashed")

        def dashboard_runner():
            try:
                logger.info("Dashboard listening on http://%s:%s", dashboard_host, dashboard_port)
                dashboard.serve(host=dashboard_host, port=dashboard_port)
            except Exception:
                logger.exception("Dashboard thread crashed")

        ws_thread = threading.Thread(target=websocket_runner, daemon=True)
        dashboard_thread = threading.Thread(target=dashboard_runner, daemon=True)

        try:
            ws_thread.start()
            dashboard_thread.start()

            pipe_server.start()
            diagnostics["health"] = "ok"
            logger.info("All services started")

            webbrowser.open(f"http://{dashboard_host}:{dashboard_port}")

            ws_thread.join()
            dashboard_thread.join()

        except Exception:
            logger.exception("Fatal error in server thread")

        finally:
            diagnostics["health"] = "stopping"
            KILL_SWITCH.set(1 if kill_switch.is_active() else 0)

            try:
                pipe_server.stop()
            except Exception:
                logger.exception("Failed stopping pipe server")

            try:
                dashboard.stop()
            except Exception:
                logger.exception("Failed stopping dashboard")

            try:
                if self.loop:
                    self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception:
                logger.exception("Failed stopping event loop")

            self.server_stopped.emit()
            self.running = False
            self.dashboard = None
