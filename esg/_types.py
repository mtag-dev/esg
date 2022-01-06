import types
import typing

# WSGI
Environ = typing.MutableMapping[str, typing.Any]
ExcInfo = typing.Tuple[
    typing.Type[BaseException], BaseException, typing.Optional[types.TracebackType]
]
StartResponse = typing.Callable[
    [str, typing.Iterable[typing.Tuple[str, str]], typing.Optional[ExcInfo]], None
]
WSGIApp = typing.Callable[
    [Environ, StartResponse], typing.Union[typing.Iterable[bytes], BaseException]
]

Scope = typing.MutableMapping[str, typing.Any]
Message = typing.MutableMapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

ASGIApp = typing.Callable[[Scope, Receive, Send], typing.Awaitable[None]]
