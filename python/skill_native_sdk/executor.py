"""SkillExecutor — run skill scripts from the registry."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from .models import SkillSpec, ToolMeta, ToolResult
from .registry import SkillRegistry


class SkillExecutor:
    """Execute skill tools referenced in a :class:`SkillRegistry`."""

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def execute(
        self,
        skill_name: str,
        tool_name: str,
        params: dict[str, Any] | None = None,
        output_format: str = "json",
    ) -> ToolResult:
        """Execute a tool from a skill.

        Args:
            skill_name: Name of the skill (matches SKILL.md ``name`` field).
            tool_name:  Name of the tool within the skill.
            params:     Input parameters dict.
            output_format: One of ``"json"``, ``"toon"``, ``"mcp"``.

        Returns:
            A :class:`ToolResult`.
        """
        pair = self.registry.get_tool(skill_name, tool_name)
        if pair is None:
            return ToolResult.fail(
                error=f"Tool '{tool_name}' not found in skill '{skill_name}'",
            )

        spec, tool = pair
        params = params or {}

        runtime = spec.runtime.type

        if runtime == "python":
            return self._run_python_inprocess(spec, tool, params)
        elif runtime == "subprocess":
            return self._run_subprocess(spec, tool, params)
        elif runtime == "http":
            return self._run_http(spec, tool, params)
        else:
            return ToolResult.fail(error=f"Unsupported runtime type: {runtime}")

    # ------------------------------------------------------------------
    # Runtime implementations
    # ------------------------------------------------------------------

    def _run_python_inprocess(
        self, spec: SkillSpec, tool: ToolMeta, params: dict[str, Any]
    ) -> ToolResult:
        """Import and call a Python skill script in-process."""
        if not tool.source_file:
            return ToolResult.fail(error=f"Tool '{tool.name}' has no source_file")

        script_path = Path(spec.source_dir) / tool.source_file
        if not script_path.exists():
            return ToolResult.fail(error=f"Script not found: {script_path}")

        try:
            module_name = f"_skill_{spec.name}_{tool.name}"
            spec_obj = importlib.util.spec_from_file_location(module_name, script_path)
            if spec_obj is None or spec_obj.loader is None:
                return ToolResult.fail(error=f"Cannot load module: {script_path}")

            module = importlib.util.module_from_spec(spec_obj)
            spec_obj.loader.exec_module(module)  # type: ignore[union-attr]

            entry = getattr(module, spec.runtime.entry, None)
            if entry is None:
                return ToolResult.fail(
                    error=f"Entry '{spec.runtime.entry}' not found in {script_path}"
                )

            result = entry(**params)
            if isinstance(result, ToolResult):
                return result
            return ToolResult.ok(str(result), data=result)

        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(error=f"{type(exc).__name__}: {exc}")

    def _run_subprocess(
        self, spec: SkillSpec, tool: ToolMeta, params: dict[str, Any]
    ) -> ToolResult:
        """Run a skill script as a subprocess (supports mayapy / hython etc.)."""
        if not tool.source_file:
            return ToolResult.fail(error=f"Tool '{tool.name}' has no source_file")

        script_path = Path(spec.source_dir) / tool.source_file
        interpreter = spec.runtime.interpreter or sys.executable

        try:
            proc = subprocess.run(
                [interpreter, str(script_path), json.dumps(params)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode != 0:
                return ToolResult.fail(error=proc.stderr or "subprocess failed")

            data = json.loads(proc.stdout)
            return ToolResult(**data)

        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(error=f"{type(exc).__name__}: {exc}")

    def _run_http(
        self, spec: SkillSpec, tool: ToolMeta, params: dict[str, Any]
    ) -> ToolResult:
        """Placeholder for HTTP bridge execution."""
        return ToolResult.fail(error="HTTP runtime not yet implemented")
