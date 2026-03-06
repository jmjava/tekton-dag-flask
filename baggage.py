"""
Baggage middleware — delegates to the standalone tekton-dag-baggage library.
This file exists for backward compatibility so `import baggage` and
`baggage.init_app(app)` continue to work without changing app.py.

When tekton-dag-baggage is not installed (production builds that omit
dev dependencies), all functions become safe no-ops.
"""
try:
    from tekton_dag_baggage import (
        parse_baggage,
        merge_baggage,
        serialize_baggage,
        init_app,
        BaggageSession,
        HEADER_NAME,
        BAGGAGE_KEY,
        SESSION_VALUE,
        ROLE,
    )
except ImportError:
    HEADER_NAME = "x-dev-session"
    BAGGAGE_KEY = "dev-session"
    SESSION_VALUE = ""
    ROLE = "disabled"

    def parse_baggage(header):
        return {}

    def merge_baggage(header, key, value):
        return ""

    def serialize_baggage(entries):
        return ""

    def init_app(app):
        pass

    class BaggageSession:
        pass


__all__ = [
    "parse_baggage",
    "merge_baggage",
    "serialize_baggage",
    "init_app",
    "BaggageSession",
    "HEADER_NAME",
    "BAGGAGE_KEY",
    "SESSION_VALUE",
    "ROLE",
]
