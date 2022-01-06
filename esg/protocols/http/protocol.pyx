#cython: language_level=3

from __future__ import print_function

cimport cython
from cpython cimport (
    Py_buffer,
    PyBUF_SIMPLE,
    PyBuffer_Release,
    PyBytes_AsString,
    PyObject_GetBuffer,
)
from cpython.mem cimport PyMem_Free, PyMem_Malloc

from esg.protocols.http cimport cparser, url_cparser as uparser
from esg.protocols.http.flow_control cimport CLOSE_HEADER, HIGH_WATER_LIMIT, FlowControl
from esg.protocols.http.python cimport PyMemoryView_Check, PyMemoryView_GET_BUFFER

import asyncio
import http
import logging
import re
from urllib.parse import unquote

from esg.logging import TRACE_LOG_LEVEL
from esg.protocols.http.errors import (
    HttpParserCallbackError,
    HttpParserError,
    HttpParserInvalidMethodError,
    HttpParserInvalidStatusError,
    HttpParserInvalidURLError,
    HttpParserUpgrade,
)
from esg.protocols.http.flow_control import FlowControl
from esg.protocols.utils import (
    get_client_addr,
    get_local_addr,
    get_path_with_query_string,
    get_remote_addr,
    is_ssl,
)

HEADER_RE = re.compile(b'[\x00-\x1F\x7F()<>@,;:[]={} \t\\"]')
HEADER_VALUE_RE = re.compile(b"[\x00-\x1F\x7F]")


def _get_status_line(status_code):
    try:
        phrase = http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        phrase = b""
    return b"".join([b"HTTP/1.1 ", str(status_code).encode(), b" ", phrase, b"\r\n"])


STATUS_LINE = {
    status_code: _get_status_line(status_code) for status_code in range(100, 600)
}


SERVICE_UNAVAILABLE = (
    b"HTTP/1.1 503 Service Unavailable\r\n"
    b"content-type: text/plain; charset=utf-8\r\n"
    b"connection: close\r\n"
    b"content-length: 19\r\n\r\n"
    b"Service Unavailable"
)


cdef class Protocol:

    def __cinit__(self, config, server_state, on_connection_lost = None, _loop=None):
        self._cparser = <cparser.llhttp_t*> \
                                PyMem_Malloc(sizeof(cparser.llhttp_t))
        if self._cparser is NULL:
            raise MemoryError()

        self._csettings = <cparser.llhttp_settings_t*> \
                                PyMem_Malloc(sizeof(cparser.llhttp_settings_t))
        if self._csettings is NULL:
            raise MemoryError()

        cparser.llhttp_settings_init(self._csettings)

        cparser.llhttp_init(self._cparser, cparser.HTTP_REQUEST, self._csettings)
        self._cparser.data = <void*>self

        self._current_header_name = None
        self._current_header_value = None

        self.expect_100_continue = False
        self.headers = []
        self._scope = {}
        self.url = b""

        # Callbacks
        self._csettings.on_header_field = cb_on_header_field
        self._csettings.on_header_value = cb_on_header_value
        self._csettings.on_url = cb_on_url
        self._csettings.on_headers_complete = cb_on_headers_complete
        self._csettings.on_message_complete = cb_on_message_complete
        self._csettings.on_body = cb_on_body

        if not config.loaded:
            config.load()

        self.config = config
        self.app = config.loaded_app
        self.on_connection_lost = on_connection_lost
        self._loop = _loop or asyncio.get_event_loop()
        self.logger = logging.getLogger("esg.error")
        self.access_logger = logging.getLogger("esg.access")
        self.access_log = self.access_logger.hasHandlers()
        self.ws_protocol_class = config.ws_protocol_class
        self.root_path = config.root_path
        self.limit_concurrency = config.limit_concurrency

        # Timeouts
        self.timeout_keep_alive = config.timeout_keep_alive
        self.keep_alive = bool(self.timeout_keep_alive)

        # Global state
        self.server_state = server_state
        self.connections = server_state.connections
        self.tasks = server_state.tasks
        self.default_headers = server_state.default_headers

        # Per-connection state
        self._transport = None
        self.flow = None
        self.server = None
        self.client = None
        self.scheme = None

        ## From cycle
        self.message_event = self._loop.create_future()
        self.run_asgi_event = self._loop.create_future()
        self.worker = self._loop.create_task(self.run_asgi())
        self.tasks.add(self.worker)
        self.worker.add_done_callback(self.tasks.discard)

        self.disconnected = False
        self.body = b""
        self.more_body = True

        # Response state
        self.response_started = False
        self.response_complete = False
        self.chunked_encoding = None
        self.expected_content_length = 0

        self.idle = 0
        self.request_processing = False

        self._last_error = None

    @property
    def loop(self):
        return self._loop

    @property
    def transport(self):
        return self._transport

    @property
    def scope(self):
        return self._scope

    def __dealloc__(self):
        PyMem_Free(self._cparser)
        PyMem_Free(self._csettings)

    cdef inline _maybe_call_on_header(self):
        cdef bytes header_name

        if self._current_header_value is not None:
            header_name = self._current_header_name.lower()
            if header_name == b"expect" and self._current_header_value.lower() == b"100-continue":
                self.expect_100_continue = True

            self.headers.append((header_name, self._current_header_value))
            self._current_header_name = self._current_header_value = None

    cdef inline _on_header_field(self, bytes field):
        self._maybe_call_on_header()
        if self._current_header_name is None:
            self._current_header_name = field
        else:
            self._current_header_name += field

    cdef inline _on_header_value(self, bytes val):
        if self._current_header_value is None:
            self._current_header_value = val
        else:
            self._current_header_value += val

    cdef inline _on_headers_complete(self):
        self._maybe_call_on_header()

        if self.limit_concurrency is not None and len(self.connections) >= self.limit_concurrency:
            if not self._transport.is_closing():
                self._transport.write(SERVICE_UNAVAILABLE)
                self._transport.close()
                return

        if self._cparser.http_major != 1 or self._cparser.http_minor != 1:
            self._scope["http_version"] = '{}.{}'.format(
                self._cparser.http_major,
                self._cparser.http_minor
            )

        if self._cparser.upgrade == 1:
            return

        self.response_started = self.response_complete = False

        if not self.run_asgi_event.done():
            self.run_asgi_event.set_result(True)

    cdef inline _on_chunk_header(self):
        if (self._current_header_value is not None or
            self._current_header_name is not None):
            raise HttpParserError('invalid headers state')

        if self._proto_on_chunk_header is not None:
            self._proto_on_chunk_header()

    # cdef _on_chunk_complete(self):
    #     self._maybe_call_on_header()
    #
    #     if self._proto_on_chunk_complete is not None:
    #         self._proto_on_chunk_complete()

    cdef _on_url(self, url):
        self.request_processing = True
        cdef:
            Py_buffer py_buf
            char* buf_data
            uparser.http_parser_url* parsed
            int res
            bytes raw_path = None
            bytes query = None
            bytes method = None
            str path = None
            int off
            int ln
            cparser.llhttp_t * parser = self._cparser

        parsed = <uparser.http_parser_url*> \
                            PyMem_Malloc(sizeof(uparser.http_parser_url))
        uparser.http_parser_url_init(parsed)
        PyObject_GetBuffer(url, &py_buf, PyBUF_SIMPLE)

        try:
            buf_data = <char*>py_buf.buf
            res = uparser.http_parser_parse_url(buf_data, py_buf.len, 0, parsed)

            if res == 0:
                if parsed.field_set & (1 << uparser.UF_PATH):
                    off = parsed.field_data[<int>uparser.UF_PATH].off
                    ln = parsed.field_data[<int>uparser.UF_PATH].len
                    raw_path = buf_data[off:off+ln]

                if parsed.field_set & (1 << uparser.UF_QUERY):
                    off = parsed.field_data[<int>uparser.UF_QUERY].off
                    ln = parsed.field_data[<int>uparser.UF_QUERY].len
                    query = buf_data[off:off+ln]

                method = cparser.llhttp_method_name( < cparser.llhttp_method_t > parser.method)
                path = raw_path.decode("ascii")
                if "%" in path:
                    path = unquote(path)
                self.url = url
                self.expect_100_continue = False
                self.headers = []
                self._scope = {
                    # Per-request state
                    "method": method.decode(),
                    "path": path,
                    "raw_path": raw_path,
                    "query_string": query or b"",
                    "headers": self.headers,
                    # Extract per-connection state
                    **self._connection_scope,
                }

                self.body = b""
                self.more_body = True

                # Response state
                self.response_started = False
                self.response_complete = False
                self.chunked_encoding = None
                self.expected_content_length = 0
            else:
                raise HttpParserInvalidURLError("invalid url {!r}".format(url))
        finally:
            PyBuffer_Release(&py_buf)
            PyMem_Free(parsed)


    ### Public API ###

    # Protocol interface
    def connection_made(self, transport):
        self.connections.add(self)

        self._transport = transport
        self.flow = FlowControl(transport)
        self.server = get_local_addr(transport)
        self.client = get_remote_addr(transport)
        self.scheme = "https" if is_ssl(transport) else "http"
        #
        self._connection_scope = {
            # Per connection - state
            "type": "http",
            "asgi": {"version": self.config.asgi_version, "spec_version": "2.1"},
            "http_version": "1.1",
            "server": self.server,
            "client": self.client,
            "scheme": self.scheme,
            "root_path": self.root_path,
        }

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.client) if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sHTTP connection made", prefix)

    def connection_lost(self, exc):
        self.connections.discard(self)

        if not self.run_asgi_event.done():
            self.run_asgi_event.set_result(False)

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.client) if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sHTTP connection lost", prefix)

        self.disconnected = True

        if not self.message_event.done():
            self.message_event.set_result(True)

        if self.flow is not None:
            self.flow.resume_writing()
        if exc is None:
            if not self._transport.is_closing():
                self._transport.close()

        if self.on_connection_lost is not None:
            self.on_connection_lost()

    def eof_received(self):
        pass

    def handle_upgrade(self):
        if not self.run_asgi_event.done():
            self.run_asgi_event.set_result(False)

        upgrade_value = None
        for name, value in self.headers:
            if name == b"upgrade":
                upgrade_value = value.lower()

        if upgrade_value != b"websocket" or self.ws_protocol_class is None:
            msg = "Unsupported upgrade request."
            self.logger.warning(msg)

            from esg.protocols.websockets.auto import AutoWebSocketsProtocol

            if AutoWebSocketsProtocol is None:
                msg = "No supported WebSocket library detected. Please use 'pip install uvicorn[standard]', or install 'websockets' or 'wsproto' manually."  # noqa: E501
                self.logger.warning(msg)

            content = [STATUS_LINE[400]]
            for name, value in self.default_headers:
                content.extend([name, b": ", value, b"\r\n"])
            content.extend(
                [
                    b"content-type: text/plain; charset=utf-8\r\n",
                    b"content-length: " + str(len(msg)).encode("ascii") + b"\r\n",
                    b"connection: close\r\n",
                    b"\r\n",
                    msg.encode("ascii"),
                ]
            )
            self._transport.write(b"".join(content))
            if not self._transport.is_closing():
                self._transport.close()
            return

        if self.logger.level <= TRACE_LOG_LEVEL:
            prefix = "%s:%d - " % tuple(self.client) if self.client else ""
            self.logger.log(TRACE_LOG_LEVEL, "%sUpgrading to WebSocket", prefix)

        self.connections.discard(self)

        method = self._scope["method"].encode()
        output = [method, b" ", self.url, b" HTTP/1.1\r\n"]
        for name, value in self._scope["headers"]:
            output += [name, b": ", value, b"\r\n"]
        output.append(b"\r\n")
        protocol = self.ws_protocol_class(
            config=self.config,
            server_state=self.server_state,
            on_connection_lost=self.on_connection_lost,
        )
        protocol.connection_made(self._transport)
        protocol.data_received(b"".join(output))
        self._transport.set_protocol(protocol)

    cdef inline _on_body(self, bytes body):
        if self._cparser.upgrade == 1 or self.response_complete:
            return
        self.body += body
        if len(self.body) > HIGH_WATER_LIMIT:
            self.flow.pause_reading()
        if not self.message_event.done():
            self.message_event.set_result(True)

    cdef inline _on_message_complete(self):
        if self._cparser.upgrade == 1 or self.response_complete:
            return
        self.more_body = False
        if not self.message_event.done():
            self.message_event.set_result(True)

    def shutdown(self):
        """
        Called by the server to commence a graceful shutdown.
        """
        if not self.request_processing:
            if not self._transport.is_closing():
                self._transport.close()
        else:
            self.keep_alive = False

        if not self.run_asgi_event.done():
            self.run_asgi_event.set_result(False)

    def pause_writing(self):
        """
        Called by the transport when the write buffer exceeds the high water mark.
        """
        self.flow.pause_writing()

    def resume_writing(self):
        """
        Called by the transport when the write buffer drops below the low water mark.
        """
        self.flow.resume_writing()

    def is_expired(self, now):
        if self.request_processing:
            return False
        return self.idle > 0 and now - self.idle > self.timeout_keep_alive

    def data_received(self, data):
        self.idle = 0

        cdef:
            size_t data_len
            cparser.llhttp_errno_t err
            Py_buffer *buf
            bint owning_buf = False
            char* err_pos

        if PyMemoryView_Check(data):
            buf = PyMemoryView_GET_BUFFER(data)
            data_len = <size_t>buf.len
            err = cparser.llhttp_execute(
                self._cparser,
                <char*>buf.buf,
                data_len)

        else:
            buf = &self.py_buf
            PyObject_GetBuffer(data, buf, PyBUF_SIMPLE)
            owning_buf = True
            data_len = <size_t>buf.len

            err = cparser.llhttp_execute(
                self._cparser,
                <char*>buf.buf,
                data_len)

        try:
            if self._cparser.upgrade == 1 and err == cparser.HPE_PAUSED_UPGRADE:
                err_pos = cparser.llhttp_get_error_pos(self._cparser)

                # Immediately free the parser from "error" state, simulating
                # http-parser behavior here because 1) we never had the API to
                # allow users manually "resume after upgrade", and 2) the use
                # case for resuming parsing is very rare.
                cparser.llhttp_resume_after_upgrade(self._cparser)

                # The err_pos here is specific for the input buf. So if we ever
                # switch to the llhttp behavior (re-raise HttpParserUpgrade for
                # successive calls to feed_data() until resume_after_upgrade is
                # called), we have to store the result and keep our own state.
                #raise HttpParserUpgrade(err_pos - <char*>buf.buf)
                self.handle_upgrade()
                return
        finally:
            if owning_buf:
                PyBuffer_Release(buf)

        if err != cparser.HPE_OK:
            ex = parser_error_from_errno(
                self._cparser,
                <cparser.llhttp_errno_t> self._cparser.error)
            if isinstance(ex, HttpParserCallbackError):
                if self._last_error is not None:
                    ex.__context__ = self._last_error
                    self._last_error = None
            msg = "Invalid HTTP request received."
            self.logger.warning(msg, exc_info=ex)
            if not self._transport.is_closing():
                self._transport.close()

    # ASGI exception wrapper
    async def run_asgi(self):
        while not self.disconnected:
            try:
                run_app = await self.run_asgi_event
                if not run_app:
                    return
                
                self.run_asgi_event = self._loop.create_future()

                result = await self.app(self._scope, self.receive, self.send)
            except asyncio.CancelledError:
                return
            except BaseException as exc:
                msg = "Exception in ASGI application\n"
                self.logger.error(msg, exc_info=exc)
                if not self.response_started:
                    await self.send_500_response()
                else:
                    if not self._transport.is_closing():
                        self._transport.close()
                return
            else:
                if result is not None:
                    msg = "ASGI callable should return None, but returned '%s'."
                    self.logger.error(msg, result)
                    if not self._transport.is_closing():
                        self._transport.close()
                    return
                elif not self.response_started and not self.disconnected:
                    msg = "ASGI callable returned without starting response."
                    self.logger.error(msg)
                    await self.send_500_response()
                    return
                elif not self.response_complete and not self.disconnected:
                    msg = "ASGI callable returned without completing response."
                    self.logger.error(msg)
                    if not self._transport.is_closing():
                        self._transport.close()
                    return
                else:
                    if not self.keep_alive:
                        return

    #            self.on_response = None

    async def send_500_response(self):
        await self.send(
            {
                "type": "http.response.start",
                "status": 500,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"connection", b"close"),
                ],
            }
        )
        await self.send(
            {"type": "http.response.body", "body": b"Internal Server Error"}
        )


    # ASGI interface
    async def send(self, dict message):
        cdef str message_type = message["type"]
        cdef int status_code
        cdef list headers
        cdef bytes name
        cdef bytes value
        cdef str msg
        cdef list content

        if self.flow.write_paused and not self.disconnected:
            await self.flow.drain()

        if self.disconnected:
            return

        if not self.response_started:
            # Sending response status line and headers
            if message_type != "http.response.start":
                msg = "Expected ASGI message 'http.response.start', but got '%s'."
                raise RuntimeError(msg % message_type)

            self.response_started = True
            self.expect_100_continue = False

            status_code = message["status"]
            headers = self.default_headers + list(message.get("headers", []))

            if CLOSE_HEADER in self._scope["headers"] and CLOSE_HEADER not in headers:
                headers = headers + [CLOSE_HEADER]

            if self.access_log:
                self.access_logger.info(
                    '%s - "%s %s HTTP/%s" %d',
                    get_client_addr(self._scope),
                    self._scope["method"],
                    get_path_with_query_string(self._scope),
                    self._scope["http_version"],
                    status_code,
                )

            # Write response status line and headers
            self._transport.write(STATUS_LINE[status_code])

            for name, value in headers:
                # Should be active only in development mode.
                # if HEADER_RE.search(name):
                #     raise RuntimeError("Invalid HTTP header name.")
                # if HEADER_VALUE_RE.search(value):
                #     raise RuntimeError("Invalid HTTP header value.")

                name = name.lower()
                if name == b"content-length" and self.chunked_encoding is None:
                    self.expected_content_length = int(value)
                    self.chunked_encoding = False
                elif name == b"transfer-encoding" and value.lower() == b"chunked":
                    self.expected_content_length = 0
                    self.chunked_encoding = True
                elif name == b"connection" and value.lower() == b"close":
                    self.keep_alive = False
                self._transport.writelines((name, b": ", value, b"\r\n"))

            if (
                    self.chunked_encoding is None
                    and self._scope["method"] != "HEAD"
                    and status_code not in (204, 304)
            ):
                # Neither content-length nor transfer-encoding specified
                self.chunked_encoding = True
                self._transport.write(b"transfer-encoding: chunked\r\n\r\n")
            else:
                self._transport.write(b"\r\n")

        elif not self.response_complete:
            # Sending response body
            if message_type != "http.response.body":
                msg = "Expected ASGI message 'http.response.body', but got '%s'."
                raise RuntimeError(msg % message_type)

            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            # Write response body
            if self._scope["method"] == "HEAD":
                self.expected_content_length = 0
            elif self.chunked_encoding:
                if body and not more_body:
                    self._transport.writelines(
                        (b"%x\r\n" % len(body), body, b"\r\n0\r\n\r\n")
                    )
                elif body and more_body:
                    self._transport.writelines(
                        (b"%x\r\n" % len(body), body, b"\r\n")
                    )
                elif not body and not more_body:
                    self._transport.write(b"0\r\n\r\n")
            else:
                num_bytes = len(body)
                if self.expected_content_length:
                    if num_bytes > self.expected_content_length:
                        raise RuntimeError("Response content longer than Content-Length")
                    else:
                        self.expected_content_length -= num_bytes
                self._transport.write(body)

            # Handle response completion
            if not more_body:
                if self.expected_content_length != 0:
                    raise RuntimeError("Response content shorter than Content-Length")
                self.response_complete = True
                self.request_processing = False

                if self.flow.read_paused:
                    self.flow.resume_reading()

                if not self.message_event.done():
                    self.message_event.set_result(True)

                if not self.keep_alive and not self._transport.is_closing():
                    if self.flow.write_paused:
                        await self.flow.drain()
                    self._transport.close()

                self.server_state.total_requests += 1
                self.idle = self.server_state.time

        else:
            # Response already sent
            msg = "Unexpected ASGI message '%s' sent, after response already completed."
            raise RuntimeError(msg % message_type)

    async def receive(self):
        if self.expect_100_continue and not self._transport.is_closing():
            self._transport.write(b"HTTP/1.1 100 Continue\r\n\r\n")
            self.expect_100_continue = False

        if not self.disconnected and not self.response_complete:
            if self.flow.read_paused:
                self.flow.resume_reading()
            await self.message_event
            self.message_event = self._loop.create_future()

        if self.disconnected or self.response_complete:
            message = {"type": "http.disconnect"}
        else:
            message = {
                "type": "http.request",
                "body": self.body,
                "more_body": self.more_body,
            }
            self.body = b""

        return message


cdef inline int cb_on_message_begin(cparser.llhttp_t* parser) except -1:
    cdef Protocol pyparser = < Protocol > parser.data
    try:
        pyparser._proto_on_message_begin()
    except BaseException as ex:
        pyparser._last_error = ex
        return -1
    else:
        return 0


cdef inline int cb_on_url(cparser.llhttp_t* parser,
                   const char *at, size_t length) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_url(at[:length])
    except BaseException as ex:
        cparser.llhttp_set_error_reason(parser, "`on_url` callback error")
        pyparser._last_error = ex
        return cparser.HPE_USER
    else:
        return 0


cdef inline int cb_on_header_field(cparser.llhttp_t* parser,
                            const char *at, size_t length) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_header_field(at[:length])
    except BaseException as ex:
        cparser.llhttp_set_error_reason(parser, "`on_header_field` callback error")
        pyparser._last_error = ex
        return cparser.HPE_USER
    else:
        return 0


cdef inline int cb_on_header_value(cparser.llhttp_t* parser,
                            const char *at, size_t length) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_header_value(at[:length])
    except BaseException as ex:
        cparser.llhttp_set_error_reason(parser, "`on_header_value` callback error")
        pyparser._last_error = ex
        return cparser.HPE_USER
    else:
        return 0


cdef inline int cb_on_headers_complete(cparser.llhttp_t* parser) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_headers_complete()
    except BaseException as ex:
        pyparser._last_error = ex
        return -1
    else:
        if pyparser._cparser.upgrade:
            return 1
        else:
            return 0


cdef inline int cb_on_body(cparser.llhttp_t* parser,
                    const char *at, size_t length) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_body(at[:length])
    except BaseException as ex:
        cparser.llhttp_set_error_reason(parser, "`on_body` callback error")
        pyparser._last_error = ex
        return cparser.HPE_USER
    else:
        return 0


cdef inline int cb_on_message_complete(cparser.llhttp_t* parser) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_message_complete()
    except BaseException as ex:
        pyparser._last_error = ex
        return -1
    else:
        return 0


cdef inline int cb_on_chunk_header(cparser.llhttp_t* parser) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_chunk_header()
    except BaseException as ex:
        pyparser._last_error = ex
        return -1
    else:
        return 0


cdef inline int cb_on_chunk_complete(cparser.llhttp_t* parser) except -1:
    cdef Protocol pyparser = <Protocol>parser.data
    try:
        pyparser._on_chunk_complete()
    except BaseException as ex:
        pyparser._last_error = ex
        return -1
    else:
        return 0


cdef inline parser_error_from_errno(cparser.llhttp_t* parser, cparser.llhttp_errno_t errno):
    cdef bytes reason = cparser.llhttp_get_error_reason(parser)

    if errno in (cparser.HPE_CB_MESSAGE_BEGIN,
                 cparser.HPE_CB_HEADERS_COMPLETE,
                 cparser.HPE_CB_MESSAGE_COMPLETE,
                 cparser.HPE_CB_CHUNK_HEADER,
                 cparser.HPE_CB_CHUNK_COMPLETE,
                 cparser.HPE_USER):
        cls = HttpParserCallbackError

    elif errno == cparser.HPE_INVALID_STATUS:
        cls = HttpParserInvalidStatusError

    elif errno == cparser.HPE_INVALID_METHOD:
        cls = HttpParserInvalidMethodError

    elif errno == cparser.HPE_INVALID_URL:
        cls = HttpParserInvalidURLError

    else:
        cls = HttpParserError

    return cls(reason.decode('latin-1'))
