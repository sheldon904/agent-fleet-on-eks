#!/usr/bin/env python3
"""Local end-to-end test of the agent-fleet pipeline, no AWS or cluster required.

Starts governance-mcp and ticket-to-pr-runner as real HTTP servers plus a mock notify target
(standing in for the Go notify-bridge, which is covered by its own Go tests + CI), then drives
one ticket through the scheduler and asserts the whole trust flow:

    scheduler --(request open_pr token)--> governance
    scheduler --(ticket + token)---------> runner
    runner    --(verify+consume token)---> governance
    runner    --(HMAC-signed notify)-----> notify (mock)

Exits 0 on success, 1 on failure. Uses os._exit to avoid the slow interpreter teardown seen in
this environment.
"""

import hashlib
import hmac
import importlib.util
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVC = os.path.join(ROOT, "services")
SECRET = b"e2e-shared-secret"

GOV_PORT, RUNNER_PORT, NOTIFY_PORT = 18081, 18082, 18085
GOV_URL = f"http://127.0.0.1:{GOV_PORT}"
RUNNER_URL = f"http://127.0.0.1:{RUNNER_PORT}"
NOTIFY_URL = f"http://127.0.0.1:{NOTIFY_PORT}"


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SVC, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gov_mod = load("gov_app", "governance-mcp/app.py")
runner_mod = load("runner_app", "ticket-to-pr-runner/app.py")
sched_mod = load("sched_app", "scheduler/app.py")


# --- mock notify target: verifies the HMAC signature like the real Go bridge does ---
NOTIFY_RECEIVED = []


class NotifyMock(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(length)
        sig = self.headers.get("X-Signature-256", "").removeprefix("sha256=")
        expected = hmac.new(SECRET, body, hashlib.sha256).hexdigest()
        ok = hmac.compare_digest(sig, expected)
        NOTIFY_RECEIVED.append({"ok": ok, "body": json.loads(body)})
        code = 200 if ok else 401
        payload = json.dumps({"delivered": 1 if ok else 0}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def start(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()


def wait_ready(url, tries=50):
    for _ in range(tries):
        try:
            with urllib.request.urlopen(url + "/healthz", timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def main():
    failures = []

    # governance
    gov_mod.Handler.gov = gov_mod.Governance(
        secret=SECRET, trust_ladder={"scheduler": {"open_pr"}},
        audit_path=os.path.join(ROOT, "scripts", ".e2e-audit.log"),
    )
    start(ThreadingHTTPServer(("127.0.0.1", GOV_PORT), gov_mod.Handler))

    # notify mock
    start(ThreadingHTTPServer(("127.0.0.1", NOTIFY_PORT), NotifyMock))

    # runner (points at governance + notify mock)
    runner_mod.Handler.runner = runner_mod.Runner(
        gov_url=GOV_URL, notify_url=NOTIFY_URL, notify_secret=SECRET, dry_run=True,
    )
    start(ThreadingHTTPServer(("127.0.0.1", RUNNER_PORT), runner_mod.Handler))

    for name, url in [("governance", GOV_URL), ("runner", RUNNER_URL)]:
        if not wait_ready(url):
            print(f"FAIL: {name} did not become ready")
            os._exit(1)

    # scheduler drives the flow over real HTTP
    sched = sched_mod.Scheduler(gov_url=GOV_URL, runner_url=RUNNER_URL)
    ticket = {"id": "TCK-1", "title": "Add liveness probe", "body": "probe /healthz"}
    sched.enqueue(ticket)
    results = sched.run_once()

    print("\n=== pipeline result ===")
    print(json.dumps(results, indent=2))

    # assertions
    r0 = results[0] if results else {}
    if not r0.get("ok"):
        failures.append("scheduler did not report success")
    resp = r0.get("response", {})
    if not resp.get("pr_url"):
        failures.append("runner returned no pr_url")
    if not resp.get("notified"):
        failures.append("runner did not report a successful notification")

    # governance audit stream: token issued then consumed, chain intact
    with urllib.request.urlopen(GOV_URL + "/audit", timeout=2) as r:
        audit = json.loads(r.read())
    events = [e["event"] for e in audit["events"]]
    print("\n=== governance audit events ===")
    print(events, "chain_valid=", audit["chain_valid"])
    if "token.issued" not in events:
        failures.append("audit missing token.issued")
    if "token.consumed" not in events:
        failures.append("audit missing token.consumed")
    if not audit["chain_valid"]:
        failures.append("audit hash chain invalid")

    # notify target received exactly one correctly-signed message
    print("\n=== notify target ===")
    print(json.dumps(NOTIFY_RECEIVED, indent=2))
    if len(NOTIFY_RECEIVED) != 1 or not NOTIFY_RECEIVED[0]["ok"]:
        failures.append("notify target did not receive one valid signed message")

    print("\n" + "=" * 40)
    if failures:
        print("E2E FAILED:")
        for f in failures:
            print("  -", f)
        sys.stdout.flush()  # os._exit skips buffer flush
        os._exit(1)
    print("E2E PASSED: ticket -> token -> PR -> signed notification, audit chain intact")
    sys.stdout.flush()  # os._exit skips buffer flush
    os._exit(0)


if __name__ == "__main__":
    main()
