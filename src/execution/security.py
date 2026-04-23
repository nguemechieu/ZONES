from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any


DEFAULT_TTL_SECONDS = 15


class SignatureError(Exception):
    pass


def _secret() -> bytes:
    value = os.getenv("ZONES_HMAC_SECRET", "").strip()
    if not value:
        raise SignatureError("ZONES_HMAC_SECRET is not configured")
    return value.encode("utf-8")


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sign_payload(payload: dict[str, Any], timestamp: int | None = None) -> dict[str, Any]:
    ts = int(time.time() if timestamp is None else timestamp)
    body = canonical_json(payload)
    message = f"{ts}.{body}".encode("utf-8")
    signature = hmac.new(_secret(), message, hashlib.sha256).hexdigest()

    return {
        "timestamp": ts,
        "payload": payload,
        "signature": signature,
    }


def verify_envelope(envelope: dict[str, Any], ttl_seconds: int = DEFAULT_TTL_SECONDS) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise SignatureError("Envelope must be a dict")

    ts = envelope.get("timestamp")
    payload = envelope.get("payload")
    signature = envelope.get("signature")

    if not isinstance(ts, int):
        raise SignatureError("Missing or invalid timestamp")
    if not isinstance(payload, dict):
        raise SignatureError("Missing or invalid payload")
    if not isinstance(signature, str) or not signature:
        raise SignatureError("Missing signature")

    now = int(time.time())
    if abs(now - ts) > ttl_seconds:
        raise SignatureError("Signature expired or clock skew too large")

    body = canonical_json(payload)
    message = f"{ts}.{body}".encode("utf-8")
    expected = hmac.new(_secret(), message, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise SignatureError("Invalid signature")

    return payload
