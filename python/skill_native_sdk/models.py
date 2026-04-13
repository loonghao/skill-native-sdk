"""SKILL.md v2 Pydantic models — the schema layer of skill-native-sdk."""
from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Union

if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal  # type: ignore[import]

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Input / Output field descriptors
# ---------------------------------------------------------------------------

class FieldSchema(BaseModel):
    type: Literal["string", "number", "boolean", "array", "object"] = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None


# ---------------------------------------------------------------------------
# On-success / on-error chain hints
# ---------------------------------------------------------------------------

class ChainHint(BaseModel):
    suggest: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Single tool declaration
# ---------------------------------------------------------------------------

class ToolMeta(BaseModel):
    name: str
    description: str = ""
    source_file: str | None = None

    # Safety semantics
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = False

    # Cost hints
    cost: Literal["low", "medium", "high", "external"] = "low"
    latency: Literal["fast", "normal", "slow"] = "fast"

    # I/O schemas
    input: Dict[str, FieldSchema] = Field(default_factory=dict)
    output: Dict[str, str] = Field(default_factory=dict)

    # Chain hints
    on_success: ChainHint = Field(default_factory=ChainHint)
    on_error: ChainHint = Field(default_factory=ChainHint)

    # Agent hint for preferred execution style
    agent_hint: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Runtime configuration
# ---------------------------------------------------------------------------

class RuntimeConfig(BaseModel):
    type: Literal["python", "rust", "wasm", "http", "subprocess"] = "python"
    entry: str = "skill_entry"
    interpreter: Optional[str] = None  # e.g. "mayapy", "hython"


# ---------------------------------------------------------------------------
# Permissions block
# ---------------------------------------------------------------------------

class Permissions(BaseModel):
    network: bool = False
    filesystem: Literal["none", "read", "write", "full"] = "none"
    external_api: bool = False





# ---------------------------------------------------------------------------
# Top-level SKILL.md v2 spec
# ---------------------------------------------------------------------------

class SkillSpec(BaseModel):
    """Parsed representation of a SKILL.md v2 file."""

    # Identity layer
    name: str
    domain: str = "generic"
    version: str = "1.0.0"
    description: str = ""
    tags: List[str] = Field(default_factory=list)

    # Tools
    tools: List[ToolMeta] = Field(default_factory=list)

    # Runtime bridge
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)

    # Permissions
    permissions: Permissions = Field(default_factory=Permissions)

    # Source directory (set by parser at load time, not in SKILL.md)
    source_dir: str = ""

    def get_tool(self, name: str) -> Optional[ToolMeta]:
        for t in self.tools:
            if t.name == name:
                return t
        return None

    @property
    def readonly_tools(self) -> List[ToolMeta]:
        return [t for t in self.tools if t.read_only]

    @property
    def entry_points(self) -> List[str]:
        """Tools that are not in any other tool's on_success/on_error suggest list."""
        mentioned: set[str] = set()
        for t in self.tools:
            mentioned.update(t.on_success.suggest)
            mentioned.update(t.on_error.suggest)
        return [t.name for t in self.tools if t.name not in mentioned]


# ---------------------------------------------------------------------------
# ToolResult — structured output from any skill execution
# ---------------------------------------------------------------------------

class ToolResult(BaseModel):
    """Structured result returned by any skill tool execution."""

    success: bool
    message: str = ""
    data: Any = None
    next_actions: List[str] = Field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, message: str = "", data: Any = None, next_actions: Optional[List[str]] = None) -> "ToolResult":
        return cls(success=True, message=message, data=data, next_actions=next_actions or [])

    @classmethod
    def fail(cls, error: str, message: str = "") -> "ToolResult":
        return cls(success=False, error=error, message=message)

    def to_toon(self) -> Dict[str, Any]:
        """Minimal token format for agent consumption."""
        return {
            "ok": self.success,
            "msg": self.message,
            "next": self.next_actions,
            **({"err": self.error} if self.error else {}),
            **({"data": self.data} if self.data is not None else {}),
        }

    def to_mcp(self) -> Dict[str, Any]:
        """Standard MCP tool_result format."""
        return {
            "type": "tool_result",
            "content": [{"type": "text", "text": self.message}],
            "isError": not self.success,
        }

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
