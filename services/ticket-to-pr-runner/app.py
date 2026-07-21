"""ticket-to-pr-runner — turns a ticket into a pull request, under governance.

Flow for POST /run {ticket, token}:
  1. Re-verify (and consume) the one-shot token with governance-mcp. The token's action must be
     `open_pr` and its subject must match this ticket. A denied/expired/replayed token stops here.
  2. Open a PR. DRY_RUN (default) synthesizes a PR URL; with GITHUB_TOKEN + GITHUB_REPO and
     DRY_RUN=false it drives the real GitHub API.
  3. Announce via the notify-bridge with an HMAC-signed request.

Reference stand-in, standard library only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Http:
    """Thin urllib wrapper; injected so tests can stub network calls."""

    def post_json(self, url: str, obj: dict, timeout: float = 5.0):
        return self._request(url, json.dumps(obj).encode(), {"Content-Type": "application/json"}, "POST", timeout)

    def post_raw(self, url: str, data: bytes, headers: dict, timeout: float = 5.0):
        return self._request(url, data, headers, "POST", timeout)

    def _request(self, url, data, headers, method, timeout):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {"error": "http error"}
            return e.code, body
        except urllib.error.URLError as e:
            return 0, {"error": str(e)}


class Runner:
    def __init__(self, gov_url, notify_url, notify_secret: bytes, github_token=None,
                 github_repo=None, base_branch="main", dry_run=True, http=None):
        self.gov_url = gov_url.rstrip("/")
        self.notify_url = notify_url.rstrip("/")
        self.notify_secret = notify_secret
        self.github_token = github_token
        self.github_repo = github_repo
        self.base_branch = base_branch
        self.dry_run = dry_run
        self.http = http or Http()

    def verify_token(self, token: str, ticket_id: str) -> dict:
        code, body = self.http.post_json(f"{self.gov_url}/verify", {"token": token})
        if code != 200 or not body.get("valid"):
            raise PermissionError(body.get("error", "token verification failed"))
        if body.get("action") != "open_pr":
            raise PermissionError("token action mismatch")
        if body.get("subject") != ticket_id:
            raise PermissionError("token subject mismatch")
        return body

    def open_pr(self, ticket: dict) -> dict:
        if self.dry_run or not (self.github_token and self.github_repo):
            repo = self.github_repo or "example/repo"
            return {"pr_url": f"https://example.invalid/{repo}/pull/{ticket['id']}", "dry_run": True}
        return self._open_pr_github(ticket)

    def _open_pr_github(self, ticket: dict) -> dict:
        api = "https://api.github.com"
        repo = self.github_repo
        headers = {
            "Authorization": f"Bearer {self.github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "agent-fleet-runner",
            "Content-Type": "application/json",
        }
        _, ref = self.http._request(f"{api}/repos/{repo}/git/ref/heads/{self.base_branch}", None, headers, "GET", 10)
        base_sha = ref["object"]["sha"]
        branch = f"agent/{ticket['id']}"
        self.http._request(
            f"{api}/repos/{repo}/git/refs",
            json.dumps({"ref": f"refs/heads/{branch}", "sha": base_sha}).encode(), headers, "POST", 10,
        )
        path = f"tickets/{ticket['id']}.md"
        content = base64.b64encode(f"# {ticket.get('title', 'ticket')}\n\n{ticket.get('body', '')}\n".encode()).decode()
        self.http._request(
            f"{api}/repos/{repo}/contents/{path}",
            json.dumps({"message": f"chore: address {ticket['id']}", "content": content, "branch": branch}).encode(),
            headers, "PUT", 10,
        )
        _, pr = self.http._request(
            f"{api}/repos/{repo}/pulls",
            json.dumps({
                "title": f"[agent] {ticket.get('title', ticket['id'])}",
                "head": branch, "base": self.base_branch,
                "body": ticket.get("body", "Opened by the agent fleet."),
            }).encode(), headers, "POST", 10,
        )
        return {"pr_url": pr.get("html_url"), "dry_run": False}

    def notify(self, message: str, title: str = "ticket shipped"):
        body = json.dumps({"title": title, "message": message}).encode()
        sig = hmac.new(self.notify_secret, body, hashlib.sha256).hexdigest()
        return self.http.post_raw(
            f"{self.notify_url}/notify", body,
            {"Content-Type": "application/json", "X-Signature-256": f"sha256={sig}"},
        )

    def run(self, ticket: dict, token: str) -> dict:
        self.verify_token(token, ticket["id"])
        pr = self.open_pr(ticket)
        ncode, _ = self.notify(f"PR for {ticket['id']}: {pr.get('pr_url')}")
        return {
            "ok": True,
            "pr_url": pr.get("pr_url"),
            "dry_run": pr.get("dry_run", False),
            "notified": ncode in (200, 207),
        }


class Handler(BaseHTTPRequestHandler):
    runner: Runner = None

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
        self._send(404, {"error": "not found"})

    def do_POST(self):
        try:
            body = self._read_json()
        except Exception:
            return self._send(400, {"error": "invalid json"})
        if self.path == "/run":
            try:
                ticket, token = body["ticket"], body["token"]
            except KeyError as e:
                return self._send(400, {"error": f"missing field {e}"})
            try:
                return self._send(200, self.runner.run(ticket, token))
            except PermissionError as e:
                return self._send(403, {"ok": False, "error": str(e)})
            except Exception as e:
                return self._send(502, {"ok": False, "error": str(e)})
        self._send(404, {"error": "not found"})


def _secret_from_env() -> bytes:
    path = os.environ.get("NOTIFY_HMAC_SECRET_FILE")
    if path:
        with open(path, "rb") as f:
            return f.read().strip()
    return os.environ.get("NOTIFY_HMAC_SECRET", "dev-insecure-secret").encode()


def _github_token_from_env():
    path = os.environ.get("GITHUB_TOKEN_FILE")
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return os.environ.get("GITHUB_TOKEN")


def build_runner() -> Runner:
    return Runner(
        gov_url=os.environ.get("GOVERNANCE_URL", "http://governance-mcp:8080"),
        notify_url=os.environ.get("NOTIFY_URL", "http://notify-bridge:8080"),
        notify_secret=_secret_from_env(),
        github_token=_github_token_from_env(),
        github_repo=os.environ.get("GITHUB_REPO"),
        base_branch=os.environ.get("BASE_BRANCH", "main"),
        dry_run=os.environ.get("DRY_RUN", "true").lower() != "false",
    )


def serve() -> None:
    Handler.runner = build_runner()
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"level": "info", "msg": "ticket-to-pr-runner listening",
                      "port": port, "dry_run": Handler.runner.dry_run}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    serve()
