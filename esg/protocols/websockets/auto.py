import asyncio
import typing

AutoWebSocketsProtocol: typing.Optional[typing.Type[asyncio.Protocol]]
try:
    import websockets  # noqa
except ImportError:  # pragma: no cover
    try:
        import wsproto  # noqa
    except ImportError:
        AutoWebSocketsProtocol = None
    else:
        from esg.protocols.websockets.wsproto_impl import WSProtocol

        AutoWebSocketsProtocol = WSProtocol
else:
    from esg.protocols.websockets.websockets_impl import WebSocketProtocol

    AutoWebSocketsProtocol = WebSocketProtocol
