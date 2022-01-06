import asyncio

import pytest

from esg.config import Config
from esg.loops.auto import auto_loop_setup
from esg.main import ServerState
from esg.protocols.websockets.auto import AutoWebSocketsProtocol

try:
    import uvloop
except ImportError:  # pragma: no cover
    uvloop = None

try:
    import httptools
except ImportError:  # pragma: no cover
    httptools = None

try:
    import websockets
except ImportError:  # pragma: no cover
    # Note that we skip the websocket tests completely in this case.
    websockets = None


async def app(scope, receive, send):
    pass  # pragma: no cover


# TODO: Add pypy to our testing matrix, and assert we get the correct classes
#       dependent on the platform we're running the tests under.


def test_loop_auto():
    auto_loop_setup()
    policy = asyncio.get_event_loop_policy()
    assert isinstance(policy, asyncio.events.BaseDefaultEventLoopPolicy)
    expected_loop = "asyncio" if uvloop is None else "uvloop"
    assert type(policy).__module__.startswith(expected_loop)


@pytest.mark.asyncio
async def test_websocket_auto():
    config = Config(app=app)
    server_state = ServerState()
    protocol = AutoWebSocketsProtocol(config=config, server_state=server_state)
    expected_websockets = "WSProtocol" if websockets is None else "WebSocketProtocol"
    assert type(protocol).__name__ == expected_websockets
