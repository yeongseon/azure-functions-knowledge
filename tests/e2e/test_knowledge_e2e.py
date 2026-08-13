"""Real-Azure end-to-end tests for azure-functions-knowledge.

These drive the HTTP routes of ``examples/e2e_app`` on a live Azure Functions
host that was deployed from the release commit's own source (see the e2e-azure
workflow). They are the runtime-behavior proof behind the release gate's Azure
certification.

Usage::

    E2E_BASE_URL=https://<app>.azurewebsites.net pytest tests/e2e -v -m e2e

Every test is marked ``e2e`` and skips automatically when ``E2E_BASE_URL`` is
unset (so ordinary unit runs, which exclude ``-m e2e``, never hit the network).
"""

from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("E2E_BASE_URL", "").rstrip("/")
SKIP_REASON = "E2E_BASE_URL not set — skipping real-Azure e2e tests"

# Consumption (Y1) cold start + Python worker init.
POLL_TIMEOUT_SECONDS = 300
POLL_INTERVAL_SECONDS = 5

pytestmark = pytest.mark.e2e


def _url(path: str) -> str:
    return f"{BASE_URL}{path}"


@pytest.fixture(scope="session", autouse=True)
def warmup() -> None:
    """Retry /api/health until the Consumption cold-start finishes (max 5 min)."""
    if not BASE_URL:
        pytest.skip(SKIP_REASON)
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            r = requests.get(_url("/api/health"), timeout=15)
            if r.status_code == 200:
                return
        except requests.RequestException as exc:  # pragma: no cover - network
            last_exc = exc
        time.sleep(POLL_INTERVAL_SECONDS)
    raise AssertionError(f"Function App never became healthy: {last_exc}")


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_health_lists_registered_provider() -> None:
    r = requests.get(_url("/api/health"), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True, body
    # Proves register_provider("static", ...) ran at import time on the worker.
    assert "static" in body.get("providers", []), body


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_search_returns_matching_document() -> None:
    # A successful search also proves %STATIC_CONNECTION% resolved to
    # "static-e2e": StaticProvider.__init__ raises (→ 500) otherwise.
    r = requests.get(_url("/api/search"), params={"q": "python"}, timeout=30)
    assert r.status_code == 200, r.text
    results = r.json()
    assert isinstance(results, list) and results, results
    titles = {d.get("title") for d in results}
    ids = {d.get("id") for d in results}
    assert "Python v2" in titles, results
    assert "1" in ids, results


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_search_no_match_returns_empty_list() -> None:
    # Deterministic negative: a term that matches no document content yields an
    # empty list (still 200), avoiding exception-to-HTTP ambiguity.
    r = requests.get(_url("/api/search"), params={"q": "no-such-term"}, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json() == [], r.text


@pytest.mark.skipif(not BASE_URL, reason=SKIP_REASON)
def test_doc_by_id_returns_expected_document() -> None:
    # inject_client path: also gated on %STATIC_CONNECTION% resolution.
    r = requests.get(_url("/api/doc/1"), timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("id") == "1", body
    assert body.get("title") == "Python v2", body
    assert "Python v2 programming model" in body.get("content", ""), body
