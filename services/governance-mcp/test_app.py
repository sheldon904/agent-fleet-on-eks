import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest

from app import Governance


def new_gov(trust=None, now=1000):
    clock = {"t": now}
    fd, path = tempfile.mkstemp()
    os.close(fd)
    g = Governance(
        secret=b"test-secret",
        trust_ladder=trust or {"scheduler": {"open_pr"}},
        audit_path=path,
        clock=lambda: clock["t"],
    )
    return g, clock


class TestGovernance(unittest.TestCase):
    def test_issue_and_consume(self):
        g, _ = new_gov()
        tok = g.issue_token("scheduler", "open_pr", "ticket-42")
        payload = g.verify_and_consume(tok)
        self.assertEqual(payload["action"], "open_pr")
        self.assertEqual(payload["subject"], "ticket-42")

    def test_default_deny_unknown_caller(self):
        g, _ = new_gov()
        with self.assertRaises(PermissionError):
            g.issue_token("intruder", "open_pr", "x")

    def test_action_not_on_ladder(self):
        g, _ = new_gov(trust={"scheduler": {"open_pr"}})
        with self.assertRaises(PermissionError):
            g.issue_token("scheduler", "delete_repo", "x")

    def test_one_shot_replay_rejected(self):
        g, _ = new_gov()
        tok = g.issue_token("scheduler", "open_pr", "t1")
        g.verify_and_consume(tok)
        with self.assertRaises(ValueError):
            g.verify_and_consume(tok)

    def test_expired_token(self):
        g, clock = new_gov(now=1000)
        tok = g.issue_token("scheduler", "open_pr", "t1", ttl=10)
        clock["t"] = 1011
        with self.assertRaises(ValueError):
            g.verify_and_consume(tok)

    def test_tampered_signature(self):
        g, _ = new_gov()
        tok = g.issue_token("scheduler", "open_pr", "t1")
        body, sig = tok.split(".", 1)
        forged = body + "." + ("0" * len(sig))
        with self.assertRaises(ValueError):
            g.verify_and_consume(forged)

    def test_unknown_but_well_signed_token(self):
        g, _ = new_gov()
        payload = {"jti": "deadbeef", "action": "open_pr", "subject": "x", "caller": "scheduler", "exp": 99999999999}
        body = base64.urlsafe_b64encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).rstrip(b"=").decode()
        sig = hmac.new(b"test-secret", body.encode(), hashlib.sha256).hexdigest()
        with self.assertRaises(ValueError):
            g.verify_and_consume(f"{body}.{sig}")

    def test_audit_chain_valid(self):
        g, _ = new_gov()
        g.issue_token("scheduler", "open_pr", "t1")
        g.audit("custom.event", {"k": "v"})
        self.assertTrue(g.verify_chain())

    def test_audit_chain_detects_tamper(self):
        g, _ = new_gov()
        g.issue_token("scheduler", "open_pr", "t1")
        g._events[0]["details"]["action"] = "hacked"
        self.assertFalse(g.verify_chain())


if __name__ == "__main__":
    unittest.main()
