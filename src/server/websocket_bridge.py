from __future__ import annotations

import json
import logging
import time
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

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
        port: int = 8090,
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
            "WebSocket bridge listening on ws://%s:%s", self.host, self.port
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def _handler(self, websocket) -> None:
        WS_CLIENTS.inc()
        remote = getattr(websocket, "remote_address", None)

        try:
         
            async for raw in websocket:
                started = time.perf_counter()
                action = "unknown"

                try:
                    envelope = json.loads(raw)
                    payload = self._extract_payload(envelope, websocket)
                    action = str(payload.get("action", ""))

                    self.kill_switch.assert_allows(action)
                    response = self.process_payload(payload)

                    REQUEST_LATENCY.labels("websocket", action).observe(
                        time.perf_counter() - started
                    )
                    await websocket.send(json.dumps(response))

                except SignatureError as exc:
                    COMMANDS_TOTAL.labels(action, "signature_error").inc()
                    await websocket.send(
                        json.dumps({"status": "error", "message": str(exc)})
                    )

                except PermissionError as exc:
                    COMMANDS_TOTAL.labels(action, "blocked").inc()
                    await websocket.send(
                        json.dumps({"status": "blocked", "message": str(exc)})
                    )

                except Exception as exc:
                    self.logger.exception("WebSocket handler error on action=%s", action)
                    COMMANDS_TOTAL.labels(action, "error").inc()
                    await websocket.send(
                        json.dumps({"status": "error", "message": str(exc)})
                    )

        except ConnectionClosedOK:
            self.logger.info("WebSocket client closed cleanly: %s", remote)

        except ConnectionClosedError as exc:
            self.logger.warning("WebSocket client disconnected uncleanly: %s | %s", remote, exc)

        except ConnectionClosed as exc:
            self.logger.info("WebSocket client closed: %s | %s", remote, exc)

        finally:
            WS_CLIENTS.dec()

    def _extract_payload(self, envelope: dict[str, Any], websocket) -> dict[str, Any]:
        """
        Accept signed envelopes when available, but allow plain localhost JSON
        so MT4 can connect without building your signature envelope format.
        """
        try:
            payload = verify_envelope(envelope)
            if isinstance(payload, dict):
                return payload
            raise SignatureError("Verified envelope did not produce a JSON object payload")
        except SignatureError:
            remote = getattr(websocket, "remote_address", None)
            remote_host = ""
            if isinstance(remote, tuple) and remote:
                remote_host = str(remote[0])

            if remote_host in {"127.0.0.1", "::1", "localhost"} and isinstance(envelope, dict):
                return envelope

            raise

    def _command_dict_to_wire(self, cmd: dict[str, Any]) -> str:
        """
        Convert a Python command dict into the MT4 wire format:
        id=...|type=...|symbol=...|lot=...|sl=...|tp=...
        """
        parts: list[str] = []

        command_id = str(cmd.get("id", ""))
        command_type = str(cmd.get("type", cmd.get("command_type", "")))
        symbol = str(cmd.get("symbol", ""))

        if command_id:
            parts.append(f"id={command_id}")
        if command_type:
            parts.append(f"type={command_type}")
        if symbol:
            parts.append(f"symbol={symbol}")

        params = cmd.get("params", {})
        if isinstance(params, dict):
            for key, value in params.items():
                parts.append(f"{key}={value}")

        for key, value in cmd.items():
            if key in {"id", "type", "command_type", "symbol", "params"}:
                continue
            parts.append(f"{key}={value}")

        return "|".join(parts)

    def _normalize_fetch_command_result(self, result: Any) -> dict[str, Any]:
        """
        Normalize feed_service.fetch_next_command(...) output into:
        {"status": "ok", "command": "..."}
        """
        if result is None:
            return {"status": "ok", "command": ""}

        if isinstance(result, str):
            return {"status": "ok", "command": result}

        if isinstance(result, dict):
            if "command" in result:
                cmd = result.get("command", "")
                if isinstance(cmd, dict):
                    return {"status": "ok", "command": self._command_dict_to_wire(cmd)}
                return {"status": "ok", "command": str(cmd or "")}

            if "result" in result:
                value = result.get("result", "")
                if isinstance(value, dict):
                    return {"status": "ok", "command": self._command_dict_to_wire(value)}
                return {"status": "ok", "command": str(value or "")}

            if any(k in result for k in ("id", "type", "command_type", "symbol", "params")):
                return {"status": "ok", "command": self._command_dict_to_wire(result)}

        return {"status": "ok", "command": str(result)}

    def process_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", ""))

        if action == "health":
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {
                "status": "ok",
                "message": "alive",
                "host": self.host,
                "port": self.port,
            }

        if action == "kill_switch_on":
            reason = str(payload.get("reason", "manual activation"))
            self.kill_switch.activate(reason)
            self.audit_logger.log_event("kill_switch_on", {"reason": reason})
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok", "kill_switch": self.kill_switch.snapshot()}

        if action == "kill_switch_off":
            self.kill_switch.clear()
            self.audit_logger.log_event("kill_switch_off", {})
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok", "kill_switch": self.kill_switch.snapshot()}

        if action == "post_snapshot":
            inner_payload = payload.get("payload", {})
            if not isinstance(inner_payload, dict):
                raise ValueError("post_snapshot requires 'payload' to be a JSON object")

            result = self.feed_service.ingest_payload(inner_payload)
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {
                "status": "ok",
                "account_id": result["account_id"],
                "symbol": result["symbol"],
                "created_at": result["report"]["created_at"],
                "execution_allowed": result["report"]["execution_decision"]["allowed"],
            }

        if action in {"fetch_command", "fetch_next_command"}:
            result = self.feed_service.fetch_next_command(
                str(payload.get("account_id", "")),
                str(payload.get("symbol", "")),
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return self._normalize_fetch_command_result(result)

        if action == "fetch_chart_snapshot":
            result = self.feed_service.chart_snapshot_wire(
                str(payload.get("account_id", "")),
                str(payload.get("symbol", "")),
                str(payload.get("timeframe", "")),
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok", "snapshot": result}

        if action == "command_ack":
            command_id = str(payload.get("id", ""))
            status = str(payload.get("status", ""))
            message = str(payload.get("message", ""))

            self.audit_logger.log_command(
                command_id=command_id,
                action="command_ack",
                account_id=str(payload.get("account_id", "")),
                symbol=str(payload.get("symbol", "")),
                status=status,
                metadata={"message": message},
            )
            COMMANDS_TOTAL.labels(action, "ok").inc()
            return {"status": "ok"}

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
                metadata={"command_type": str(payload.get("command_type", ""))},
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