from logging import WARNING

import httpx
import pytest

from esg.config import Config
from esg.main import run
from tests.utils import run_server


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_return_close_header():
    config = Config(app=app, host="localhost", loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:8000", headers={"connection": "close"}
            )

    assert response.status_code == 204
    assert (
        "connection" in response.headers and response.headers["connection"] == "close"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host, url",
    [
        pytest.param(None, "http://127.0.0.1:8000", id="default"),
        pytest.param("localhost", "http://127.0.0.1:8000", id="hostname"),
        pytest.param("::1", "http://[::1]:8000", id="ipv6"),
    ],
)
async def test_run(host, url):
    config = Config(app=app, host=host, loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_multiprocess():
    config = Config(app=app, loop="asyncio", workers=2, limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_reload():
    config = Config(app=app, loop="asyncio", reload=True, limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
    assert response.status_code == 204


def test_run_invalid_app_config_combination(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(SystemExit) as exit_exception:
        run(app, reload=True)
    assert exit_exception.value.code == 1
    assert caplog.records[-1].name == "esg.error"
    assert caplog.records[-1].levelno == WARNING
    assert caplog.records[-1].message == (
        "You must pass the application as an import string to enable "
        "'reload' or 'workers'."
    )


def test_run_startup_failure(caplog: pytest.LogCaptureFixture) -> None:
    async def app(scope, receive, send):
        assert scope["type"] == "lifespan"
        message = await receive()
        if message["type"] == "lifespan.startup":
            raise RuntimeError("Startup failed")

    with pytest.raises(SystemExit) as exit_exception:
        run(app, lifespan="on")
    assert exit_exception.value.code == 3
