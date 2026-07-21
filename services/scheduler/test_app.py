import unittest

from app import Scheduler


class FakePoster:
    """Records calls and returns canned (code, body) responses keyed by URL suffix."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url, obj, timeout=5.0):
        self.calls.append((url, obj))
        for suffix, resp in self.responses.items():
            if url.endswith(suffix):
                return resp
        return 404, {"error": "no stub"}


class TestScheduler(unittest.TestCase):
    def test_happy_path_issues_token_then_dispatches(self):
        poster = FakePoster({
            "/token": (200, {"token": "tok-123"}),
            "/run": (200, {"ok": True, "pr_url": "https://example.invalid/pr/t1"}),
        })
        s = Scheduler("http://gov", "http://runner", poster=poster)
        result = s.process_one({"id": "t1", "title": "fix"})

        self.assertTrue(result["ok"])
        self.assertEqual(len(poster.calls), 2)
        # token requested first, for the right action/subject
        self.assertTrue(poster.calls[0][0].endswith("/token"))
        self.assertEqual(poster.calls[0][1]["action"], "open_pr")
        self.assertEqual(poster.calls[0][1]["subject"], "t1")
        # runner dispatched with the issued token
        self.assertTrue(poster.calls[1][0].endswith("/run"))
        self.assertEqual(poster.calls[1][1]["token"], "tok-123")

    def test_token_denied_does_not_dispatch(self):
        poster = FakePoster({"/token": (403, {"error": "denied"})})
        s = Scheduler("http://gov", "http://runner", poster=poster)
        result = s.process_one({"id": "t2"})

        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "token")
        # runner must never be called when the token is denied
        self.assertEqual(len(poster.calls), 1)

    def test_runner_failure_recorded(self):
        poster = FakePoster({
            "/token": (200, {"token": "tok"}),
            "/run": (502, {"error": "runner down"}),
        })
        s = Scheduler("http://gov", "http://runner", poster=poster)
        result = s.process_one({"id": "t3"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["stage"], "run")

    def test_run_once_drains_queue(self):
        poster = FakePoster({"/token": (200, {"token": "t"}), "/run": (200, {"ok": True})})
        s = Scheduler("http://gov", "http://runner", poster=poster)
        s.enqueue({"id": "a"})
        s.enqueue({"id": "b"})
        results = s.run_once()
        self.assertEqual(len(results), 2)
        self.assertEqual(s.status()["pending"], 0)


if __name__ == "__main__":
    unittest.main()
