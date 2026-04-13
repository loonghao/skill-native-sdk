"""Tests for the SKILL.md v2 parser (stdlib dataclasses — no third-party deps)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from skill_native_sdk import parse_skill_md, scan_and_load
from skill_native_sdk.models import SkillSpec


SKILL_MD_CONTENT = textwrap.dedent("""\
    ---
    name: test-skill
    domain: testing
    version: "1.0.0"
    description: "A test skill"
    tags: [test, example]

    tools:
      - name: do_something
        description: "Does something useful"
        source_file: scripts/do_something.py
        read_only: false
        destructive: false
        idempotent: true
        cost: low
        latency: fast
        input:
          value:
            type: string
            required: true
            description: "Input value"
        output:
          result: string
        on_success:
          suggest: [do_something_else]
        on_error:
          suggest: []

      - name: do_something_else
        description: "Follow-up tool"
        read_only: true
        destructive: false
        idempotent: true
        cost: low
        latency: fast

    runtime:
      type: python
      entry: skill_entry

    permissions:
      network: false
      filesystem: read
      external_api: false
    ---
""")


@pytest.fixture()
def skill_dir(tmp_path: Path) -> Path:
    """Create a temporary skill directory with a SKILL.md."""
    (tmp_path / "SKILL.md").write_text(SKILL_MD_CONTENT, encoding="utf-8")
    return tmp_path


def test_parse_from_directory(skill_dir: Path) -> None:
    spec = parse_skill_md(skill_dir)
    assert spec is not None
    assert spec.name == "test-skill"
    assert spec.domain == "testing"
    assert spec.version == "1.0.0"
    assert len(spec.tools) == 2


def test_parse_from_file(skill_dir: Path) -> None:
    spec = parse_skill_md(skill_dir / "SKILL.md")
    assert spec is not None
    assert spec.name == "test-skill"


def test_parse_tool_fields(skill_dir: Path) -> None:
    spec = parse_skill_md(skill_dir)
    assert spec is not None
    tool = spec.get_tool("do_something")
    assert tool is not None
    assert tool.read_only is False
    assert tool.idempotent is True
    assert tool.cost == "low"
    assert "value" in tool.input
    assert tool.input["value"].required is True
    assert tool.on_success.suggest == ["do_something_else"]


def test_parse_missing_file() -> None:
    spec = parse_skill_md("/nonexistent/path/SKILL.md")
    assert spec is None


def test_parse_missing_skill_md(tmp_path: Path) -> None:
    """Directory without SKILL.md returns None."""
    spec = parse_skill_md(tmp_path)
    assert spec is None


def test_scan_and_load(tmp_path: Path) -> None:
    """scan_and_load finds all SKILL.md files recursively."""
    # Create two skill directories
    for skill in ["skill-a", "skill-b"]:
        d = tmp_path / skill
        d.mkdir()
        content = SKILL_MD_CONTENT.replace("test-skill", skill)
        (d / "SKILL.md").write_text(content, encoding="utf-8")

    specs = scan_and_load(tmp_path)
    assert len(specs) == 2
    names = {s.name for s in specs}
    assert names == {"skill-a", "skill-b"}


def test_scan_and_load_no_scripts_dir(tmp_path: Path) -> None:
    """Skills without a scripts/ directory should still be loaded (Bug #2 fix)."""
    d = tmp_path / "pure-description-skill"
    d.mkdir()
    # SKILL.md with no source_file (pure description type)
    content = textwrap.dedent("""\
        ---
        name: pure-skill
        domain: testing
        tools:
          - name: noop
            description: "No source file"
            read_only: true
        ---
    """)
    (d / "SKILL.md").write_text(content, encoding="utf-8")

    specs = scan_and_load(tmp_path)
    assert len(specs) == 1
    assert specs[0].name == "pure-skill"


def test_entry_points(skill_dir: Path) -> None:
    spec = parse_skill_md(skill_dir)
    assert spec is not None
    # do_something is entry (not in any on_success/on_error)
    # do_something_else is suggested by do_something
    assert "do_something" in spec.entry_points
    assert "do_something_else" not in spec.entry_points


def test_readonly_tools(skill_dir: Path) -> None:
    spec = parse_skill_md(skill_dir)
    assert spec is not None
    names = {t.name for t in spec.readonly_tools}
    assert "do_something_else" in names
    assert "do_something" not in names
