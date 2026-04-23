from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

import websockets


from ..execution.audit import AuditLogger
from ..execution.kill_switch import GlobalKillSwitch
from ..execution.metrics import COMMANDS_TOTAL, REQUEST_LATENCY, WS_CLIENTS
from ..execution.security import SignatureError, verify_envelope


class WebSocketBridgeServer:
    def __init__(
        self,
        feed_service,
        diagnostics: dict[str, Any],
        kill_switch: GlobalKillSwitch,
        audit_logger: AuditLogger,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.feed_service = feed_service
        self.diagnostics = diagnostics
        self.kill_switch = kill_switch
        self.audit_logger = audit_logger
        self.host = host
        self.port = port
        self.logger = logging.getLogger("zones.websocket")
        self._server = None

    async def start(self) -> None:
        self._server = await websockets.serve(self._handler, self.host, self.port)
        self.logger.info(
            "WebSocket bridge listening on ws://%s:%s", self.host, self.port)

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handler(self, websocket) -> None:
        WS_CLIENTS.inc()
        try:
            async for raw in websocket:
                started = time.perf_counter()
                action = "unknown"
                try:
                    envelope = json.loads(raw)
                    payload = verify_envelope(envelope)
                    action = str(payload.get("action", ""))

                    self.kill_switch.assert_allows(action)

                    response = self.process_payload(payload)
                    REQUEST_LATENCY.labels("websocket", action).observe(
                        time.perf_counter() - started)
                    await websocket.send(json.dumps(response))
                except SignatureError as exc:
                    COMMANDS_TOTAL.labels(action, "signature_error").inc()
                    await websocket.send(json.dumps({"status": "error", "message": str(exc)}))
                except PermissionError as exc:
                    COMMANDS_TOTAL.labels(action, "blocked").inc()
                    await websocket.send(json.dumps({"status": "blocked", "message": str(exc)}))
                except Exception as exc:
                    COMMANDS_TOTAL.labels(action, "error").inc()
                    await websocket.send(json.dumps({"status": "error", "message": str(exc)}))
        finally:
            WS_CLIENTS.dec()

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", ""))

        if action == "kill_switch_on":
            reason = str(payload.get("reason", "manual activation"))
            self.kill_switch.activate(reason)
            self.audit_logger.log_event("kill_switch_on", {"reason": reason})
            return {"status": "ok", "kill_switch": self.kill_switch.snapshot()}

        if action == "kill_switch_off":
            self.kill_switch.clear()
            self.audit_logger.log_event("kill_switch_off", {})
            return {"status": "ok", "kill_switch": self.kill_switch.snapshot()}

        if action == "fetch_next_command":
            result = self.feed_service.fetch_next_command(
                str(payload.get("account_id", "")),
                str(payload.get("symbol", "")),
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return result if isinstance(result, dict) else {"status": "ok", "result": result}

        if action == "fetch_chart_snapshot":
            result = self.feed_service.chart_snapshot_wire(
                str(payload.get("account_id", "")),
                str(payload.get("symbol", "")),
                str(payload.get("timeframe", "")),
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok", "snapshot": result}

        if action == "queue_command":
            cmd = self.feed_service.enqueue_command(
                account_id=str(payload.get("account_id", "")),
                symbol=str(payload.get("symbol", "")),
                command_type=str(payload.get("command_type", "")),
                params=dict(payload.get("params", {})),
            )
            self.audit_logger.log_command(
                command_id=str(cmd.get("id", "")),
                action="queue_command",
                account_id=str(payload.get("account_id", "")),
                symbol=str(payload.get("symbol", "")),
                status="queued",
                metadata={"command_type": str(
                    payload.get("command_type", ""))},
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok", "command": cmd}

        if action == "record_ai_decision":
            self.audit_logger.log_decision(
                symbol=str(payload.get("symbol", "")),
                account_id=str(payload.get("account_id", "")),
                decision=str(payload.get("decision", "")),
                allowed=bool(payload.get("allowed", False)),
                confidence=float(payload.get("confidence", 0.0)),
                reasons=list(payload.get("reasons", [])),
                metadata=dict(payload.get("metadata", {})),
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok"}

        result = self.feed_service.ingest_payload(payload)
        COMMANDS_TOTAL.labels("ingest_payload", "ok").inc()
        return {
            "status": "ok",
            "account_id": result["account_id"],
            "symbol": result["symbol"],
            "created_at": result["report"]["created_at"],
            "execution_allowed": result["report"]["execution_decision"]["allowed"],
        }
