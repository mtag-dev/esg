<p align="center">
<em>Low latency ASGI server.</em>
</p>

---

[![Build Status](https://github.com/mtag-dev/esg/workflows/Test%20Suite/badge.svg)](https://github.com/mtag-dev/esg/actions)
[![Package version](https://badge.fury.io/py/esg.svg)](https://pypi.python.org/pypi/esg)
[![PyVersions](https://img.shields.io/pypi/pyversions/python-squall.svg?color=%2334D058)](https://pypi.org/project/python-squall/)

**Documentation**: [https://esg.mtag.dev](https://esg.mtag.dev)


ESG is a speed-oriented ASGI server implementation.

Implements application server for asynchronous Python Web-frameworks.

Please read [ASGI specification] 

Supports HTTP/1.1 and WebSockets.

## Quickstart

Install using `pip`:

```shell
$ pip install esg
```

This will install ESG with minimal (pure Python) dependencies.

```shell
$ pip install esg[standard]
```

This will install ESG with "Cython-based" dependencies (where possible) and other "optional extras".

In this context, "Cython-based" means the following:

- the event loop `uvloop` will be installed and used if possible.
- the http protocol will be handled by `httptools` if possible.

Moreover, "optional extras" means that:

- the websocket protocol will be handled by `websockets` (should you want to use `wsproto` you'd need to install it manually) if possible.
- the `--reload` flag in development mode will use `watchgod`.
- windows users will have `colorama` installed for the colored logs.
- `python-dotenv` will be installed should you want to use the `--env-file` option.
- `PyYAML` will be installed to allow you to provide a `.yaml` file to `--log-config`, if desired.


#### ASGI application example

Put following code in `example.py`:

```python
async def app(scope, receive, send):
    assert scope['type'] == 'http'

    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
    })
    await send({
        'type': 'http.response.body',
        'body': b'Hello, world!',
    })
```

Run the server:

```shell
$ esg example:app
```

---

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[ASGI specification]: https://asgi.readthedocs.io/en/latest/
