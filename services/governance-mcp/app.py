"""governance-mcp — the trust core of the agent fleet.

Reference implementation (standard library only) of three controls the fleet relies on:

  1. Default-deny trust ladder — a caller may only request action tokens it is explicitly
     allowed to request. Everything else is denied and audited.
  2. One-shot action tokens — HMAC-signed, single-use, time-bounded capabilities. Replaying a
     consumed token fails.
  3. Append-only, hash-chained audit stream — every decision is recorded to a tamper-evident
     log (each record commits to the previous record's hash) and mirrored to stdout.

This is a stand-in for the production governance MCP server; the security *shape* is the point.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


class Governance:
    """Core governance logic, independent of the HTTP layer so it can be unit-tested directly."""

    def __init__(self, secret: bytes, trust_ladder: dict[str, set[str]], audit_path: str, clock=time.time):
        self.secret = secret
        self.trust = trust_ladder
        self.audit_path = audit_path
        self.clock = clock
        self._issued: dict[str, dict] = {}
        self._events: list[dict] = []
        self._prev_hash = "0" * 64
        self._seq = 0
        self._lock = threading.Lock()

    # ---- audit stream ----

    def audit(self, event: str, details: dict) -> dict:
        """Append one tamper-evident record. Append-only: there is no update or delete."""
        with self._lock:
            self._seq += 1
            record = {
                "seq": self._seq,
                "ts": int(self.clock()),
                "event": event,
                "details": details,
                "prev_hash": self._prev_hash,
            }
            payload = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
            record["hash"] = hashlib.sha256(payload).hexdigest()
            self._prev_hash = record["hash"]
            self._events.append(record)
            line = json.dumps(record, sort_keys=True)
            try:
                with open(self.audit_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass  # stdout stream below is the durable path if the volume is unavailable
            print(line, flush=True)
            return record

    def recent(self, n: int = 50) -> list[dict]:
        with self._lock:
            return list(self._events[-n:])

    def verify_chain(self) -> bool:
        """Re-derive every record hash to confirm the audit stream was not altered."""
        prev = "0" * 64
        with self._lock:
            for rec in self._events:
                base = {k: rec[k] for k in ("seq", "ts", "event", "details", "prev_hash")}
                if rec["prev_hash"] != prev:
                    return False
                payload = json.dumps(base, sort_keys=True, separators=(",", ":")).encode()
                if hashlib.sha256(payload).hexdigest() != rec["hash"]:
                    return False
                prev = rec["hash"]
        return True

    # ---- trust ladder ----

    def allowed(self, caller: str, action: str) -> bool:
        return action in self.trust.get(caller, set())

    # ---- one-shot action tokens ----

    def issue_token(self, caller: str, action: str, subject: str, ttl: int = 300) -> str:
        if not self.allowed(caller, action):
            self.audit("token.denied", {"caller": caller, "action": action, "subject": subject})
            raise PermissionError(f"caller '{caller}' may not request action '{action}'")
        jti = secrets.token_hex(16)
        payload = {
            "jti": jti,
            "action": action,
            "subject": subject,
            "caller": caller,
            "exp": int(self.clock()) + ttl,
        }
        token = self._sign(payload)
        with self._lock:
            self._issued[jti] = {"consumed": False, "action": action, "subject": subject}
        self.audit("token.issued", {"jti": jti, "caller": caller, "action": action, "subject": subject})
        return token

    def _sign(self, payload: dict) -> str:
        body = _b64e(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        sig = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
        return f"{body}.{sig}"

    def verify_and_consume(self, token: str) -> dict:
        try:
            body, sig = token.split(".", 1)
        except ValueError:
            raise ValueError("malformed token")
        expected = hmac.new(self.secret, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            self.audit("token.invalid", {"reason": "bad_signature"})
            raise ValueError("bad signature")
        payload = json.loads(_b64d(body))
        if int(self.clock()) > int(payload["exp"]):
            self.audit("token.invalid", {"jti": payload.get("jti"), "reason": "expired"})
            raise ValueError("token expired")
        jti = payload["jti"]
        with self._lock:
            rec = self._issued.get(jti)
            if rec is None:
                self.audit("token.invalid", {"jti": jti, "reason": "unknown"})
                raise ValueError("unknown token")
            if rec["consumed"]:
                self.audit("token.replay", {"jti": jti})
                raise ValueError("token already consumed")
            rec["consumed"] = True
        self.audit("token.consumed", {"jti": jti, "action": payload["action"], "subject": payload["subject"]})
        return payload


# ---- HTTP layer ----


class Handler(BaseHTTPRequestHandler):
    gov: Governance = None  # set in serve()

    def _send(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw or b"{}")

    def log_message(self, *_args):  # silence default noisy logging
        pass

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if self.path == "/readyz":
            return self._send(200, {"status": "ready"})
        if self.path == "/audit":
            return self._send(200, {"events": self.gov.recent(50), "chain_valid": self.gov.verify_chain()})
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._read_json()
        except Exception:
            return self._send(400, {"error": "invalid json"})

        if self.path == "/token":
            try:
                token = self.gov.issue_token(body["caller"], body["action"], body.get("subject", ""))
                return self._send(200, {"token": token})
            except PermissionError as e:
                return self._send(403, {"error": str(e)})
            except KeyError as e:
                return self._send(400, {"error": f"missing field {e}"})

        if self.path == "/verify":
            try:
                payload = self.gov.verify_and_consume(body["token"])
                return self._send(200, {"valid": True, "action": payload["action"], "subject": payload["subject"]})
            except ValueError as e:
                return self._send(401, {"valid": False, "error": str(e)})
            except KeyError as e:
                return self._send(400, {"error": f"missing field {e}"})

        if self.path == "/audit":
            rec = self.gov.audit(body.get("event", "custom"), body.get("details", {}))
            return self._send(200, {"recorded": rec["seq"]})

        self._send(404, {"error": "not found"})


def _secret_from_env() -> bytes:
    path = os.environ.get("GOV_HMAC_SECRET_FILE")
    if path:
        with open(path, "rb") as f:
            return f.read().strip()
    val = os.environ.get("GOV_HMAC_SECRET")
    if val:
        return val.encode()
    print(json.dumps({"level": "warn", "msg": "GOV_HMAC_SECRET not set; using insecure dev default"}), flush=True)
    return b"dev-insecure-secret"


def _trust_from_env() -> dict[str, set[str]]:
    raw = os.environ.get("TRUST_LADDER")
    if raw:
        data = json.loads(raw)
        return {k: set(v) for k, v in data.items()}
    # Default: only the scheduler may request open_pr tokens. Everything else is denied.
    return {"scheduler": {"open_pr"}}


def build_governance() -> Governance:
    return Governance(
        secret=_secret_from_env(),
        trust_ladder=_trust_from_env(),
        audit_path=os.environ.get("AUDIT_LOG_PATH", "audit.log"),
    )


def serve() -> None:
    Handler.gov = build_governance()
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"level": "info", "msg": "governance-mcp listening", "port": port}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    serve()
