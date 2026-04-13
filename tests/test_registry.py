"""Tests for SkillRegistry."""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

# SkillRegistry depends on Pydantic (Python 3.8+)
pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 8),
    reason="Pydantic-based SkillRegistry requires Python 3.8+",
)

from skill_native_sdk import SkillRegistry, parse_skill_md
from skill_native_sdk.models import SkillSpec


def _make_skill(tmp_path: Path, name: str, domain: str = "testing") -> Path:
    d = tmp_path / name
    d.mkdir(parents=True, exist_ok=True)
    content = textwrap.dedent(f"""\
        ---
        name: {name}
        domain: {domain}
        version: "1.0.0"
        description: "Test skill {name}"
        tools:
          - name: tool_a
            description: "Tool A"
            read_only: true
            idempotent: true
          - name: tool_b
            description: "Tool B"
            read_only: false
            on_success:
              suggest: [tool_a]
        ---
    """)
    (d / "SKILL.md").write_text(content, encoding="utf-8")
    return d


def test_from_path(tmp_path: Path) -> None:
    _make_skill(tmp_path, "skill-x", domain="maya")
    _make_skill(tmp_path, "skill-y", domain="finance")

    registry = SkillRegistry.from_path(tmp_path)
    assert len(registry) == 2


def test_list_filter_by_domain(tmp_path: Path) -> None:
    _make_skill(tmp_path, "maya-anim", domain="maya")
    _make_skill(tmp_path, "invoice", domain="finance")

    registry = SkillRegistry.from_path(tmp_path)
    maya_skills = registry.list(domain="maya")
    assert len(maya_skills) == 1
    assert maya_skills[0].name == "maya-anim"


def test_get_tool(tmp_path: Path) -> None:
    _make_skill(tmp_path, "my-skill")
    registry = SkillRegistry.from_path(tmp_path)

    result = registry.get_tool("my-skill", "tool_a")
    assert result is not None
    spec, tool = result
    assert tool.name == "tool_a"
    assert tool.read_only is True


def test_get_tool_not_found(tmp_path: Path) -> None:
    _make_skill(tmp_path, "my-skill")
    registry = SkillRegistry.from_path(tmp_path)

    assert registry.get_tool("my-skill", "nonexistent") is None
    assert registry.get_tool("nonexistent-skill", "tool_a") is None


def test_domains(tmp_path: Path) -> None:
    _make_skill(tmp_path, "skill-a", domain="maya")
    _make_skill(tmp_path, "skill-b", domain="finance")
    _make_skill(tmp_path, "skill-c", domain="maya")

    registry = SkillRegistry.from_path(tmp_path)
    domains = registry.domains()
    assert domains == ["finance", "maya"]


def test_capability_graph(tmp_path: Path) -> None:
    _make_skill(tmp_path, "my-skill", domain="testing")
    registry = SkillRegistry.from_path(tmp_path)

    graph = registry.capability_graph("my-skill")
    assert graph["skill"] == "my-skill"
    assert graph["domain"] == "testing"
    assert "entry_points" in graph
    assert "graph" in graph

    # tool_b suggests tool_a on success, so tool_b is an entry point
    assert "tool_b" in graph["entry_points"]
    assert "tool_a" not in graph["entry_points"]

    # tool_b on_success → tool_a
    assert "tool_a" in graph["graph"]["tool_b"]["on_success"]


def test_contains(tmp_path: Path) -> None:
    _make_skill(tmp_path, "existing-skill")
    registry = SkillRegistry.from_path(tmp_path)
    assert "existing-skill" in registry
    assert "ghost-skill" not in registry
