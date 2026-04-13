"""SkillRegistry — load, index, and query skills from a directory tree."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .models import SkillSpec, ToolMeta
from .parser import parse_skill_md, scan_and_load


class SkillRegistry:
    """Central registry for all loaded :class:`SkillSpec` objects."""

    def __init__(self) -> None:
        self._specs: dict[str, SkillSpec] = {}  # keyed by skill name

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_path(cls, directory: str | Path) -> "SkillRegistry":
        """Recursively scan *directory* and register all SKILL.md skills."""
        registry = cls()
        for spec in scan_and_load(directory):
            registry.register(spec)
        return registry

    @classmethod
    def from_spec(cls, spec: SkillSpec) -> "SkillRegistry":
        registry = cls()
        registry.register(spec)
        return registry

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def register(self, spec: SkillSpec) -> None:
        """Add a :class:`SkillSpec` to the registry (overwrites existing name)."""
        self._specs[spec.name] = spec

    def load_file(self, path: str | Path) -> SkillSpec | None:
        """Parse a single SKILL.md and register it. Returns the spec or None."""
        spec = parse_skill_md(path)
        if spec:
            self.register(spec)
        return spec

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get(self, name: str) -> SkillSpec | None:
        return self._specs.get(name)

    def list(self, domain: str | None = None) -> list[SkillSpec]:
        specs = list(self._specs.values())
        if domain:
            specs = [s for s in specs if s.domain == domain]
        return specs

    def get_tool(self, skill_name: str, tool_name: str) -> tuple[SkillSpec, ToolMeta] | None:
        spec = self.get(skill_name)
        if spec is None:
            return None
        tool = spec.get_tool(tool_name)
        if tool is None:
            return None
        return spec, tool

    def domains(self) -> list[str]:
        return sorted({s.domain for s in self._specs.values()})

    # ------------------------------------------------------------------
    # CapabilityGraph
    # ------------------------------------------------------------------

    def capability_graph(self, skill_name: str) -> dict:
        """Return the capability graph for a given skill (for LLM context)."""
        spec = self.get(skill_name)
        if spec is None:
            return {}

        graph: dict[str, dict] = {}
        for tool in spec.tools:
            graph[tool.name] = {
                "description": tool.description,
                "read_only": tool.read_only,
                "destructive": tool.destructive,
                "idempotent": tool.idempotent,
                "cost": tool.cost,
                "on_success": tool.on_success.suggest,
                "on_error": tool.on_error.suggest,
                "safe_to_parallelize_with": [
                    t.name for t in spec.tools
                    if t.name != tool.name and t.read_only and tool.read_only
                ],
            }

        return {
            "skill": skill_name,
            "domain": spec.domain,
            "entry_points": spec.entry_points,
            "graph": graph,
            "terminal_nodes": [
                t.name for t in spec.tools
                if not t.on_success.suggest and not t.on_error.suggest
            ],
        }

    # ------------------------------------------------------------------
    # Iteration
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[SkillSpec]:
        return iter(self._specs.values())

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, name: str) -> bool:
        return name in self._specs
