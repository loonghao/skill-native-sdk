"""skill-native-sdk — SKILL.md → anywhere.

Write once in SKILL.md, deploy as MCP / OpenAI / LangChain / REST.

Architecture
------------
The SDK has two layers that work together:

1. **Rust core** (``_skill_native_core`` extension module, built by maturin):
   - Zero-copy YAML parser for SKILL.md v2
   - Lock-free ResultCache (DashMap)
   - DAG scheduler for parallel read-only tools
   - SafetyChecker enforcing destructive/idempotent semantics
   - All exposed via PyO3 as ``RustSkillSpec``, ``RustToolResult``, etc.

2. **Python layer** (this package):
   - ``SkillRegistry`` — load, index, query skills
   - ``SkillExecutor`` — dispatch to Rust bridges
   - ``MCPServer`` adapter, OpenAI adapter, LangChain adapter
   - ``skill`` CLI

The Python layer transparently uses the Rust implementation when the
compiled extension is available, falling back to pure Python otherwise.
"""

import sys as _sys

# ── Try to import compiled Rust core ──────────────────────────────────────────
try:
    from . import _skill_native_core as _rust  # type: ignore[attr-defined]
    _RUST_AVAILABLE = True
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False

# ── Public API ────────────────────────────────────────────────────────────────
# Pydantic (v2) requires Python 3.8+.
# On Python 3.7 we expose only the Rust-backed types and the YAML parser
# (pure-Python fallback via pyyaml).  The Pydantic model layer, the CLI,
# and the adapters are not available on Python 3.7.
_PY38 = _sys.version_info >= (3, 8)

if _PY38:
    from .decorators import run_main, skill_entry, skill_error, skill_success
    from .executor import SkillExecutor
    from .models import FieldSchema, Permissions, RuntimeConfig, SkillSpec, ToolMeta, ToolResult
    from .parser import parse_skill_md, scan_and_load
    from .registry import SkillRegistry

    __all__ = [
        # Core models
        "SkillSpec",
        "ToolMeta",
        "ToolResult",
        "FieldSchema",
        "RuntimeConfig",
        "Permissions",
        # Parser
        "parse_skill_md",
        "scan_and_load",
        # Registry
        "SkillRegistry",
        # Executor
        "SkillExecutor",
        # Decorators
        "skill_entry",
        "skill_success",
        "skill_error",
        "run_main",
    ]
else:
    # Python 3.7 — Rust-only mode
    # Use _skill_native_core directly:
    #   from skill_native_sdk._skill_native_core import RustToolResult, SafetyChecker, ...
    if not _RUST_AVAILABLE:
        import warnings
        warnings.warn(
            "skill-native-sdk: Pydantic (Python 3.8+) is not available and the "
            "compiled Rust extension (_skill_native_core) was not found. "
            "On Python 3.7 please install the prebuilt wheel:\n"
            "  pip install skill-native-sdk",
            ImportWarning,
            stacklevel=2,
        )

    __all__: list = []  # type: ignore[assignment]

__version__ = "0.1.0"

__all__ = [
    # Core models
    "SkillSpec",
    "ToolMeta",
    "ToolResult",
    "FieldSchema",
    "RuntimeConfig",
    "Permissions",
    # Parser
    "parse_skill_md",
    "scan_and_load",
    # Registry
    "SkillRegistry",
    # Executor
    "SkillExecutor",
    # Decorators
    "skill_entry",
    "skill_success",
    "skill_error",
    "run_main",
]
