"""Tests for the SKILL.md v2 parser (stdlib dataclasses — no third-party deps)."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from skill_native_sdk import parse_skill_md, scan_and_load
from skill_native_sdk.models import SkillSpec
from skill_native_sdk.parser import _stdlib_parse


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



# ── FieldSchema conversion tests ──────────────────────────────────────────────

SKILL_WITH_ENUMS = textwrap.dedent("""\
    ---
    name: enum-skill
    domain: test
    version: "1.0.0"
    description: "Tests enum + default fields"

    tools:
      - name: set_mode
        description: "Set render mode"
        read_only: false
        input:
          mode:
            type: string
            required: true
            enum: [fast, quality, preview]
            description: "Render mode"
          samples:
            type: integer
            required: false
            default: 64
            description: "Sample count"

    runtime:
      type: python
      entry: skill_entry
    permissions:
      network: false
      filesystem: none
    ---
""")


def test_fieldschema_enum_parsed() -> None:
    """FieldSchema.enum must survive the stdlib parser round-trip."""
    spec = _stdlib_parse(SKILL_WITH_ENUMS, "/tmp")
    tool = spec.get_tool("set_mode")
    assert tool is not None
    mode_field = tool.input.get("mode")
    assert mode_field is not None
    assert mode_field.enum == ["fast", "quality", "preview"]


def test_fieldschema_default_parsed() -> None:
    """FieldSchema.default must be preserved by the stdlib parser."""
    spec = _stdlib_parse(SKILL_WITH_ENUMS, "/tmp")
    tool = spec.get_tool("set_mode")
    assert tool is not None
    samples_field = tool.input.get("samples")
    assert samples_field is not None
    assert samples_field.default == 64
    assert not samples_field.required


def test_fieldschema_required_flag() -> None:
    spec = _stdlib_parse(SKILL_WITH_ENUMS, "/tmp")
    tool = spec.get_tool("set_mode")
    assert tool is not None
    assert tool.input["mode"].required is True
    assert tool.input["samples"].required is False


# ── SkillsManager discovery tests ─────────────────────────────────────────────

def test_skills_manager_scan_for_cwd(skill_dir: Path, tmp_path: Path) -> None:
    """SkillsManager discovers skills under the cwd."""
    # skill_dir == tmp_path / "test-skill" — create a parent to scan from
    skills_root = skill_dir.parent

    try:
        from skill_native_sdk._skill_native_core import SkillsManager
    except ImportError:
        pytest.skip("Rust extension not built")

    mgr = SkillsManager()
    outcome = mgr.scan_for_cwd(str(skills_root), force_reload=True)
    names = [m.name for m in outcome.metadata]
    assert "test-skill" in names


def test_skills_manager_lazy_load(skill_dir: Path, tmp_path: Path) -> None:
    """SkillMetadata.load() returns a full RustSkillSpec without pre-loading all skills."""
    skills_root = skill_dir.parent

    try:
        from skill_native_sdk._skill_native_core import SkillsManager
    except ImportError:
        pytest.skip("Rust extension not built")

    mgr = SkillsManager()
    outcome = mgr.scan_for_cwd(str(skills_root), force_reload=True)

    meta = outcome.find("test-skill")
    assert meta is not None
    assert meta.domain == "testing"

    spec = meta.load()
    assert spec.name == "test-skill"
    assert len(spec.tools()) >= 1


def test_skills_manager_cache(skill_dir: Path, tmp_path: Path) -> None:
    """Second call with force_reload=False returns a cached result."""
    skills_root = skill_dir.parent

    try:
        from skill_native_sdk._skill_native_core import SkillsManager
    except ImportError:
        pytest.skip("Rust extension not built")

    mgr = SkillsManager()
    outcome1 = mgr.scan_for_cwd(str(skills_root), force_reload=True)
    outcome2 = mgr.scan_for_cwd(str(skills_root), force_reload=False)
    assert len(outcome1.metadata) == len(outcome2.metadata)


def test_skills_manager_clear_cache(skill_dir: Path, tmp_path: Path) -> None:
    """clear_cache() forces a fresh scan on the next call."""
    skills_root = skill_dir.parent

    try:
        from skill_native_sdk._skill_native_core import SkillsManager
    except ImportError:
        pytest.skip("Rust extension not built")

    mgr = SkillsManager()
    mgr.scan_for_cwd(str(skills_root), force_reload=True)
    mgr.clear_cache()
    # After clear_cache, a new scan should still find the same skills
    outcome = mgr.scan_for_cwd(str(skills_root), force_reload=False)
    assert any(m.name == "test-skill" for m in outcome.metadata)


# ── HTTP executor tests ───────────────────────────────────────────────────────

def test_http_executor_url_error(tmp_path: Path) -> None:
    """HTTP runtime returns ToolResult.fail on connection error (not crash)."""
    import textwrap

    skill_md = tmp_path / "http-skill" / "SKILL.md"
    skill_md.parent.mkdir()
    skill_md.write_text(textwrap.dedent("""\
        ---
        name: http-skill
        domain: test
        version: "1.0.0"
        description: "HTTP test"
        tools:
          - name: ping
            description: "Ping remote"
        runtime:
          type: http
          entry: http://127.0.0.1:19999/http-skill/ping
        permissions:
          network: true
          filesystem: none
        ---
    """))

    from skill_native_sdk import SkillRegistry
    from skill_native_sdk.executor import SkillExecutor

    registry = SkillRegistry.from_path(tmp_path)
    executor = SkillExecutor(registry)

    result = executor.execute("http-skill", "ping", {})
    # Port 19999 should not be listening → connection error, not an exception
    assert not result.success
    assert result.error is not None
    assert "error" in result.error.lower() or "connect" in result.error.lower()
