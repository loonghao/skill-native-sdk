"""Tests for ToolResult and model helpers (stdlib dataclasses — no third-party deps)."""
from __future__ import annotations

import json

import pytest

from skill_native_sdk.models import ToolResult


def test_tool_result_ok() -> None:
    r = ToolResult.ok("Done", data={"x": 1}, next_actions=["next_tool"])
    assert r.success is True
    assert r.message == "Done"
    assert r.data == {"x": 1}
    assert r.next_actions == ["next_tool"]


def test_tool_result_fail() -> None:
    r = ToolResult.fail(error="Something went wrong", message="Failed step")
    assert r.success is False
    assert r.error == "Something went wrong"
    assert r.message == "Failed step"


def test_to_toon_success() -> None:
    r = ToolResult.ok("Done", next_actions=["foo"])
    toon = r.to_toon()
    assert toon["ok"] is True
    assert toon["msg"] == "Done"
    assert toon["next"] == ["foo"]
    assert "err" not in toon


def test_to_toon_failure() -> None:
    r = ToolResult.fail(error="Oops")
    toon = r.to_toon()
    assert toon["ok"] is False
    assert toon["err"] == "Oops"


def test_to_mcp() -> None:
    r = ToolResult.ok("Hello MCP")
    mcp = r.to_mcp()
    assert mcp["type"] == "tool_result"
    assert mcp["isError"] is False
    assert mcp["content"][0]["text"] == "Hello MCP"


def test_to_dict() -> None:
    r = ToolResult.ok("test")
    d = r.to_dict()
    assert isinstance(d, dict)
    assert d["success"] is True
    # Must be JSON serializable (this was Bug #3 in dcc-mcp-core)
    json.dumps(d)  # should not raise


def test_to_dict_json_serializable() -> None:
    """ToolResult.to_dict() must be directly JSON-serializable (Bug #3 fix)."""
    r = ToolResult.ok("works", data={"nested": [1, 2, 3]})
    serialized = json.dumps(r.to_dict())
    restored = json.loads(serialized)
    assert restored["success"] is True
    assert restored["data"]["nested"] == [1, 2, 3]
