"""SKILL.md v2 parser — zero third-party dependencies.

Primary path  : Rust ``_skill_native_core`` (always available in the wheel).
Fallback path : Pure-stdlib minimal YAML front-matter parser (for development
                without a compiled extension, e.g. ``pip install -e . --no-build-isolation``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .models import (
    ChainHint,
    FieldSchema,
    Permissions,
    RuntimeConfig,
    SkillSpec,
    ToolMeta,
)

# ---------------------------------------------------------------------------
# Try to use the fast Rust parser first
# ---------------------------------------------------------------------------
try:
    from . import _skill_native_core as _rust_core  # type: ignore[attr-defined]
    _RUST_AVAILABLE = True
except ImportError:
    _rust_core = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False


def _rust_spec_to_python(rs: Any) -> SkillSpec:
    """Convert a Rust ``RustSkillSpec`` object to a Python ``SkillSpec`` dataclass."""
    tools: List[ToolMeta] = []
    for rt in rs.tools():
        t = ToolMeta(
            name=rt.name,
            description=rt.description,
            source_file=rt.source_file,
            read_only=rt.read_only,
            destructive=rt.destructive,
            idempotent=rt.idempotent,
            cost=rt.cost,
            latency=rt.latency,
            on_success=ChainHint(suggest=list(rt.on_success_suggest)),
            on_error=ChainHint(suggest=list(rt.on_error_suggest)),
        )
        # Rebuild FieldSchema map from Rust dict
        for fname, fdata in rt.input_fields().items():
            t.input[fname] = FieldSchema(
                type=fdata.get("type", "string"),
                description=fdata.get("description", ""),
                required=bool(fdata.get("required", False)),
            )
        tools.append(t)

    return SkillSpec(
        name=rs.name,
        domain=rs.domain,
        version=rs.version,
        description=rs.description,
        tags=list(rs.tags),
        tools=tools,
        runtime=RuntimeConfig(
            type=rs.runtime_type,
            entry=rs.runtime_entry,
            interpreter=rs.runtime_interpreter,
        ),
        permissions=Permissions(
            network=rs.perm_network,
            filesystem=rs.perm_filesystem,
            external_api=rs.perm_external_api,
        ),
        source_dir=rs.source_dir,
    )


# ---------------------------------------------------------------------------
# Pure-stdlib minimal YAML front-matter parser (fallback only)
# ---------------------------------------------------------------------------

def _scalar(s: str) -> Any:
    s = s.strip()
    for q in ('"', "'"):
        if len(s) >= 2 and s[0] == s[-1] == q:
            return s[1:-1]
    lo = s.lower()
    if lo in ("true", "yes"): return True
    if lo in ("false", "no"): return False
    if lo in ("null", "none", "~", ""): return None
    for fn in (int, float):
        try: return fn(s)  # type: ignore[arg-type]
        except (ValueError, TypeError): pass
    return s


def _inline_list(s: str) -> List[Any]:
    inner = s.strip()[1:-1]
    return [_scalar(x) for x in inner.split(",") if x.strip()] if inner.strip() else []


def _ind(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_mapping(lines: List[str], i: int, base: int) -> Tuple[Dict[str, Any], int]:
    result: Dict[str, Any] = {}
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()
        if not s or s.startswith("#") or s in ("---", "..."):
            i += 1; continue
        ind = _ind(raw)
        if ind < base:
            break
        if ":" not in s:
            i += 1; continue
        k, _, rest = s.partition(":")
        k = k.strip(); rest = rest.strip()
        i += 1
        if rest:
            result[k] = _inline_list(rest) if rest.startswith("[") else _scalar(rest)
        else:
            # Skip blank lines and peek at next non-blank line
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i >= len(lines) or _ind(lines[i]) <= base:
                result[k] = None
                continue
            child_ind = _ind(lines[i])
            cs = lines[i].strip()
            if cs.startswith("- ") or cs == "-":
                result[k], i = _parse_sequence(lines, i, child_ind)
            else:
                result[k], i = _parse_mapping(lines, i, child_ind)
    return result, i


def _parse_sequence(lines: List[str], i: int, base: int) -> Tuple[List[Any], int]:
    result: List[Any] = []
    while i < len(lines):
        raw = lines[i]; s = raw.strip()
        if not s or s.startswith("#"): i += 1; continue
        if _ind(raw) < base: break
        if not (s.startswith("- ") or s == "-"): break
        i += 1
        item_text = s[2:].strip() if s.startswith("- ") else ""
        if not item_text:
            # Nested block
            while i < len(lines) and not lines[i].strip(): i += 1
            if i < len(lines) and _ind(lines[i]) > base:
                ci = _ind(lines[i])
                cs = lines[i].strip()
                if cs.startswith("- ") or cs == "-":
                    val, i = _parse_sequence(lines, i, ci)
                else:
                    val, i = _parse_mapping(lines, i, ci)
                result.append(val)
            else:
                result.append(None)
        elif ":" in item_text and item_text[0] not in ('"', "'"):
            # First key of a mapping item
            k, _, v = item_text.partition(":")
            item: Dict[str, Any] = {}
            item[k.strip()] = _inline_list(v.strip()) if v.strip().startswith("[") else _scalar(v.strip())
            # Collect sibling keys at indent > base
            while i < len(lines):
                sub = lines[i]; ss = sub.strip()
                if not ss or ss.startswith("#"): i += 1; continue
                si = _ind(sub)
                if si <= base or ss.startswith("- "): break
                if ":" in ss:
                    k2, _, v2 = ss.partition(":")
                    k2 = k2.strip(); v2 = v2.strip()
                    i += 1
                    if v2:
                        item[k2] = _inline_list(v2) if v2.startswith("[") else _scalar(v2)
                    else:
                        while i < len(lines) and not lines[i].strip(): i += 1
                        if i < len(lines) and _ind(lines[i]) > si:
                            ci = _ind(lines[i]); cs2 = lines[i].strip()
                            if cs2.startswith("- ") or cs2 == "-":
                                item[k2], i = _parse_sequence(lines, i, ci)
                            else:
                                item[k2], i = _parse_mapping(lines, i, ci)
                        else:
                            item[k2] = None
                else:
                    i += 1
            result.append(item)
        else:
            result.append(_scalar(item_text))
    return result, i


def _extract_frontmatter(text: str) -> Optional[str]:
    text = text.lstrip()
    if not text.startswith("---"):
        return None
    rest = text[3:].lstrip("\r\n")
    end = rest.find("\n---")
    return rest[:end] if end != -1 else None


def _stdlib_parse(text: str, source_dir: str) -> Optional[SkillSpec]:
    fm = _extract_frontmatter(text)
    if not fm:
        return None
    data, _ = _parse_mapping(fm.splitlines(), 0, 0)
    return _dict_to_spec(data, source_dir)


def _dict_to_spec(data: Dict[str, Any], source_dir: str) -> SkillSpec:
    tools: List[ToolMeta] = []
    for raw in data.get("tools", []) or []:
        if not isinstance(raw, dict):
            continue
        on_s = raw.get("on_success") or {}
        on_e = raw.get("on_error") or {}
        t = ToolMeta(
            name=str(raw.get("name", "")),
            description=str(raw.get("description", "")),
            source_file=raw.get("source_file"),
            read_only=bool(raw.get("read_only", True)),
            destructive=bool(raw.get("destructive", False)),
            idempotent=bool(raw.get("idempotent", False)),
            cost=str(raw.get("cost", "low")),
            latency=str(raw.get("latency", "fast")),
            on_success=ChainHint(suggest=list(on_s.get("suggest", []) or [])),
            on_error=ChainHint(suggest=list(on_e.get("suggest", []) or [])),
        )
        for fn, fv in (raw.get("input") or {}).items():
            if isinstance(fv, dict):
                t.input[fn] = FieldSchema(
                    type=str(fv.get("type", "string")),
                    description=str(fv.get("description", "")),
                    required=bool(fv.get("required", False)),
                    default=fv.get("default"),
                )
            elif isinstance(fv, str):
                t.input[fn] = FieldSchema(type=fv)
        tools.append(t)

    rt_raw = data.get("runtime") or {}
    perm_raw = data.get("permissions") or {}
    return SkillSpec(
        name=str(data.get("name", "")),
        domain=str(data.get("domain", "generic")),
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        tags=list(data.get("tags", []) or []),
        tools=tools,
        runtime=RuntimeConfig(
            type=str(rt_raw.get("type", "python")),
            entry=str(rt_raw.get("entry", "skill_entry")),
            interpreter=rt_raw.get("interpreter"),
        ),
        permissions=Permissions(
            network=bool(perm_raw.get("network", False)),
            filesystem=str(perm_raw.get("filesystem", "none")),
            external_api=bool(perm_raw.get("external_api", False)),
        ),
        source_dir=source_dir,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_skill_md(path: Union[str, Path]) -> Optional[SkillSpec]:
    """Parse a SKILL.md file or directory. Returns ``None`` if not found."""
    p = Path(path)
    if p.is_dir():
        candidate = p / "SKILL.md"
        if not candidate.exists():
            return None
        p = candidate
    if not p.exists():
        return None

    source_dir = str(p.parent)

    if _RUST_AVAILABLE:
        rs = _rust_core.parse_skill_md(str(p))
        return _rust_spec_to_python(rs) if rs is not None else None

    text = p.read_text(encoding="utf-8")
    return _stdlib_parse(text, source_dir)


def scan_and_load(directory: Union[str, Path]) -> List[SkillSpec]:
    """Recursively scan *directory* for SKILL.md files."""
    root = Path(directory)

    if _RUST_AVAILABLE:
        return [_rust_spec_to_python(rs) for rs in _rust_core.scan_and_load(str(root))]

    specs: List[SkillSpec] = []
    for skill_file in root.rglob("SKILL.md"):
        spec = parse_skill_md(skill_file.parent)
        if spec is not None:
            specs.append(spec)
    return specs
