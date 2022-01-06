cdef tuple CLOSE_HEADER

cdef int HIGH_WATER_LIMIT


cdef class FlowControl:
    cdef:
        _transport, _is_writable_event

        int read_paused
        int write_paused

    cdef inline pause_reading(self)

    cdef inline resume_reading(self)

    cdef inline pause_writing(self)

    cdef inline resume_writing(self)
