"""
Role-aware W3C baggage / x-dev-session middleware for Flask.

Roles:
  originator — sets headers on all outgoing calls from configured value
  forwarder  — extracts from incoming, propagates on outgoing
  terminal   — extracts from incoming for logging/routing, never propagates

Production safety: no-op unless BAGGAGE_ENABLED=true is set in the environment.
"""

import os
from flask import g, request
import requests as _requests


HEADER_NAME = os.environ.get("BAGGAGE_HEADER_NAME", "x-dev-session")
BAGGAGE_KEY = os.environ.get("BAGGAGE_KEY", "dev-session")
SESSION_VALUE = os.environ.get("BAGGAGE_SESSION_VALUE", "")
ROLE = os.environ.get("BAGGAGE_ROLE", "forwarder").lower()


# ---------------------------------------------------------------------------
# W3C Baggage codec
# ---------------------------------------------------------------------------

def parse_baggage(header):
    entries = {}
    if not header or not header.strip():
        return entries
    for member in header.split(","):
        member = member.strip()
        if not member:
            continue
        eq = member.find("=")
        if eq < 1:
            continue
        entries[member[:eq].strip()] = member[eq + 1:].strip()
    return entries


def merge_baggage(existing_header, key, value):
    entries = parse_baggage(existing_header)
    entries[key] = value
    return serialize_baggage(entries)


def serialize_baggage(entries):
    return ",".join(f"{k}={v}" for k, v in entries.items())


# ---------------------------------------------------------------------------
# Flask integration
# ---------------------------------------------------------------------------

def init_app(app):
    enabled = os.environ.get("BAGGAGE_ENABLED", "").lower() == "true"
    if not enabled:
        return

    @app.before_request
    def _extract_session():
        if ROLE == "originator":
            val = SESSION_VALUE.strip() or None
        elif ROLE in ("forwarder", "terminal"):
            val = (request.headers.get(HEADER_NAME) or "").strip() or None
        else:
            val = None
        g.dev_session = val


# ---------------------------------------------------------------------------
# Outgoing requests session (forwarder / originator only)
# ---------------------------------------------------------------------------

class BaggageSession(_requests.Session):
    """requests.Session subclass that propagates baggage on outgoing calls."""

    def request(self, method, url, **kwargs):
        session_value = self._resolve_outgoing()
        if session_value:
            headers = kwargs.setdefault("headers", {})
            headers[HEADER_NAME] = session_value
            existing = headers.get("baggage", "")
            headers["baggage"] = merge_baggage(existing, BAGGAGE_KEY, session_value)
        return super().request(method, url, **kwargs)

    @staticmethod
    def _resolve_outgoing():
        if ROLE == "originator":
            return SESSION_VALUE.strip() or None
        if ROLE == "forwarder":
            try:
                return getattr(g, "dev_session", None)
            except RuntimeError:
                return None
        return None
