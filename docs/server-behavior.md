``# Server Behavior

ESG is designed with particular attention to connection and resource management, in order to provide a robust server implementation. It aims to ensure graceful behavior to either server or client errors, and resilience to poor client behavior or denial of service attacks.

## HTTP Headers

The `Server` and `Date` headers are added to all outgoing requests.

If a `Connection: Close` header is included then ESG will close the connection after the response. Otherwise connections will stay open, pending the keep-alive timeout.

If a `Content-Length` header is included then ESG will ensure that the content length of the response body matches the value in the header, and raise an error otherwise.

If no `Content-Length` header is included then ESG will use chunked encoding for the response body, and will set a `Transfer-Encoding` header if required.

If a `Transfer-Encoding` header is included then any `Content-Length` header will be ignored.

HTTP headers are mandated to be case-insensitive. ESG will always send response headers strictly in lowercase.

---

## Flow Control

Proper flow control ensures that large amounts of data does not become buffered on the transport when either side of a connection is sending data faster than its counterpart is able to handle.

### Write flow control

If the write buffer passes a high water mark, then ESG ensures the ASGI `send` messages will only return once the write buffer has been drained below the low water mark.

### Read flow control

ESG will pause reading from a transport once the buffered request body hits a high water mark, and will only resume once `receive` has been called, or once the response has been sent.

---

## Request and Response bodies

### Response completion

Once a response has been sent, ESG will no longer buffer any remaining request body. Any later calls to `receive` will return an `http.disconnect` message.

Together with the read flow control, this behavior ensures that responses that return without reading the request body will not stream any substantial amounts of data into memory.

### Expect: 100-Continue

The `Expect: 100-Continue` header may be sent by clients to require a confirmation from the server before uploading the request body. This can be used to ensure that large request bodies are only sent once the client has confirmation that the server is willing to accept the request.

ESG ensures that any required `100 Continue` confirmations are only sent if the ASGI application calls `receive` to read the request body.

Note that that proxy configurations may not necessarily forward on `Expect: 100-Continue` headers. In particular Nginx defaults to buffering request bodies, and automatically sends `100 Continues` rather than passing the header on to the upstream server.

### HEAD requests

ESG will strip any response body from HTTP requests with the `HEAD` method.

Applications should generally treat `HEAD` requests in the same manner as `GET` requests, in order to ensure that identical headers are sent in both cases, and that any ASGI middleware that modifies the headers will operate identically in either case.

One exception to this might be if your application serves large file downloads, in which case you might wish to only generate the response headers.

---

## Timeouts

ESG provides the following timeouts:

* Keep-Alive. Defaults to 5 seconds. Between requests, connections must receive new data within this period or be disconnected.

---

## Resource Limits

ESG provides the following resource limiting:

* Concurrency. Defaults to `None`. If set, this provides a maximum number of concurrent tasks *or* open connections that should be allowed. Any new requests or connections that occur once this limit has been reached will result in a "503 Service Unavailable" response. Setting this value to a limit that you know your servers are able to support will help ensure reliable resource usage, even against significantly over-resourced servers.
* Max requests. Defaults to `None`. If set, this provides a maximum number of HTTP requests that will be serviced before terminating a process. Together with a process manager this can be used to prevent memory leaks from impacting long running processes.

---

## Server Errors

Server errors will be logged at the `error` log level. All logging defaults to being written to `stdout`.

### Exceptions

If an exception is raised by an ASGI application, and a response has not yet been sent on the connection, then a `500 Server Error` HTTP response will be sent.

### Invalid responses

ESG will ensure that ASGI applications send the correct sequence of messages, and will raise errors otherwise. This includes checking for no response sent, partial response sent, or invalid message sequences being sent.

---

## Graceful Process Shutdown

Graceful process shutdowns are particularly important during a restart period. During this period you want to:

* Start a number of new server processes to handle incoming requests, listening on the existing socket.
* Stop the previous server processes from listening on the existing socket.
* Close any connections that are not currently waiting on an HTTP response, and wait for any other connections to finalize their HTTP responses.
* Wait for any background tasks to run to completion, such as occurs when the ASGI application has sent the HTTP response, but the asyncio task has not yet run to completion.

ESG handles process shutdown gracefully, ensuring that connections are properly finalized, and all tasks have run to completion. During a shutdown period ESG will ensure that responses and tasks must still complete within the configured timeout periods.

---

## HTTP Pipelining

HTTP/1.1 provides support for sending multiple requests on a single connection, before having received each corresponding response. Servers are required to support HTTP pipelining, but it is now generally accepted to lead to implementation issues. It is not enabled on browsers, and may not necessarily be enabled on any proxies that the HTTP request passes through.

ESG supports pipelining pragmatically. It will queue up any pipelined HTTP requests, and pause reading from the underlying transport. It will not start processing pipelined requests until each response has been dealt with in turn.
``