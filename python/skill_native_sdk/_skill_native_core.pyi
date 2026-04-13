"""Type stubs for the compiled Rust extension `_skill_native_core`.

Available after::

    maturin develop --features python-bindings,ext-module

New in progressive-loading release:
    SkillScope, SkillMetadata, ScanError, ScanOutcome, SkillsManager, run_cli
"""
from __future__ import annotations
from typing import Any, Optional

__version__: str
__author__: str

# ── From skill-schema — scope & progressive discovery ─────────────────────────

class SkillScope:
    """Priority scope of a discovered skill.

    Ordering: ``Repo`` (highest) > ``User`` > ``System`` (lowest).
    """
    @property
    def rank(self) -> int:
        """Numeric priority (0 = Repo, 1 = User, 2 = System)."""
        ...
    def as_str(self) -> str:
        """One of ``"repo"``, ``"user"``, ``"system"``."""
        ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...


class SkillMetadata:
    """Lightweight skill record populated during discovery.

    Only ``name``, ``description``, and index fields are read from disk.
    Call :meth:`load` to obtain the full :class:`RustSkillSpec`.
    """
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def domain(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def tags(self) -> list[str]: ...
    @property
    def scope(self) -> SkillScope: ...
    @property
    def path_to_skill_md(self) -> str: ...
    @property
    def source_dir(self) -> str: ...
    def load(self) -> RustSkillSpec:
        """Lazily parse the full ``RustSkillSpec`` from disk."""
        ...
    def __repr__(self) -> str: ...


class ScanError:
    """A ``SKILL.md`` that failed to parse during discovery."""
    @property
    def path(self) -> str: ...
    @property
    def message(self) -> str: ...
    def __repr__(self) -> str: ...


class ScanOutcome:
    """Result of a :class:`SkillsManager` discovery scan.

    ``metadata`` is sorted by scope priority (Repo first), then name.
    """
    @property
    def metadata(self) -> list[SkillMetadata]:
        """Lightweight records — no full YAML parse."""
        ...
    @property
    def errors(self) -> list[ScanError]:
        """Skills that could not be parsed."""
        ...
    def __len__(self) -> int: ...
    def find(self, name: str) -> Optional[SkillMetadata]:
        """Find a skill by name, or ``None``."""
        ...
    def __repr__(self) -> str: ...


class SkillsManager:
    """Progressive skill discovery manager with layered roots and cwd-keyed cache.

    Example::

        mgr = SkillsManager()
        outcome = mgr.scan_for_cwd(".")
        for meta in outcome.metadata:
            print(meta.scope, meta.name)
            spec = meta.load()          # lazy — reads YAML only here
    """
    def __init__(self) -> None: ...
    def scan_for_cwd(self, cwd: str, force_reload: bool = False) -> ScanOutcome:
        """Discover skills from cwd upward (Repo) and ``~/.skill-native/skills`` (User)."""
        ...
    def load_skill(self, path: str) -> RustSkillSpec:
        """Lazily load the full ``RustSkillSpec`` from a ``SKILL.md`` path."""
        ...
    def clear_cache(self) -> None:
        """Invalidate the in-process discovery cache."""
        ...


# ── From skill-schema ────────────────────────────────────────────────────────

class ToolMeta:
    """Metadata for a single tool from a SKILL.md v2 file."""
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def source_file(self) -> str | None: ...
    @property
    def read_only(self) -> bool: ...
    @property
    def destructive(self) -> bool: ...
    @property
    def idempotent(self) -> bool: ...
    @property
    def cost(self) -> str: ...
    @property
    def latency(self) -> str: ...
    @property
    def on_success_suggest(self) -> list[str]: ...
    @property
    def on_error_suggest(self) -> list[str]: ...
    def input_fields(self) -> dict[str, dict[str, Any]]: ...
    def __repr__(self) -> str: ...


class RustSkillSpec:
    """Parsed SKILL.md v2 specification (Rust implementation, ~10× faster parse)."""
    @property
    def name(self) -> str: ...
    @property
    def domain(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def tags(self) -> list[str]: ...
    @property
    def source_dir(self) -> str: ...
    @property
    def scope(self) -> SkillScope:
        """Priority scope this skill was discovered under."""
        ...
    @property
    def path_to_skill_md(self) -> str:
        """Absolute path to the ``SKILL.md`` file (empty when parsed from string)."""
        ...
    @property
    def runtime_type(self) -> str: ...
    @property
    def runtime_entry(self) -> str: ...
    @property
    def runtime_interpreter(self) -> str | None: ...
    @property
    def perm_network(self) -> bool: ...
    @property
    def perm_filesystem(self) -> str: ...
    @property
    def perm_external_api(self) -> bool: ...
    def tools(self) -> list[ToolMeta]: ...
    def get_tool(self, name: str) -> ToolMeta | None: ...
    def entry_points(self) -> list[str]: ...
    def readonly_tools(self) -> list[ToolMeta]: ...
    def __repr__(self) -> str: ...


def parse_skill_md(path: str) -> RustSkillSpec | None:
    """Parse a SKILL.md file or directory.

    Returns ``None`` if no SKILL.md found.
    Raises ``ValueError`` on YAML parse errors.
    Raises ``IOError`` on file read errors.
    """
    ...

def scan_and_load(directory: str) -> list[RustSkillSpec]:
    """Recursively scan *directory* for SKILL.md files.

    Skills that fail to parse are silently skipped.
    """
    ...

# ── From skill-core ──────────────────────────────────────────────────────────

class RustToolResult:
    """Structured tool execution result (Rust implementation).

    JSON serialization::

        result.to_json()           # str — preferred
        result.to_dict()           # dict — for Pydantic interop
        result.to_toon()           # dict — minimal token format
        result.to_mcp()            # dict — MCP tool_result format
    """
    def __init__(
        self,
        success: bool = True,
        message: str = "",
        error: str | None = None,
    ) -> None: ...
    @staticmethod
    def ok(message: str) -> RustToolResult: ...
    @staticmethod
    def fail(error: str) -> RustToolResult: ...
    @property
    def success(self) -> bool: ...
    @property
    def message(self) -> str: ...
    @property
    def error(self) -> str | None: ...
    @property
    def next_actions(self) -> list[str]: ...
    def to_json(self) -> str: ...
    def to_dict(self) -> dict[str, Any]: ...
    def to_toon(self) -> dict[str, Any]: ...
    def to_mcp(self) -> dict[str, Any]: ...
    def __repr__(self) -> str: ...


class SafetyChecker:
    """Enforces SKILL.md v2 safety semantics.

    Decision is one of: ``"allow"``, ``"confirm"``, ``"block"``.

    Example::

        checker = SafetyChecker(block_destructive=False)
        decision, reason = checker.check("delete_mesh", destructive=True, cost="low", confirmed=False)
        # decision == "confirm"
        # reason == "⚠️ Tool 'delete_mesh' is destructive..."
    """
    def __init__(
        self,
        block_destructive: bool = False,
        block_external_cost: bool = False,
    ) -> None: ...
    def check(
        self,
        tool_name: str,
        destructive: bool,
        cost: str,
        confirmed: bool,
    ) -> tuple[str, str]:
        """Returns ``(decision, reason)`` where decision is one of:
        ``"allow"``, ``"confirm"``, ``"block"``.
        """
        ...


def plan_execution(skill_json: str, tool_names: list[str]) -> list[list[str]]:
    """Build a DAG execution plan for the given tools.

    Returns a list of stages where tools in each stage can run in parallel.

    Example::

        stages = plan_execution(skill_json, ["get_a", "get_b", "write_c"])
        # [["get_a", "get_b"], ["write_c"]]  — get_a/b are read_only → parallel
    """
    ...

# ── From skill-runtime ───────────────────────────────────────────────────────

SUBPROCESS_BRIDGE: str
HTTP_BRIDGE: str
PYTHON_BRIDGE: str

# ── From skill-cli ────────────────────────────────────────────────────────────

def run_cli(args: list[str]) -> int:
    """Run the ``skn`` CLI with the given argument list.

    Typically called as::

        import sys
        from skill_native_sdk._skill_native_core import run_cli
        sys.exit(run_cli(sys.argv))

    Args:
        args: Argument list where ``args[0]`` is the program name
              (pass ``sys.argv`` directly).

    Returns:
        OS exit code — ``0`` for success, non-zero for failure.

    Subcommands::

        run_cli(["skn", "list"])
        run_cli(["skn", "list", "--domain", "maya"])
        run_cli(["skn", "describe", "maya-animation"])
        run_cli(["skn", "run", "maya-animation", "set_keyframe",
                 "--params", '{"object":"pCube1","time":24}'])
        run_cli(["skn", "chain", "maya-animation", "--entry", "set_keyframe",
                 "--follow-success"])
        run_cli(["skn", "graph", "maya-animation"])
    """
    ...
