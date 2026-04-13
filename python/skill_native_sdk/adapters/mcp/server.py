"""MCPServer — generate a full MCP-compatible server from a SkillRegistry."""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from ...executor import SkillExecutor
from ...models import ToolMeta
from ...registry import SkillRegistry


def _tool_to_mcp_schema(skill_name: str, tool: ToolMeta) -> Dict[str, Any]:
    """Convert a ToolMeta to MCP tools/list entry format."""
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for field_name, field_schema in tool.input.items():
        prop: Dict[str, Any] = {"type": field_schema.type, "description": field_schema.description}
        if field_schema.enum:
            prop["enum"] = field_schema.enum
        if field_schema.default is not None:
            prop["default"] = field_schema.default
        properties[field_name] = prop
        if field_schema.required:
            required.append(field_name)

    # Build description with safety hints
    description = tool.description
    hints: List[str] = []
    if tool.read_only:
        hints.append("read-only")
    if tool.destructive:
        hints.append("⚠️ DESTRUCTIVE — requires confirmation")
    if tool.idempotent:
        hints.append("idempotent/cacheable")
    if tool.on_success.suggest:
        next_str = ", ".join(tool.on_success.suggest)
        hints.append(f"on_success → [{next_str}]")
    if hints:
        description += f" [{', '.join(hints)}]"

    return {
        "name": f"{skill_name}__{tool.name}",  # namespaced to avoid collisions
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
        "_skill": skill_name,
        "_tool": tool.name,
    }


class MCPServer:
    """A minimal MCP server implementation backed by a :class:`SkillRegistry`.

    Supports stdio transport (default) and can be extended for HTTP.

    Features over hand-written MCP servers:
    - ``destructive`` tools trigger a confirmation step
    - ``read_only`` tools are marked for potential parallel scheduling
    - ``idempotent`` tools are marked for caching
    - ``on_success`` hints are injected into results automatically
    """

    def __init__(self, registry: SkillRegistry, name: str = "skill-native-sdk") -> None:
        self.registry = registry
        self.executor = SkillExecutor(registry)
        self.name = name
        self._tools: List[Dict[str, Any]] = self._build_tool_list()

    def _build_tool_list(self) -> List[Dict[str, Any]]:
        tools = []
        for spec in self.registry:
            for tool in spec.tools:
                tools.append(_tool_to_mcp_schema(spec.name, tool))
        return tools

    # ------------------------------------------------------------------
    # MCP message handlers
    # ------------------------------------------------------------------

    def handle_initialize(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": msg.get("id"),
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self.name, "version": "0.1.0"},
            },
        }

    def handle_tools_list(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        public_tools = [{k: v for k, v in t.items() if not k.startswith("_")} for t in self._tools]
        return {"jsonrpc": "2.0", "id": msg.get("id"), "result": {"tools": public_tools}}

    def handle_tools_call(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        params = msg.get("params", {})
        tool_name: str = params.get("name", "")
        arguments: Dict[str, Any] = params.get("arguments", {})

        # Find the matching tool entry
        entry = next((t for t in self._tools if t["name"] == tool_name), None)
        if entry is None:
            return self._error(msg, -32602, f"Unknown tool: {tool_name}")

        skill_name = entry["_skill"]
        real_tool = entry["_tool"]

        # Safety check for destructive tools
        spec_tool = self.registry.get(skill_name)
        if spec_tool:
            tool_meta = spec_tool.get_tool(real_tool)
            if tool_meta and tool_meta.destructive:
                confirmed = arguments.pop("__confirmed__", False)
                if not confirmed:
                    return {
                        "jsonrpc": "2.0", "id": msg.get("id"),
                        "result": {"content": [{"type": "text", "text":
                            f"⚠️ Tool '{real_tool}' is destructive. "
                            "Re-call with __confirmed__=true to proceed."}],
                            "isError": False},
                    }

        result = self.executor.execute(skill_name, real_tool, arguments)

        # Inject on_success hints into result message
        if result.success and result.next_actions:
            next_str = " → ".join(result.next_actions)
            result.message += f"\n\nSuggested next: {next_str}"

        return {"jsonrpc": "2.0", "id": msg.get("id"), "result": result.to_mcp()}

    def _error(self, msg: dict, code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": code, "message": message}}

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------

    def handle_message(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = msg.get("method", "")
        if method == "initialize":
            return self.handle_initialize(msg)
        if method == "tools/list":
            return self.handle_tools_list(msg)
        if method == "tools/call":
            return self.handle_tools_call(msg)
        if method == "notifications/initialized":
            return None  # no response needed
        return self._error(msg, -32601, f"Method not found: {method}")

    def serve(self, transport: str = "stdio") -> None:
        """Start the MCP server.

        Args:
            transport: ``"stdio"`` (default) reads JSON-RPC from stdin line by line.
        """
        if transport != "stdio":
            raise NotImplementedError(f"Transport '{transport}' not yet supported. Use 'stdio'.")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                response = self.handle_message(msg)
                if response is not None:
                    sys.stdout.write(json.dumps(response) + "\n")
                    sys.stdout.flush()
            except json.JSONDecodeError:
                pass
