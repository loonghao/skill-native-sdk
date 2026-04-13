"""skill-native-sdk — SKILL.md → anywhere.

Write once in SKILL.md, deploy as MCP / OpenAI / LangChain / REST.
Zero third-party Python dependencies — all heavy lifting is in the Rust core.

Layers
------
1. **Rust core** (``_skill_native_core``, built by maturin):
   - SKILL.md v2 YAML parser (BFS + lazy loading + layered discovery)
   - Lock-free ``ResultCache`` (DashMap)
   - DAG scheduler for parallel ``read_only`` tools
   - ``SafetyChecker`` for destructive/idempotent semantics
   - ``SkillsManager`` — cwd-keyed progressive discovery

2. **Python layer** (pure stdlib, Python 3.7+):
   - ``SkillRegistry`` / ``SkillExecutor``
   - Adapters: MCP · OpenAI · LangChain · REST
   - ``skn`` CLI (delegates to ``_skill_native_core.run_cli``)
"""
# ── Try to import compiled Rust core ──────────────────────────────────────────
try:
    from . import _skill_native_core as _rust  # type: ignore[attr-defined]
    _RUST_AVAILABLE = True
except ImportError:
    _rust = None  # type: ignore[assignment]
    _RUST_AVAILABLE = False

# ── Public API — pure stdlib, works on Python 3.7+ ───────────────────────────
from .decorators import run_main, skill_entry, skill_error, skill_success
from .executor import SkillExecutor
from .models import FieldSchema, Permissions, RuntimeConfig, SkillSpec, ToolMeta, ToolResult
from .parser import parse_skill_md, scan_and_load
from .registry import SkillRegistry

__version__ = "0.1.0"

__all__ = [
    # Core models (stdlib dataclasses, zero deps)
    "SkillSpec",
    "ToolMeta",
    "ToolResult",
    "FieldSchema",
    "RuntimeConfig",
    "Permissions",
    # Parser (Rust primary, stdlib fallback)
    "parse_skill_md",
    "scan_and_load",
    # Registry & executor
    "SkillRegistry",
    "SkillExecutor",
    # Decorators / helpers
    "skill_entry",
    "skill_success",
    "skill_error",
    "run_main",
    # Version
    "__version__",
]
