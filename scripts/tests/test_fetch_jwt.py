"""
Tests for .github/scripts/fetch_jwt.sh, run against a local fake LMS token endpoint.

The function is sourced and called from bash exactly as the translate and seed workflows do,
under `set -euo pipefail` like translate_po_source_strings.sh.
"""
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "..", ".github", "scripts", "fetch_jwt.sh")


class FakeLMS:
    """Answers POSTs with a scripted list of (status, body) responses; repeats the last one."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802 (http.server API)
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                status, body = fake.responses[min(fake.requests, len(fake.responses) - 1)]
                fake.requests += 1
                data = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/oauth2/access_token"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


def token(n, expires_in=3600):
    body = {"access_token": f"jwt-{n}", "token_type": "JWT"}
    if expires_in is not None:
        body["expires_in"] = expires_in
    return (200, body)


def run_calls(lms, calls, **env):
    """Source the script, call fetch_jwt `calls` times, print the token after each call."""
    script = (
        "set -euo pipefail\n"
        f". '{SCRIPT}'\n"
        f"for i in $(seq {calls}); do fetch_jwt || exit 1; echo \"TOKEN=$JWT_TOKEN\"; done\n"
    )
    full_env = {
        **os.environ,
        "LMS_ACCESS_TOKEN_URL": lms.url,
        "EDX_TRANSLATIONS_PROD_CLIENT_ID": "client-id",
        "EDX_TRANSLATIONS_PROD_CLIENT_SECRET": "client-secret",
        "JWT_FETCH_RETRY_DELAY": "1",
        **env,
    }
    proc = subprocess.run(["bash", "-c", script], env=full_env, capture_output=True, text=True, timeout=60)
    tokens = [line.split("=", 1)[1] for line in proc.stdout.splitlines() if line.startswith("TOKEN=")]
    return proc.returncode, tokens, proc.stdout


@pytest.fixture
def lms_factory():
    servers = []

    def make(responses):
        server = FakeLMS(responses)
        servers.append(server)
        return server

    yield make
    for server in servers:
        server.close()


def test_token_is_reused_until_close_to_expiry(lms_factory):
    """225 calls (9 packages x 25 languages) must not mean 225 token requests."""
    lms = lms_factory([token(1), token(2)])
    code, tokens, _ = run_calls(lms, 225)
    assert code == 0
    assert lms.requests == 1
    assert set(tokens) == {"jwt-1"}


def test_token_is_refreshed_when_inside_the_margin(lms_factory):
    """A token with no more than the refresh margin left is replaced on the next call."""
    lms = lms_factory([token(1, expires_in=300), token(2, expires_in=300), token(3, expires_in=300)])
    code, tokens, _ = run_calls(lms, 3, JWT_REFRESH_MARGIN_SECONDS="300")
    assert code == 0
    assert lms.requests == 3
    assert tokens == ["jwt-1", "jwt-2", "jwt-3"]


def test_rate_limit_is_retried(lms_factory):
    """A 429 from the LMS is retried instead of failing the job."""
    lms = lms_factory([(429, {"detail": "throttled"}), (429, {"detail": "throttled"}), token(1)])
    code, tokens, _ = run_calls(lms, 1)
    assert code == 0
    assert lms.requests == 3
    assert tokens == ["jwt-1"]


def test_server_errors_are_retried(lms_factory):
    lms = lms_factory([(503, {}), token(1)])
    code, tokens, _ = run_calls(lms, 1)
    assert code == 0
    assert lms.requests == 2
    assert tokens == ["jwt-1"]


def test_bad_credentials_fail_without_retrying(lms_factory):
    """A 401 is not transient: fail once, clearly, with the status code."""
    lms = lms_factory([(401, {"error": "invalid_client"})])
    code, tokens, out = run_calls(lms, 1)
    assert code == 1
    assert lms.requests == 1
    assert tokens == []
    assert "failed with status code 401" in out


def test_missing_expires_in_uses_default_lifetime(lms_factory):
    lms = lms_factory([token(1, expires_in=None), token(2)])
    code, tokens, _ = run_calls(lms, 5)
    assert code == 0
    assert lms.requests == 1
    assert set(tokens) == {"jwt-1"}


def test_missing_access_token_fails(lms_factory):
    lms = lms_factory([(200, {"token_type": "JWT", "expires_in": 3600})])
    code, _, out = run_calls(lms, 1)
    assert code == 1
    assert "Failed to extract access_token" in out


def test_token_is_masked(lms_factory):
    lms = lms_factory([token(1)])
    _, _, out = run_calls(lms, 1)
    assert "::add-mask::jwt-1" in out
