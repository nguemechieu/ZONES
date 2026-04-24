
from __future__ import annotations

import ctypes
import json
import logging
import threading
import time
from ctypes import wintypes
from typing import Any

from ..execution.audit import AuditLogger
from ..execution.kill_switch import GlobalKillSwitch
from ..execution.metrics import COMMANDS_TOTAL, INGEST_FAILURES, INGEST_REQUESTS, KILL_SWITCH, PIPE_CLIENTS, REQUEST_LATENCY
from ..execution.security import SignatureError, verify_envelope
from ..server.bridge import LiveFeedService


PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_MESSAGE = 0x00000004
PIPE_READMODE_MESSAGE = 0x00000002
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255
INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value
ERROR_BROKEN_PIPE = 109
ERROR_MORE_DATA = 234
ERROR_PIPE_CONNECTED = 535
BUFFER_SIZE = 65536
HEALTH_MESSAGE = "__zones_health__"
MAX_MESSAGE_SIZE = 2_000_000


kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

kernel32.CreateNamedPipeW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
]
kernel32.CreateNamedPipeW.restype = wintypes.HANDLE

kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
kernel32.ConnectNamedPipe.restype = wintypes.BOOL

kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
kernel32.DisconnectNamedPipe.restype = wintypes.BOOL

kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
kernel32.ReadFile.restype = wintypes.BOOL

kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
kernel32.WriteFile.restype = wintypes.BOOL

kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
kernel32.FlushFileBuffers.restype = wintypes.BOOL


class NamedPipeBridgeServer:
    def __init__(
        self,
        feed_service: LiveFeedService,
        diagnostics: dict[str, Any],
        pipe_name: str = r"\\.\pipe\ZonesBridgePipe",
        kill_switch: GlobalKillSwitch | None = None,
        audit_logger: AuditLogger | None = None,
    ) -> None:
        self.feed_service = feed_service
        self.diagnostics = diagnostics
        self.pipe_name = pipe_name
        self.kill_switch = kill_switch or GlobalKillSwitch()
        self.audit_logger = audit_logger or AuditLogger()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.logger = logging.getLogger("zones.pipe")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._serve_forever, daemon=True, name="ZonesPipeServer")
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _serve_forever(self) -> None:
        while not self._stop_event.is_set():
            pipe_handle = kernel32.CreateNamedPipeW(
                self.pipe_name,
                PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                PIPE_UNLIMITED_INSTANCES,
                BUFFER_SIZE,
                BUFFER_SIZE,
                0,
                None,
            )
            if pipe_handle == INVALID_HANDLE_VALUE:
                self._fail(
                    f"CreateNamedPipe failed: {ctypes.get_last_error()}")
                return

            connected = kernel32.ConnectNamedPipe(pipe_handle, None)
            if not connected:
                error_code = ctypes.get_last_error()
                if error_code != ERROR_PIPE_CONNECTED:
                    self._fail(f"ConnectNamedPipe failed: {error_code}")
                    kernel32.CloseHandle(pipe_handle)
                    continue

            worker = threading.Thread(
                target=self._handle_client,
                args=(pipe_handle,),
                daemon=True,
                name="ZonesPipeClient",
            )
            worker.start()

    def _handle_client(self, pipe_handle: wintypes.HANDLE) -> None:
        PIPE_CLIENTS.inc()
        try:
            request = self._read_message(pipe_handle)
            started = time.perf_counter()
            response = self.process_message(request)
            REQUEST_LATENCY.labels("pipe", "message").observe(
                time.perf_counter() - started)
            self._write_message(pipe_handle, response)
            kernel32.FlushFileBuffers(pipe_handle)
            time.sleep(0.02)
        except OSError as exc:
            self._fail(str(exc))
        finally:
            PIPE_CLIENTS.dec()
            kernel32.DisconnectNamedPipe(pipe_handle)
            kernel32.CloseHandle(pipe_handle)

    def process_message(self, message: str) -> str:
        stripped = message.strip()
        if stripped == HEALTH_MESSAGE:
            self.diagnostics["kill_switch"] = self.kill_switch.snapshot()
            KILL_SWITCH.set(1 if self.kill_switch.is_active() else 0)
            return json.dumps(self.diagnostics)

        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError as exc:
            return self._error(f"Invalid JSON payload: {exc}")

        payload = decoded
        if {"timestamp", "payload", "signature"} <= set(decoded.keys()):
            try:
                payload = verify_envelope(decoded)
            except SignatureError as exc:
                COMMANDS_TOTAL.labels(
                    "signed_message", "signature_error").inc()
                return self._error(str(exc))

        action = str(payload.get("action", ""))
        KILL_SWITCH.set(1 if self.kill_switch.is_active() else 0)

        try:
            if action == "kill_switch_on":
                reason = str(payload.get("reason", "manual activation"))
                self.kill_switch.activate(reason)
                self.audit_logger.log_event(
                    "kill_switch_on", {"reason": reason})
                COMMANDS_TOTAL.labels(action, "ok").inc()
                return json.dumps({"status": "ok", "kill_switch": self.kill_switch.snapshot()})

            if action == "kill_switch_off":
                self.kill_switch.clear()
                self.audit_logger.log_event("kill_switch_off", {})
                COMMANDS_TOTAL.labels(action, "ok").inc()
                return json.dumps({"status": "ok", "kill_switch": self.kill_switch.snapshot()})

            self.kill_switch.assert_allows(action)

            if action == "fetch_next_command":
                account_id = str(payload.get("account_id", ""))
                symbol = str(payload.get("symbol", ""))
                COMMANDS_TOTAL.labels(action, "ok").inc()
                result = self.feed_service.command_snapshot(
                    account_id, symbol)
                return result if isinstance(result, str) else json.dumps(result)

            if action == "fetch_chart_snapshot":
                account_id = str(payload.get("account_id", ""))
                symbol = str(payload.get("symbol", ""))
                timeframe = str(payload.get("timeframe", ""))
                COMMANDS_TOTAL.labels(action, "ok").inc()
                return self.feed_service.chart_snapshot_wire(account_id, symbol, timeframe)

            if action == "send_command_result":
                result = self.feed_service.record_command_result(
                    command_id=str(payload.get("command_id", "")),
                    status=str(payload.get("status", "")),
                    message=str(payload.get("message", "")),
                    extras=dict(payload.get("extras", {})),
                )
                self.audit_logger.log_command(
                    command_id=str(payload.get("command_id", "")),
                    action="send_command_result",
                    account_id="",
                    symbol="",
                    status=str(payload.get("status", "")),
                    metadata={"message": str(payload.get("message", ""))},
                )
                COMMANDS_TOTAL.labels(action, "ok").inc()
                return json.dumps({"status": "ok", "result": result})

            if action == "queue_command":
                command = self.feed_service.enqueue_command(
                    account_id=str(payload.get("account_id", "")),
                    symbol=str(payload.get("symbol", "")),
                    command_type=str(payload.get("command_type", "")),
                    params=dict(payload.get("params", {})),
                )
                self.audit_logger.log_command(
                    command_id=str(command.get("id", "")),
                    action="queue_command",
                    account_id=str(payload.get("account_id", "")),
                    symbol=str(payload.get("symbol", "")),
                    status="queued",
                    metadata={"command_type": str(
                        payload.get("command_type", ""))},
                )
                COMMANDS_TOTAL.labels(action, "ok").inc()
                return json.dumps({"status": "ok", "command": command})

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
                return json.dumps({"status": "ok"})

            result = self.feed_service.ingest_payload(payload)

            INGEST_REQUESTS.inc()
            self.diagnostics["ingest_requests"] += 1
            self.diagnostics["last_ingest_at"] = result["report"]["created_at"]
            self.diagnostics["last_ingest_symbol"] = result["symbol"]
            self.diagnostics["last_error"] = ""
            self.diagnostics["last_transport"] = "named-pipe"
            COMMANDS_TOTAL.labels("ingest_payload", "ok").inc()

            self.audit_logger.log_decision(
                symbol=result["symbol"],
                account_id=result["account_id"],
                decision=str(
                    result["report"]["execution_decision"].get("direction", "")),
                allowed=bool(result["report"]
                             ["execution_decision"]["allowed"]),
                confidence=float(
                    result["report"]["execution_decision"].get("confidence", 0.0)),
                reasons=list(result["report"]
                             ["execution_decision"].get("reasons", [])),
                metadata={"transport": "named-pipe"},
            )

            ai_response = dict(result.get("ai_response", {}) or {})
            return json.dumps(
                {
                    "status": "ok",
                    "account_id": result["account_id"],
                    "symbol": result["symbol"],
                    "created_at": result["report"]["created_at"],
                    "execution_allowed": result["report"]["execution_decision"]["allowed"],
                    "execution_direction": result["report"]["execution_decision"].get("direction", "neutral"),
                    "ai_prediction": ai_response.get("prediction", "HOLD"),
                    "ai_confidence": ai_response.get("confidence", 0.0),
                    "ai_reason": ai_response.get("reason", ""),
                    "ai_zone_confirmation": ai_response.get("zone_confirmation", "pending"),
                    "ai_execution_hint": ai_response.get("execution_hint", ""),
                    "ai_risk_hint": ai_response.get("risk_hint", ""),
                    "ai_model_status": ai_response.get("model_status", "warming_up"),
                }
            )

        except PermissionError as exc:
            COMMANDS_TOTAL.labels(action or "unknown", "blocked").inc()
            return json.dumps({"status": "blocked", "message": str(exc)})
        except ValueError as exc:
            COMMANDS_TOTAL.labels(action or "unknown", "error").inc()
            return self._error(str(exc))

    def _read_message(self, handle: wintypes.HANDLE) -> str:
        chunks: list[bytes] = []
        total_size = 0

        while True:
            buffer = ctypes.create_string_buffer(BUFFER_SIZE)
            bytes_read = wintypes.DWORD(0)
            ok = kernel32.ReadFile(
                handle, buffer, BUFFER_SIZE, ctypes.byref(bytes_read), None)

            if ok:
                if bytes_read.value:
                    chunks.append(buffer.raw[: bytes_read.value])
                    total_size += bytes_read.value
                break

            error_code = ctypes.get_last_error()
            if error_code == ERROR_MORE_DATA:
                if bytes_read.value:
                    chunks.append(buffer.raw[: bytes_read.value])
                    total_size += bytes_read.value
                if total_size > MAX_MESSAGE_SIZE:
                    raise OSError(0, "Pipe message too large")
                continue

            if error_code == ERROR_BROKEN_PIPE:
                break

            raise OSError(error_code, "ReadFile from named pipe failed")

        return b"".join(chunks).decode("utf-8")

    def _write_message(self, handle: wintypes.HANDLE, message: str) -> None:
        encoded = message.encode("utf-8")
        buffer = ctypes.create_string_buffer(encoded)
        bytes_written = wintypes.DWORD(0)
        ok = kernel32.WriteFile(handle, buffer, len(
            encoded), ctypes.byref(bytes_written), None)
        if not ok:
            raise OSError(ctypes.get_last_error(),
                          "WriteFile to named pipe failed")

    def _fail(self, message: str) -> None:
        self.logger.error(message)
        self.diagnostics["last_error"] = message
        self.diagnostics["ingest_failures"] += 1
        INGEST_FAILURES.inc()

    def _error(self, message: str) -> str:
        self._fail(message)
        return json.dumps({"status": "error", "message": message})
