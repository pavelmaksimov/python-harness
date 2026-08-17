# Pytest conftest fixtures

Copy into `tests/conftest.py` (merge with existing fixtures; do not overwrite without asking).
HTTP mock fixtures can be taken as-is. Wire `metadata` / `app` to the package.

Shared fixtures stay here. Modular tests live under `tests/test_modules/`; e2e under
`tests/test_e2e/` (e2e-only fixtures may go in `tests/test_e2e/conftest.py`).
Keep payloads out of fixtures — put scenario data in the test or in `tests/factories.py`.

```python
from collections.abc import Generator
from typing import Any

import httpx
import pytest
import pytest_asyncio
import respx
from aioresponses import aioresponses
from requests_mock import Mocker
from sqlalchemy import create_engine
from starlette.testclient import TestClient
from testcontainers.postgres import PostgresContainer

from project.components.base.models import Base
from project.container import Container
from project.infrastructure.adapters import database
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


# --- Database (Testcontainers) -----------------------------------------------


@pytest.fixture(scope="session")
def init_database(setup):
    with PostgresContainer("postgres:17.2") as postgres:
        async_dsn = postgres.get_connection_url(driver="asyncpg")
        sync_dsn = async_dsn.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        with Settings.local(SQLALCHEMY_DATABASE_DSN=async_dsn, DB_SCHEMA=None):
            sync_engine = create_engine(sync_dsn)
            try:
                Base.metadata.create_all(bind=sync_engine, checkfirst=True)
            finally:
                sync_engine.dispose()
            yield
            database.aengine_factory.cache_clear()
            database.async_sessionmaker_factory.cache_clear()


@pytest_asyncio.fixture
async def asession(init_database):
    database.aengine_factory.cache_clear()
    database.async_sessionmaker_factory.cache_clear()
    async with database.asession() as session:
        async with session.begin() as transaction:
            async with session.begin_nested():
                yield session
            await transaction.rollback()
```

Set `asyncio_mode = auto` in `pytest.ini` (or `[tool.pytest.ini_options]`).

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

async def test_repo(asession):
    # asession is already in a nested transaction; data rolls back after the test
    ...

def test_with_stub():
    with Container.local(repo=FakeRepo()):
        ...
```

Several LLM calls → several `httpx.Response` values in `side_effect`, in order.
Use `Settings.override` (not `local`) when the client runs in another thread (`asyncio.to_thread`).
