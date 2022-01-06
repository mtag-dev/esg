import asyncio

from asgiref.typing import (
    ASGIReceiveCallable,
    ASGISendCallable,
    HTTPResponseBodyEvent,
    HTTPResponseStartEvent,
    Scope,
)

CLOSE_HEADER = (b"connection", b"close")

HIGH_WATER_LIMIT = 65536


cdef class FlowControl:

    def __cinit__(self, transport: asyncio.Transport) -> None:
        self._transport = transport
        self.read_paused = False
        self.write_paused = False
        self._is_writable_event = asyncio.Event()
        self._is_writable_event.set()

    async def drain(self) -> None:
        await self._is_writable_event.wait()

    cdef inline pause_reading(self):
        if not self.read_paused:
            self.read_paused = True
            self._transport.pause_reading()

    cdef inline resume_reading(self):
        if self.read_paused:
            self.read_paused = False
            self._transport.resume_reading()

    cdef inline pause_writing(self):
        if not self.write_paused:
            self.write_paused = True
            self._is_writable_event.clear()

    cdef inline resume_writing(self):
        if self.write_paused:
            self.write_paused = False
            self._is_writable_event.set()
