"""skill-native-sdk — SKILL.md → anywhere.

Write once in SKILL.md, deploy as MCP / OpenAI / LangChain / REST.
"""
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
