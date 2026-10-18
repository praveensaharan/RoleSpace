"""Checks for the public website: the work-email lookup, its rate limit, the caller's address
behind proxies, and the security headers. Run: python tests/test_website.py"""

import os
import pathlib
import sys

os.environ.setdefault("TRUSTED_PROXIES", "8.232.87.117/32,35.191.0.0/16,130.211.0.0/22")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "website"))

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402

client = TestClient(server.app)


def lookup(email, ip="203.0.113.10"):
    return client.post("/api/org", json={"email": email}, headers={"x-forwarded-for": ip})


def test_known_domain_finds_its_workspace():
    r = lookup("maya@firstround.example")
    assert r.status_code == 200
    assert r.json() == {"status": "found", "org": "FirstRound", "workspace": "https://rolespace.duckdns.org",
                        "sign_in": "Google"}


def test_other_emails_get_the_demo_workspace_only():
    personal, unknown = lookup("someone@gmail.com").json(), lookup("someone@acme.com").json()
    assert personal["status"] == "personal" and unknown["status"] == "unknown"
    # Only URLs from orgs.json ever come back, so the lookup can't redirect anywhere else.
    allowed = {o["workspace"] for o in server.ORGS.values()}
    assert personal["workspace"] in allowed and unknown["workspace"] in allowed


def test_bad_input_is_refused():
    assert lookup("not-an-email").status_code == 400
    assert lookup("a" * 199 + "@x.com").status_code == 422   # over the 200-character cap


def test_rate_limit_is_per_caller():
    server._seen.clear()
    codes = [lookup("a@b.com", ip="198.51.100.7").status_code for _ in range(server.LOOKUPS_PER_MINUTE + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {200}
    assert lookup("a@b.com", ip="198.51.100.8").status_code == 200   # someone else isn't affected


def test_caller_address_skips_our_proxies():
    class Req:
        def __init__(self, xff):
            self.headers = {"x-forwarded-for": xff}
            self.client = None
    # The load balancer and Google's front ends are skipped; a forged left-hand entry is ignored.
    assert server._client(Req("6.6.6.6, 203.0.113.7, 8.232.87.117")) == "203.0.113.7"
    assert server._client(Req("203.0.113.7, 8.232.87.117, 35.191.4.4")) == "203.0.113.7"


def test_pages_carry_security_headers():
    r = client.get("/")
    assert r.status_code == 200 and "Log in to your organization" in r.text
    csp = r.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "unsafe-inline" not in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert client.get("/assets/logos/googlegemini.svg").status_code == 200


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("ok  ", t.__name__)
    print(f"{len(tests)} checks passed")
