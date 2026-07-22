"""Tests for the pure-function helpers in databricks_web_app.solara_components."""

from __future__ import annotations

import base64
import json

from databricks_web_app.solara_components import _build_short_name, _jwt_payload


def _make_unsigned_jwt(payload: dict) -> str:
    """Build a JWT-shaped string with an arbitrary payload and no real signature."""

    def _b64(data: dict) -> str:
        raw = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    header = _b64({"alg": "RS256", "typ": "JWT"})
    body = _b64(payload)
    return f"{header}.{body}.signature"


class TestJwtPayload:
    def test_decodes_payload_claims(self):
        token = _make_unsigned_jwt({"oid": "abc-123", "sub": "user"})

        assert _jwt_payload(token) == {"oid": "abc-123", "sub": "user"}

    def test_returns_empty_dict_for_empty_token(self):
        assert _jwt_payload("") == {}

    def test_returns_empty_dict_for_malformed_token(self):
        assert _jwt_payload("not-a-jwt") == {}


class TestBuildShortName:
    def test_builds_initials_from_two_parts(self):
        assert _build_short_name(["john", "doe"], fallback="john.doe") == "JoDo"

    def test_falls_back_for_single_part_name(self):
        assert _build_short_name(["jo"], fallback="jodoe") == "Jodo"

    def test_falls_back_when_part_too_short(self):
        assert _build_short_name(["j", "doe"], fallback="j.doe") == "J.do"
