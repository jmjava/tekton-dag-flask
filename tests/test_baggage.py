import os
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask, g

import baggage


# ---------------------------------------------------------------------------
# W3C Baggage codec
# ---------------------------------------------------------------------------

class TestW3cCodec:
    def test_parse_empty(self):
        assert baggage.parse_baggage(None) == {}
        assert baggage.parse_baggage("") == {}
        assert baggage.parse_baggage("  ") == {}

    def test_parse_single(self):
        assert baggage.parse_baggage("dev-session=abc") == {"dev-session": "abc"}

    def test_parse_multiple(self):
        result = baggage.parse_baggage("k1=v1,k2=v2,k3=v3")
        assert result == {"k1": "v1", "k2": "v2", "k3": "v3"}

    def test_parse_preserves_properties(self):
        result = baggage.parse_baggage("k1=v1;prop=pval,k2=v2")
        assert result["k1"] == "v1;prop=pval"

    def test_merge_adds_entry(self):
        result = baggage.merge_baggage("k1=v1", "dev-session", "abc")
        assert "k1=v1" in result
        assert "dev-session=abc" in result

    def test_merge_replaces_entry(self):
        result = baggage.merge_baggage("dev-session=old,k1=v1", "dev-session", "new")
        assert "dev-session=new" in result
        assert "=old" not in result

    def test_merge_on_empty(self):
        assert baggage.merge_baggage(None, "dev-session", "abc") == "dev-session=abc"

    def test_round_trip(self):
        original = "k1=v1,k2=v2"
        assert baggage.serialize_baggage(baggage.parse_baggage(original)) == original


# ---------------------------------------------------------------------------
# Flask before_request hook
# ---------------------------------------------------------------------------

def _make_app(env_overrides):
    """Create a fresh Flask app with baggage wired under patched env vars."""
    with patch.dict(os.environ, env_overrides):
        # Re-read module-level constants that depend on env
        import importlib
        importlib.reload(baggage)

        test_app = Flask(__name__)
        baggage.init_app(test_app)

        @test_app.route("/check")
        def _check():
            return getattr(g, "dev_session", None) or ""

        return test_app


class TestForwarderHook:
    def setup_method(self):
        self.app = _make_app({
            "BAGGAGE_ENABLED": "true",
            "BAGGAGE_ROLE": "forwarder",
        })

    def test_extracts_header(self):
        client = self.app.test_client()
        resp = client.get("/check", headers={"x-dev-session": "sess-1"})
        assert resp.data == b"sess-1"

    def test_no_header_yields_empty(self):
        client = self.app.test_client()
        resp = client.get("/check")
        assert resp.data == b""


class TestOriginatorHook:
    def setup_method(self):
        self.app = _make_app({
            "BAGGAGE_ENABLED": "true",
            "BAGGAGE_ROLE": "originator",
            "BAGGAGE_SESSION_VALUE": "orig-123",
        })

    def test_uses_configured_value(self):
        client = self.app.test_client()
        resp = client.get("/check")
        assert resp.data == b"orig-123"

    def test_ignores_incoming_header(self):
        client = self.app.test_client()
        resp = client.get("/check", headers={"x-dev-session": "ignored"})
        assert resp.data == b"orig-123"


class TestTerminalHook:
    def setup_method(self):
        self.app = _make_app({
            "BAGGAGE_ENABLED": "true",
            "BAGGAGE_ROLE": "terminal",
        })

    def test_extracts_header(self):
        client = self.app.test_client()
        resp = client.get("/check", headers={"x-dev-session": "term-val"})
        assert resp.data == b"term-val"


class TestProductionGuard:
    def test_middleware_inactive_when_disabled(self):
        app = _make_app({"BAGGAGE_ENABLED": "false", "BAGGAGE_ROLE": "forwarder"})
        client = app.test_client()
        resp = client.get("/check", headers={"x-dev-session": "should-not-extract"})
        assert resp.data == b""

    def test_middleware_inactive_when_env_missing(self):
        env = os.environ.copy()
        env.pop("BAGGAGE_ENABLED", None)
        with patch.dict(os.environ, env, clear=True):
            import importlib
            importlib.reload(baggage)
            app = Flask(__name__)
            baggage.init_app(app)

            @app.route("/check")
            def _check():
                return getattr(g, "dev_session", None) or ""

            client = app.test_client()
            resp = client.get("/check", headers={"x-dev-session": "nope"})
            assert resp.data == b""


# ---------------------------------------------------------------------------
# BaggageSession outgoing
# ---------------------------------------------------------------------------

class TestBaggageSession:
    def test_originator_sets_headers(self):
        with patch.dict(os.environ, {
            "BAGGAGE_ENABLED": "true",
            "BAGGAGE_ROLE": "originator",
            "BAGGAGE_SESSION_VALUE": "orig-sess",
        }):
            import importlib
            importlib.reload(baggage)

            session = baggage.BaggageSession()
            adapter = MagicMock()
            resp_mock = MagicMock(status_code=200, headers={}, encoding="utf-8")
            resp_mock.is_redirect = False
            resp_mock.content = b""
            adapter.send.return_value = resp_mock
            session.mount("http://", adapter)

            session.get("http://downstream/api")

            call_args = adapter.send.call_args
            prepared = call_args[0][0]
            assert prepared.headers.get("x-dev-session") == "orig-sess"
            assert "dev-session=orig-sess" in prepared.headers.get("baggage", "")

    def test_terminal_never_sets_headers(self):
        with patch.dict(os.environ, {
            "BAGGAGE_ENABLED": "true",
            "BAGGAGE_ROLE": "terminal",
        }):
            import importlib
            importlib.reload(baggage)

            session = baggage.BaggageSession()
            adapter = MagicMock()
            resp_mock = MagicMock(status_code=200, headers={}, encoding="utf-8")
            resp_mock.is_redirect = False
            resp_mock.content = b""
            adapter.send.return_value = resp_mock
            session.mount("http://", adapter)

            session.get("http://downstream/api")

            call_args = adapter.send.call_args
            prepared = call_args[0][0]
            assert "x-dev-session" not in prepared.headers
