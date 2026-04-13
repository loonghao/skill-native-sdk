"""SKILL.md v2 data models — stdlib dataclasses, zero third-party dependencies."""
from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict, List, Optional


# ── FieldSchema ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class FieldSchema:
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    enum: Optional[List[Any]] = None


# ── ChainHint ─────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class ChainHint:
    suggest: List[str] = dataclasses.field(default_factory=list)


# ── RuntimeConfig ─────────────────────────────────────────────────────────────

@dataclasses.dataclass
class RuntimeConfig:
    type: str = "python"
    entry: str = "skill_entry"
    interpreter: Optional[str] = None


# ── Permissions ───────────────────────────────────────────────────────────────

@dataclasses.dataclass
class Permissions:
    network: bool = False
    filesystem: str = "none"
    external_api: bool = False


# ── ToolMeta ──────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class ToolMeta:
    name: str = ""
    description: str = ""
    source_file: Optional[str] = None

    # Safety semantics
    read_only: bool = True
    destructive: bool = False
    idempotent: bool = False

    # Cost hints
    cost: str = "low"
    latency: str = "fast"

    # I/O schemas
    input: Dict[str, FieldSchema] = dataclasses.field(default_factory=dict)
    output: Dict[str, str] = dataclasses.field(default_factory=dict)

    # Chain hints
    on_success: ChainHint = dataclasses.field(default_factory=ChainHint)
    on_error: ChainHint = dataclasses.field(default_factory=ChainHint)

    # Agent hints
    agent_hint: Dict[str, Any] = dataclasses.field(default_factory=dict)


# ── SkillSpec ─────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class SkillSpec:
    """Parsed representation of a SKILL.md v2 file."""

    name: str = ""
    domain: str = "generic"
    version: str = "1.0.0"
    description: str = ""
    tags: List[str] = dataclasses.field(default_factory=list)
    tools: List[ToolMeta] = dataclasses.field(default_factory=list)
    runtime: RuntimeConfig = dataclasses.field(default_factory=RuntimeConfig)
    permissions: Permissions = dataclasses.field(default_factory=Permissions)
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
        mentioned: set = set()
        for t in self.tools:
            mentioned.update(t.on_success.suggest)
            mentioned.update(t.on_error.suggest)
        return [t.name for t in self.tools if t.name not in mentioned]


# ── ToolResult ────────────────────────────────────────────────────────────────

@dataclasses.dataclass
class ToolResult:
    """Structured, protocol-agnostic result from a skill tool execution."""

    success: bool = True
    message: str = ""
    data: Any = None
    next_actions: List[str] = dataclasses.field(default_factory=list)
    error: Optional[str] = None
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

    # ── Constructors ──────────────────────────────────────────────────────────

    @classmethod
    def ok(
        cls,
        message: str = "",
        data: Any = None,
        next_actions: Optional[List[str]] = None,
    ) -> "ToolResult":
        return cls(success=True, message=message, data=data, next_actions=next_actions or [])

    @classmethod
    def fail(cls, error: str, message: str = "") -> "ToolResult":
        return cls(success=False, error=error, message=message or error)

    # ── Serialisation formats ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """Full dict — always JSON-serializable."""
        return dataclasses.asdict(self)

    def to_toon(self) -> Dict[str, Any]:
        """Minimal token format (~3-5× fewer tokens than full JSON)."""
        out: Dict[str, Any] = {"ok": self.success, "msg": self.message, "next": self.next_actions}
        if self.error:
            out["err"] = self.error
        if self.data is not None:
            out["data"] = self.data
        return out

    def to_mcp(self) -> Dict[str, Any]:
        """MCP tool_result wire format."""
        return {
            "type": "tool_result",
            "content": [{"type": "text", "text": self.message}],
            "isError": not self.success,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
