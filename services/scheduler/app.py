"""scheduler — pulls pending tickets and dispatches them through the trust ladder.

For each ticket the scheduler:
  1. asks governance-mcp for a one-shot `open_pr` token (propose step),
  2. dispatches the ticket + token to the ticket-to-pr-runner.

If governance denies the token, the ticket never reaches the runner. Reference stand-in,
standard library only.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def http_post_json(url: str, obj: dict, timeout: float = 5.0):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except Exception:
            body = {"error": "http error"}
        return e.code, body
    except urllib.error.URLError as e:
        return 0, {"error": str(e)}


class Scheduler:
    def __init__(self, gov_url: str, runner_url: str, poster=http_post_json):
        self.gov_url = gov_url.rstrip("/")
        self.runner_url = runner_url.rstrip("/")
        self.poster = poster
        self.pending: deque = deque()
        self.processed: list[dict] = []
        self.lock = threading.Lock()

    def enqueue(self, ticket: dict) -> None:
        with self.lock:
            self.pending.append(ticket)

    def process_one(self, ticket: dict) -> dict:
        # 1. Request a one-shot token for this specific ticket (propose).
        code, body = self.poster(
            f"{self.gov_url}/token",
            {"caller": "scheduler", "action": "open_pr", "subject": ticket["id"]},
        )
        if code != 200:
            result = {"ticket": ticket["id"], "ok": False, "stage": "token", "error": body}
            with self.lock:
                self.processed.append(result)
            return result

        token = body["token"]

        # 2. Dispatch the ticket + token to the runner (the runner re-verifies the token).
        code, body = self.poster(f"{self.runner_url}/run", {"ticket": ticket, "token": token})
        result = {"ticket": ticket["id"], "ok": code == 200, "stage": "run", "response": body}
        with self.lock:
            self.processed.append(result)
        return result

    def run_once(self) -> list[dict]:
        with self.lock:
            batch = list(self.pending)
            self.pending.clear()
        return [self.process_one(t) for t in batch]

    def worker_loop(self, interval: float, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                self.run_once()
            except Exception as e:  # never let the loop die on a transient error
                print(json.dumps({"level": "error", "msg": "run_once failed", "err": str(e)}), flush=True)
            stop_event.wait(interval)

    def status(self) -> dict:
        with self.lock:
            return {"pending": len(self.pending), "processed": list(self.processed[-50:])}


class Handler(BaseHTTPRequestHandler):
    sched: Scheduler = None

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw or b"{}")

    def log_message(self, *_):
        pass

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"status": "ok"})
        if self.path == "/readyz":
            return self._send(200, {"status": "ready"})
        if self.path == "/status":
            return self._send(200, self.sched.status())
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._read_json()
        except Exception:
            return self._send(400, {"error": "invalid json"})
        if self.path == "/enqueue":
            if "id" not in body:
                return self._send(400, {"error": "ticket needs an id"})
            self.sched.enqueue(body)
            return self._send(202, {"queued": body["id"]})
        self._send(404, {"error": "not found"})


def build_scheduler() -> Scheduler:
    return Scheduler(
        gov_url=os.environ.get("GOVERNANCE_URL", "http://governance-mcp:8080"),
        runner_url=os.environ.get("RUNNER_URL", "http://ticket-to-pr-runner:8080"),
    )


def serve() -> None:
    Handler.sched = build_scheduler()
    interval = float(os.environ.get("POLL_INTERVAL", "5"))
    stop = threading.Event()
    worker = threading.Thread(target=Handler.sched.worker_loop, args=(interval, stop), daemon=True)
    worker.start()

    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"level": "info", "msg": "scheduler listening", "port": port, "interval": interval}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    serve()
