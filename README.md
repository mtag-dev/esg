<p align="center">
    <a href="https://github.com/mtag-dev/esg/">
        <img src="https://github.com/mtag-dev/esg/raw/feature/ESG-3-documentation/docs/img/esg.png" alt="Enhanced Service Gateway" width="300"/>
    </a>
</p>
<p align="center">
<em>Enhanced Service Gateway.</em>
</p>


[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![License](https://img.shields.io/badge/License-BSD_3--Clause-blue.svg)](https://github.com/mtag-dev/esg/blob/master/LICENSE.md)
[![Coverage](https://img.shields.io/codecov/c/github/mtag-dev/esg?color=%2334D058)](https://pypi.org/project/esg/)
[![Test](https://github.com/mtag-dev/esg/workflows/Test%20Suite/badge.svg?event=push&branch=master)](https://github.com/mtag-dev/esg/actions/workflows/test-suite.yml)
[![PyPi](https://img.shields.io/pypi/v/esg?color=%2334D058&label=pypi%20package)](https://pypi.org/project/esg/)
[![PyVersions](https://img.shields.io/pypi/pyversions/esg.svg?color=%2334D058)](https://pypi.org/project/esg/)

---

# Introduction

ESG is a speed-oriented [ASGI][asgi] server implementation with HTTP/1.1 and WebSockets support.

Is a hard fork of the awesome [uvicorn] project.

Protocol implementation based on:
 - [llhttp] - For HTTP payload
 - [http-parser] - For URL parsing
 - [httptools] - Clean and fast binding for the previous two. ESG Cython part development started from its forking.

# Performance

Speed comparison ESG vs Uvicorn 

```shell
PS > docker-compose run --rm bench-esg
Running 15s test @ http://esg:8000/
  4 threads and 64 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     2.15ms  390.13us   9.51ms   92.82%
    Req/Sec     7.47k   455.23     9.39k    68.00%
  445749 requests in 15.01s, 66.32MB read
Requests/sec:  29694.49
Transfer/sec:      4.42MB
PS > docker-compose run --rm bench-uvicorn
Running 15s test @ http://uvicorn:8000/
  4 threads and 64 connections
  Thread Stats   Avg      Stdev     Max   +/- Stdev
    Latency     4.03ms    0.85ms  16.28ms   91.16%
    Req/Sec     3.99k   376.72     4.53k    82.67%
  238272 requests in 15.01s, 36.36MB read
Requests/sec:  15874.17
Transfer/sec:      2.42MB
```

## Quickstart

Install using `pip`:

```shell
$ pip install esg[standard]
```

`standart` extra will also install:
 - [uvloop] if applicable to system arch
 - [websockets] if available *
 - [watchgod] for development's mode flag `--reload`
 - [PyYAML] for using `*.yaml` config files in `--log-config` parameter
 - [python-dotenv] for enabling `--env-file` parameter functionality
 - [colorama] for Windows users

*If you want use [wsproto] instead of [websockets]  you'd need to install it manually

### Running simple ASGI application 

Create an application, in `example.py`:

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
        'more_body': False
     })
```

Run the server:

```shell
$ esg example:app
```

---

## Usage

The ESG command line tool is the easiest way to run your application...

### Command line options

<!-- :cli_usage: -->
```
$ esg --help
Usage: esg [OPTIONS] APP

Options:
  --host TEXT                     Bind socket to this host.  [default:
                                  127.0.0.1]
  --port INTEGER                  Bind socket to this port.  [default: 8000]
  --uds TEXT                      Bind to a UNIX domain socket.
  --fd INTEGER                    Bind to socket from this file descriptor.
  --reload                        Enable auto-reload.
  --reload-dir PATH               Set reload directories explicitly, instead
                                  of using the current working directory.
  --reload-include TEXT           Set glob patterns to include while watching
                                  for files. Includes '*.py' by default; these
                                  defaults can be overridden in `--reload-
                                  exclude`.
  --reload-exclude TEXT           Set glob patterns to exclude while watching
                                  for files. Includes '.*, .py[cod], .sw.*,
                                  ~*' by default; these defaults can be
                                  overridden in `--reload-include`.
  --reload-delay FLOAT            Delay between previous and next check if
                                  application needs to be. Defaults to 0.25s.
                                  [default: 0.25]
  --workers INTEGER               Number of worker processes. Defaults to the
                                  $WEB_CONCURRENCY environment variable if
                                  available, or 1. Not valid with --reload.
  --loop [auto|asyncio|uvloop]    Event loop implementation.  [default: auto]
  --ws [auto|none|websockets|wsproto]
                                  WebSocket protocol implementation.
                                  [default: auto]
  --ws-max-size INTEGER           WebSocket max size message in bytes
                                  [default: 16777216]
  --ws-ping-interval FLOAT        WebSocket ping interval  [default: 20.0]
  --ws-ping-timeout FLOAT         WebSocket ping timeout  [default: 20.0]
  --lifespan [auto|on|off]        Lifespan implementation.  [default: auto]
  --interface [auto|asgi3|asgi2|wsgi]
                                  Select ASGI3, ASGI2, or WSGI as the
                                  application interface.  [default: auto]
  --env-file PATH                 Environment configuration file.
  --log-config PATH               Logging configuration file. Supported
                                  formats: .ini, .json, .yaml.
  --log-level [critical|error|warning|info|debug|trace]
                                  Log level. [default: info]
  --access-log / --no-access-log  Enable/Disable access log.
  --use-colors / --no-use-colors  Enable/Disable colorized logging.
  --proxy-headers / --no-proxy-headers
                                  Enable/Disable X-Forwarded-Proto,
                                  X-Forwarded-For, X-Forwarded-Port to
                                  populate remote address info.
  --server-header / --no-server-header
                                  Enable/Disable default Server header.
  --date-header / --no-date-header
                                  Enable/Disable default Date header.
  --forwarded-allow-ips TEXT      Comma seperated list of IPs to trust with
                                  proxy headers. Defaults to the
                                  $FORWARDED_ALLOW_IPS environment variable if
                                  available, or '127.0.0.1'.
  --root-path TEXT                Set the ASGI 'root_path' for applications
                                  submounted below a given URL path.
  --limit-concurrency INTEGER     Maximum number of concurrent connections or
                                  tasks to allow, before issuing HTTP 503
                                  responses.
  --backlog INTEGER               Maximum number of connections to hold in
                                  backlog
  --limit-max-requests INTEGER    Maximum number of requests to service before
                                  terminating the process.
  --timeout-keep-alive INTEGER    Close Keep-Alive connections if no new data
                                  is received within this timeout.  [default:
                                  5]
  --ssl-keyfile TEXT              SSL key file
  --ssl-certfile TEXT             SSL certificate file
  --ssl-keyfile-password TEXT     SSL keyfile password
  --ssl-version INTEGER           SSL version to use (see stdlib ssl module's)
                                  [default: 17]
  --ssl-cert-reqs INTEGER         Whether client certificate is required (see
                                  stdlib ssl module's)  [default: 0]
  --ssl-ca-certs TEXT             CA certificates file
  --ssl-ciphers TEXT              Ciphers to use (see stdlib ssl module's)
                                  [default: TLSv1]
  --header TEXT                   Specify custom default HTTP response headers
                                  as a Name:Value pair
  --version                       Display the esg version and exit.
  --app-dir TEXT                  Look for APP in the specified directory, by
                                  adding this to the PYTHONPATH. Defaults to
                                  the current working directory.  [default: .]
  --factory                       Treat APP as an application factory, i.e. a
                                  () -> <ASGI app> callable.  [default: False]
  --help                          Show this message and exit.
```

### Running programmatically

To run ESG directly from your application

**example.py**:

```python
import esg

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
        'more_body': False
     })

if __name__ == "__main__":
    esg.run("example:app", host="127.0.0.1", port=5000, log_level="info")
```

### Running with Gunicorn

[Gunicorn][gunicorn] is a mature, fully featured server and process manager.

ESG includes a Gunicorn worker class allowing you to run ASGI applications,
with all of ESG's performance benefits, while also giving you Gunicorn's
fully-featured process management.

This allows you to increase or decrease the number of worker processes on the
fly, restart worker processes gracefully, or perform server upgrades without downtime.

For production deployments we recommend using gunicorn with the ESG worker class.

```
gunicorn example:app -w 4 -k esg.workers.ESGWorker
```

For more information, see the [deployment documentation](deployment.md).

### Application factories

The `--factory` flag allows loading the application from a factory function, rather than an application instance directly. The factory will be called with no arguments and should return an ASGI application.

**example.py**:

```python
def create_app():
    app = ...
    return app
```

```shell
$ esg --factory example:create_app
```

## The ASGI interface

ESG uses the [ASGI specification][asgi] for interacting with an ASGI application.

The application should expose an async callable which takes three arguments:

* `scope` - A dictionary containing information about the incoming connection.
* `receive` - A channel on which to receive incoming messages from the server.
* `send` - A channel on which to send outgoing messages to the server.

Two common patterns you might use are either function-based applications:

```python
async def app(scope, receive, send):
    assert scope['type'] == 'http'
    ...
```

Or instance-based applications:

```python
class App:
    async def __call__(self, scope, receive, send):
        assert scope['type'] == 'http'
        ...

app = App()
```

It's good practice for applications to raise an exception on scope types
that they do not handle.

The content of the `scope` argument, and the messages expected by `receive` and `send` depend on the protocol being used.

The format for HTTP messages is described in the [ASGI HTTP Message format][asgi-http].

### HTTP Scope

An incoming HTTP request might have a connection `scope` like this:

```python
{
    'type': 'http.request',
    'scheme': 'http',
    'root_path': '',
    'server': ('127.0.0.1', 8000),
    'http_version': '1.1',
    'method': 'GET',
    'path': '/',
    'headers': [
        [b'host', b'127.0.0.1:8000'],
        [b'user-agent', b'curl/7.51.0'],
        [b'accept', b'*/*']
    ]
}
```

### HTTP Messages

The instance coroutine communicates back to the server by sending messages to the `send` coroutine.

```python
await send({
    'type': 'http.response.start',
    'status': 200,
    'headers': [
        [b'content-type', b'text/plain'],
    ]
})
await send({
    'type': 'http.response.body',
    'body': b'Hello, world!',
})
```

### Requests & responses

Here's an example that displays the method and path used in the incoming request:

```python
async def app(scope, receive, send):
    """
    Echo the method and path back in an HTTP response.
    """
    assert scope['type'] == 'http'

    body = f'Received {scope["method"]} request to {scope["path"]}'
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ]
    })
    await send({
        'type': 'http.response.body',
        'body': body.encode('utf-8'),
    })
```

### Reading the request body

You can stream the request body without blocking the asyncio task pool,
by fetching messages from the `receive` coroutine.

```python
async def read_body(receive):
    """
    Read and return the entire body from an incoming ASGI message.
    """
    body = b''
    more_body = True

    while more_body:
        message = await receive()
        body += message.get('body', b'')
        more_body = message.get('more_body', False)

    return body


async def app(scope, receive, send):
    """
    Echo the request body back in an HTTP response.
    """
    body = await read_body(receive)
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ]
    })
    await send({
        'type': 'http.response.body',
        'body': body,
    })
```

### Streaming responses

You can stream responses by sending multiple `http.response.body` messages to
the `send` coroutine.

```python
import asyncio


async def app(scope, receive, send):
    """
    Send a slowly streaming HTTP response back to the client.
    """
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ]
    })
    for chunk in [b'Hello', b', ', b'world!']:
        await send({
            'type': 'http.response.body',
            'body': chunk,
            'more_body': True
        })
        await asyncio.sleep(1)
    await send({
        'type': 'http.response.body',
        'body': b'',
    })
```

---

## Alternative ASGI servers

### Uvicorn

The most famous ASGI server. ESG development started from hard-forking of exactly Uvicorn.

Uvicorn has a clean codebase and superior fast performance.

```
$ pip install uvicorn
$ uvicorn app:App
```

### Daphne

The first ASGI server implementation, originally developed to power Django Channels, is [the Daphne webserver][daphne].

It is run widely in production, and supports HTTP/1.1, HTTP/2, and WebSockets.

Any of the example applications given here can equally well be run using `daphne` instead.

```
$ pip install daphne
$ daphne app:App
```

### Hypercorn

[Hypercorn][hypercorn] was initially part of the Quart web framework, before
being separated out into a standalone ASGI server.

Hypercorn supports HTTP/1.1, HTTP/2, and WebSockets.

```
$ pip install hypercorn
$ hypercorn app:App
```

---

## ASGI frameworks

You can use ESG, Uvicorn, Daphne, or Hypercorn to run any ASGI framework.

For small services you can also write ASGI applications directly.

### Squall

[Squall](https://github.com/mtag-dev/squall) framework which looks ahead.

High performance API framework.

### Starlette

[Starlette](https://github.com/encode/starlette) is a lightweight ASGI framework/toolkit.

It is ideal for building high performance asyncio services, and supports both HTTP and WebSockets.

### Django Channels

The ASGI specification was originally designed for use with [Django Channels](https://channels.readthedocs.io/en/latest/).

Channels is a little different to other ASGI frameworks in that it provides
an asynchronous frontend onto a threaded-framework backend. It allows Django
to support WebSockets, background tasks, and long-running connections,
with application code still running in a standard threaded context.

### Quart

[Quart](https://pgjones.gitlab.io/quart/) is a Flask-like ASGI web framework.

### FastAPI

[**FastAPI**](https://github.com/tiangolo/fastapi) is an API framework based on **Starlette** and **Pydantic**, heavily inspired by previous server versions of **APIStar**.

You write your API function parameters with Python 3.6+ type declarations and get automatic data conversion, data validation, OpenAPI schemas (with JSON Schemas) and interactive API documentation UIs.

### BlackSheep

[BlackSheep](https://www.neoteroi.dev/blacksheep/) is a web framework based on ASGI, inspired by Flask and ASP.NET Core.

Its most distinctive features are built-in support for dependency injection, automatic binding of parameters by request handler's type annotations, and automatic generation of OpenAPI documentation and Swagger UI.


[llhttp]: https://github.com/nodejs/llhttp
[http-parser]: https://github.com/nodejs/http-parser
[uvicorn]: https://github.com/encode/uvicorn
[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[gunicorn]: http://gunicorn.org/
[pypy]: https://pypy.org/
[asgi]: https://asgi.readthedocs.io/en/latest/
[asgi-http]: https://asgi.readthedocs.io/en/latest/specs/www.html
[daphne]: https://github.com/django/daphne
[hypercorn]: https://gitlab.com/pgjones/hypercorn
[uvloop_docs]: https://uvloop.readthedocs.io/
[httptools_vs_h11]: https://github.com/python-hyper/h11/issues/9
[websockets]: https://pypi.org/project/websockets/
[wsproto]: https://pypi.org/project/wsproto/
[watchgod]: https://pypi.org/project/watchgod/
[PyYAML]: https://pypi.org/project/PyYAML/
[python-dotenv]: https://pypi.org/project/python-dotenv/
[colorama]: https://pypi.org/project/colorama/
