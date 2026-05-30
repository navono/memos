"""Shared pytest fixtures for all test types."""

import os

os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

import httpx
import pytest


# Integration test fixtures (require running services)
MEMOS_URL = os.environ.get("MEMOS_URL", "http://localhost:5230")
MEMOS_USERNAME = os.environ.get("MEMOS_USERNAME", "test-agent")
MEMOS_PASSWORD = os.environ.get("MEMOS_PASSWORD", "test-agent-pass")

# Test data to seed
TEST_MEMOS = [
    {"content": "#todo Buy groceries - milk, eggs, bread", "visibility": "PRIVATE"},
    {"content": "#work Project meeting notes\n- Discuss Q3 roadmap\n- Review PR #42", "visibility": "PRIVATE"},
    {"content": "#personal Birthday ideas for Mom\n- Cookbook\n- Spa voucher", "visibility": "PRIVATE"},
    {"content": "#todo #urgent Finish the agent integration tests", "visibility": "PRIVATE"},
    {"content": "Random thought: The weather is nice today.", "visibility": "PRIVATE"},
]


@pytest.fixture(scope="session")
def memos_token():
    """Sign in to Memos and return a valid JWT.

    Auto-registers the test user if it doesn't exist yet.
    Requires running Memos server with AllowSignUp enabled (default in dev mode).
    """
    with httpx.Client(proxy=None, timeout=30.0) as client:
        # Try signin first
        resp = client.post(
            f"{MEMOS_URL}/api/v1/auth/signin",
            json={"username": MEMOS_USERNAME, "password": MEMOS_PASSWORD},
        )
        if resp.status_code == 200:
            return resp.cookies.get("memos.access-token")

        # If signin fails, try signup (first user becomes host)
        if resp.status_code == 401:
            resp = client.post(
                f"{MEMOS_URL}/api/v1/auth/signup",
                json={"username": MEMOS_USERNAME, "password": MEMOS_PASSWORD},
            )
            if resp.status_code == 200:
                return resp.cookies.get("memos.access-token")

        assert False, (
            f"Failed to authenticate (status={resp.status_code}): {resp.text}. "
            f"Ensure Memos is running in dev mode with AllowSignUp enabled."
        )


@pytest.fixture(scope="session")
def seed_test_data(memos_token):
    """Seed test memos for integration tests.

    Creates test memos if they don't exist yet. Uses a marker tag
    to identify and avoid duplicates.
    """
    MARKER_TAG = "#test-agent-seed"

    with httpx.Client(proxy=None, timeout=30.0) as client:
        headers = {"Authorization": f"Bearer {memos_token}"}

        # Check if already seeded
        resp = client.get(f"{MEMOS_URL}/api/v1/memo", params={"tag": "test-agent-seed"}, headers=headers)
        existing = resp.json()
        if len(existing) > 0:
            return  # Already seeded

        # Create test memos with marker tag
        for memo_data in TEST_MEMOS:
            content = f"{MARKER_TAG}\n\n{memo_data['content']}"
            client.post(
                f"{MEMOS_URL}/api/v1/memo",
                json={"content": content, "visibility": memo_data["visibility"]},
                headers=headers,
            )


@pytest.fixture(scope="session")
def user_id():
    """Default user ID for testing."""
    return 101


@pytest.fixture(scope="session")
def http():
    """HTTP client for integration tests."""
    with httpx.Client(proxy=None, timeout=120.0) as client:
        yield client


# Unit test fixtures
@pytest.fixture
def mock_httpx_response():
    """Factory for creating mock httpx responses."""
    def _make_response(status_code=200, json_data=None):
        import httpx
        from unittest.mock import MagicMock
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.json.return_value = json_data or []
        resp.raise_for_status = MagicMock()
        if status_code >= 400:
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                message="Error", request=MagicMock(), response=resp
            )
        return resp
    return _make_response
