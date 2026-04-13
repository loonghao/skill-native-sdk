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

# ── Try to import compiled Rust core ──────────────────────────────────────────
try:
    from . import _skill_native_core as _rust  # type: ignore[attr-defined]
    _RUST_AVAILABLE = True
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False

# ── Public API (always Python) ────────────────────────────────────────────────
from .decorators import run_main, skill_entry, skill_error, skill_success
from .executor import SkillExecutor
from .models import FieldSchema, Permissions, RuntimeConfig, SkillSpec, ToolMeta, ToolResult
from .parser import parse_skill_md, scan_and_load
from .registry import SkillRegistry

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
