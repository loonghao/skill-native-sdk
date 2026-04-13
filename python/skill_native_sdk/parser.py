"""SKILL.md v2 parser — reads and validates skill specification files."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .models import ChainHint, FieldSchema, Permissions, RuntimeConfig, SkillSpec, ToolMeta

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_YAML_FENCE = re.compile(r"```ya?ml\s*\n(.*?)```", re.DOTALL)
_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _extract_yaml(text: str) -> dict[str, Any]:
    """Extract YAML from fenced block or front-matter, or parse the whole file."""
    # 1. Try YAML front-matter
    m = _FRONTMATTER.match(text)
    if m:
        return yaml.safe_load(m.group(1)) or {}

    # 2. Try first fenced yaml block
    m = _YAML_FENCE.search(text)
    if m:
        return yaml.safe_load(m.group(1)) or {}

    # 3. Try parsing the whole file as YAML
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        pass

    return {}


def _parse_field_schema(raw: Any) -> FieldSchema:
    if isinstance(raw, dict):
        return FieldSchema(**{k: v for k, v in raw.items() if k in FieldSchema.model_fields})
    if isinstance(raw, str):
        return FieldSchema(type=raw)  # type: ignore[arg-type]
    return FieldSchema()


def _parse_tool(raw: dict[str, Any]) -> ToolMeta:
    # Parse input fields
    input_raw = raw.pop("input", {}) or {}
    input_parsed = {k: _parse_field_schema(v) for k, v in input_raw.items()}

    # Parse on_success / on_error
    on_success_raw = raw.pop("on_success", {}) or {}
    on_error_raw = raw.pop("on_error", {}) or {}
    on_success = ChainHint(**on_success_raw) if isinstance(on_success_raw, dict) else ChainHint()
    on_error = ChainHint(**on_error_raw) if isinstance(on_error_raw, dict) else ChainHint()

    # Strip unknown keys
    known = set(ToolMeta.model_fields.keys())
    clean = {k: v for k, v in raw.items() if k in known}

    return ToolMeta(
        **clean,
        input=input_parsed,
        on_success=on_success,
        on_error=on_error,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_skill_md(path: str | Path) -> SkillSpec | None:
    """Parse a SKILL.md file or a directory containing one.

    Args:
        path: Path to a SKILL.md file *or* a directory that contains SKILL.md.

    Returns:
        A :class:`SkillSpec` on success, ``None`` if nothing was found.
    """
    p = Path(path)

    # Auto-detect: if directory, look for SKILL.md inside
    if p.is_dir():
        candidate = p / "SKILL.md"
        if not candidate.exists():
            return None
        p = candidate

    if not p.exists():
        return None

    text = p.read_text(encoding="utf-8")
    data = _extract_yaml(text)
    if not data:
        return None

    # Parse tools list
    tools_raw: list[dict[str, Any]] = data.pop("tools", []) or []
    tools = [_parse_tool(dict(t)) for t in tools_raw if isinstance(t, dict)]

    # Parse runtime
    runtime_raw = data.pop("runtime", {}) or {}
    runtime = RuntimeConfig(**runtime_raw) if isinstance(runtime_raw, dict) else RuntimeConfig()

    # Parse permissions
    perms_raw = data.pop("permissions", {}) or {}
    permissions = Permissions(**perms_raw) if isinstance(perms_raw, dict) else Permissions()

    # Strip unknown top-level keys
    known = set(SkillSpec.model_fields.keys()) - {"tools", "runtime", "permissions", "source_dir"}
    clean = {k: v for k, v in data.items() if k in known}

    return SkillSpec(
        **clean,
        tools=tools,
        runtime=runtime,
        permissions=permissions,
        source_dir=str(p.parent),
    )


def scan_and_load(directory: str | Path) -> list[SkillSpec]:
    """Recursively scan *directory* for SKILL.md files and return all parsed specs.

    Unlike some previous implementations this correctly handles skills that
    have only a SKILL.md without a ``scripts/`` subdirectory.
    """
    root = Path(directory)
    specs: list[SkillSpec] = []
    for skill_file in root.rglob("SKILL.md"):
        spec = parse_skill_md(skill_file.parent)
        if spec is not None:
            specs.append(spec)
    return specs
