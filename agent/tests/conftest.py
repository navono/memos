import os

os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

import httpx
import pytest

AGENT_URL = "http://localhost:8082"
MEMOS_URL = "http://localhost:5230"


@pytest.fixture(scope="session")
def memos_token():
    """Sign in to Memos and return a valid JWT."""
    with httpx.Client(proxy=None, timeout=30.0) as client:
        resp = client.post(
            f"{MEMOS_URL}/api/v1/auth/signin",
            json={"username": "memos-demo", "password": "secret"},
        )
    assert resp.status_code == 200, f"Signin failed: {resp.text}"
    return resp.cookies.get("memos.access-token")


@pytest.fixture(scope="session")
def user_id():
    return 101


@pytest.fixture(scope="session")
def http():
    with httpx.Client(proxy=None, timeout=120.0) as client:
        yield client
