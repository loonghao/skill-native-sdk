"""MCP Adapter — expose a SkillRegistry as a standard MCP Server.

Usage::

    from skill_native_sdk import SkillRegistry
    from skill_native_sdk.adapters.mcp import MCPServer

    registry = SkillRegistry.from_path("./my-skills")
    server = MCPServer(registry)
    server.serve()  # stdio or HTTP, auto-generates tools/list + tools/call
"""
from .server import MCPServer

__all__ = ["MCPServer"]
