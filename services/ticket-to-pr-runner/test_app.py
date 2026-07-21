import hashlib
import hmac
import unittest

from app import Runner


class FakeHttp:
    def __init__(self, verify_resp):
        self.verify_resp = verify_resp
        self.json_calls = []
        self.raw_calls = []

    def post_json(self, url, obj, timeout=5.0):
        self.json_calls.append((url, obj))
        if url.endswith("/verify"):
            return self.verify_resp
        return 404, {}

    def post_raw(self, url, data, headers, timeout=5.0):
        self.raw_calls.append((url, data, headers))
        return 200, {"delivered": 1}


VALID = (200, {"valid": True, "action": "open_pr", "subject": "t1"})


class TestRunner(unittest.TestCase):
    def test_dry_run_success(self):
        http = FakeHttp(VALID)
        r = Runner("http://gov", "http://notify", b"s", dry_run=True, http=http)
        out = r.run({"id": "t1", "title": "fix"}, "tok")
        self.assertTrue(out["ok"])
        self.assertTrue(out["dry_run"])
        self.assertIn("t1", out["pr_url"])
        self.assertTrue(out["notified"])
        # token verified before notifying
        self.assertTrue(http.json_calls[0][0].endswith("/verify"))
        self.assertEqual(len(http.raw_calls), 1)

    def test_invalid_token_stops_flow(self):
        http = FakeHttp((401, {"valid": False, "error": "already consumed"}))
        r = Runner("http://gov", "http://notify", b"s", dry_run=True, http=http)
        with self.assertRaises(PermissionError):
            r.run({"id": "t1"}, "tok")
        # never opened a PR or notified
        self.assertEqual(len(http.raw_calls), 0)

    def test_subject_mismatch_denied(self):
        http = FakeHttp((200, {"valid": True, "action": "open_pr", "subject": "other"}))
        r = Runner("http://gov", "http://notify", b"s", dry_run=True, http=http)
        with self.assertRaises(PermissionError):
            r.run({"id": "t1"}, "tok")

    def test_action_mismatch_denied(self):
        http = FakeHttp((200, {"valid": True, "action": "delete_repo", "subject": "t1"}))
        r = Runner("http://gov", "http://notify", b"s", dry_run=True, http=http)
        with self.assertRaises(PermissionError):
            r.run({"id": "t1"}, "tok")

    def test_notify_is_hmac_signed_over_exact_body(self):
        secret = b"shared-secret"
        http = FakeHttp(VALID)
        r = Runner("http://gov", "http://notify", secret, dry_run=True, http=http)
        r.run({"id": "t1", "title": "fix"}, "tok")

        _, data, headers = http.raw_calls[0]
        sig = headers["X-Signature-256"].removeprefix("sha256=")
        expected = hmac.new(secret, data, hashlib.sha256).hexdigest()
        self.assertEqual(sig, expected)


if __name__ == "__main__":
    unittest.main()
