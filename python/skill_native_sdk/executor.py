"""SkillExecutor — run skill scripts from the registry."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

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
        params: Optional[Dict[str, Any]] = None,
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
        self, spec: SkillSpec, tool: ToolMeta, params: Dict[str, Any]
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
        self, spec: SkillSpec, tool: ToolMeta, params: Dict[str, Any]
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
        self, spec: SkillSpec, tool: ToolMeta, params: Dict[str, Any]
    ) -> ToolResult:
        """Execute a tool over HTTP/JSON — zero third-party deps (urllib).

        URL resolution (first match wins):
        1. ``runtime.interpreter``  — treated as a base URL, e.g. ``http://localhost:8000``
        2. ``runtime.entry``        — used as-is if it starts with ``http``
        3. Fallback                 — ``http://localhost:8000/{skill_name}/{tool_name}``

        The server must accept ``POST <url>/{tool_name}`` with a JSON body of
        ``{"params": {...}}`` and respond with a JSON body that maps to
        :class:`ToolResult` fields (``success``, ``message``, ``error``, etc.).
        """
        import urllib.error
        import urllib.request

        # Resolve target URL
        base = spec.runtime.interpreter or spec.runtime.entry
        if base and base.startswith(("http://", "https://")):
            url = base.rstrip("/") + f"/{tool.name}"
        else:
            url = f"http://localhost:8000/{spec.name}/{tool.name}"

        body = json.dumps({"params": params}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                if isinstance(data, dict):
                    return ToolResult(
                        success=bool(data.get("success", True)),
                        message=str(data.get("message", "")),
                        error=data.get("error") or None,
                        data=data.get("data"),
                        next_actions=list(data.get("next_actions") or []),
                    )
                # Unwrapped plain value
                return ToolResult.ok(str(data), data=data)

        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            return ToolResult.fail(
                error=f"HTTP {exc.code} {exc.reason}: {body_text[:200]}",
                message=f"HTTP error calling {url}",
            )
        except urllib.error.URLError as exc:
            return ToolResult.fail(
                error=f"Connection error: {exc.reason}",
                message=f"Cannot reach {url}",
            )
        except json.JSONDecodeError as exc:
            return ToolResult.fail(error=f"Invalid JSON response: {exc}")
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(error=f"{type(exc).__name__}: {exc}")
