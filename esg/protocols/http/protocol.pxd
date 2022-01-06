#cython: language_level=3


from cpython cimport Py_buffer

from esg.protocols.http.flow_control cimport FlowControl

from . cimport cparser


cdef class Protocol:

    cdef:
        cparser.llhttp_t* _cparser
        cparser.llhttp_settings_t* _csettings

        bytes _current_header_name
        bytes _current_header_value

        _proto_on_chunk_header, _proto_on_chunk_complete, _proto_on_message_begin

        object _last_error

        Py_buffer py_buf

        # proto
        object config
        object app

        on_connection_lost, _loop, logger, access_logger, access_log, ws_protocol_class
        limit_concurrency, timeout_keep_alive
        server_state, connections, tasks, _transport, server, client
        scheme, message_event, run_asgi_event, worker, chunked_encoding

        FlowControl flow
        list default_headers

        str root_path

        int expect_100_continue
        list headers
        bytes url
        dict _scope
        dict _connection_scope
        int response_started
        int response_complete
        int expected_content_length


        bytes body
        int more_body
        int disconnected
        int keep_alive
        int idle

    cdef inline _maybe_call_on_header(self)

    cdef inline _on_header_field(self, bytes field)

    cdef inline _on_header_value(self, bytes val)

    cdef inline _on_headers_complete(self)

    cdef inline _on_chunk_header(self)

    cdef _on_url(self, url)

    cdef inline _on_body(self, bytes body)

    cdef inline _on_message_complete(self)

