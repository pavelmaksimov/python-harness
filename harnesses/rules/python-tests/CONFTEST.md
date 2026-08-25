# Pytest conftest fixtures

Copy into `tests/conftest.py` (merge with existing fixtures; do not overwrite without asking).
HTTP mock fixtures can be taken as-is. Wire `app` to the package.

Shared fixtures stay here. Modular tests live under `tests/test_modules/`; e2e under
`tests/test_e2e/` (e2e-only fixtures may go in `tests/test_e2e/conftest.py`).
Keep payloads out of fixtures — put scenario data in the test body.

When `python-sqlalchemy` and `python-db-sessions` are installed, merge sibling
`CONFTEST_DATABASE.md` into this file.
When `python-redis` is installed, merge the Redis fixtures from `python-redis` / `CACHE.md`.

```python
from collections.abc import Generator
from typing import Any

import httpx
import pytest
import respx
from aioresponses import aioresponses
from requests_mock import Mocker
from starlette.testclient import TestClient

from project.container import Container
from project.infrastructure.apps.api import app
from project.settings import Settings


@pytest.fixture(autouse=True, scope="session")
def setup():
    with Settings.override(LOG_LEVEL="DEBUG"):
        yield


@pytest.fixture(autouse=True)
def reset_container():
    Container.reset()
    yield
    Container.reset()


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(app)


# --- HTTP mocks (take as-is) -------------------------------------------------


@pytest.fixture
def httpx_responses() -> Generator[respx.Router]:
    """Mock httpx: same ``Router`` as ``respx`` (``httpx_responses.get(url).mock(...)``)."""
    with respx.mock as router:
        yield router


@pytest.fixture
def aiohttp_responses():
    """Mock aiohttp via aioresponses."""
    with aioresponses() as mock:
        yield mock


@pytest.fixture
def requests_mock() -> Generator[Mocker]:
    """Mock ``requests`` (``requests_mock.get(url, json=..., status_code=...)``)."""
    with Mocker() as mocker:
        yield mocker


def openai_chat_completion_response(payload: Any, *, model: str = "mock") -> httpx.Response:
    """Wrap a domain JSON payload as an OpenAI Chat Completions body (content is a string)."""
    import json

    return httpx.Response(
        200,
        json={
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 1710000000,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        },
    )
```

Set `asyncio_mode = auto` in `pytest.ini` (or `[tool.pytest.ini_options]`) when the repo has async tests.

## Usage

```python
import httpx

def test_httpx(httpx_responses):
    httpx_responses.get("https://api.example.com/data").mock(
        side_effect=[httpx.Response(200, json={"result": "ok"})],
    )

def test_aiohttp(aiohttp_responses):
    aiohttp_responses.add(
        "https://api.example.com/data",
        method="GET",
        payload={"result": "ok"},
        status=200,
    )

def test_requests(requests_mock):
    requests_mock.get(
        "https://gitlab.example.com/api/v4/projects/1",
        json={"id": 1, "name": "demo"},
        status_code=200,
    )

def test_llm(httpx_responses):
    url = f"{Settings().LLM_BASE_URL}/chat/completions"
    httpx_responses.post(url).mock(
        side_effect=[openai_chat_completion_response({"response": []})],
    )

def test_endpoint(api_client):
    response = api_client.get("/health")
    assert response.status_code == 200

def test_with_stub():
    with Container.local(repo=FakeRepo()):
        ...
```

Several LLM calls → several `httpx.Response` values in `side_effect`, in order.
Use `Settings.override` (not `local`) when the client runs in another thread (`asyncio.to_thread`).
