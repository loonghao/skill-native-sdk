"""OpenAI function-calling adapter for skill-native-sdk."""
from __future__ import annotations

from typing import Any

from ...models import ToolMeta
from ...registry import SkillRegistry


def to_openai_functions(registry: SkillRegistry) -> list[dict[str, Any]]:
    """Convert a SkillRegistry to OpenAI function-calling format.

    Returns a list of ``{"type": "function", "function": {...}}`` dicts
    suitable for passing to ``openai.chat.completions.create(tools=...)``.
    """
    functions = []
    for spec in registry:
        for tool in spec.tools:
            functions.append(_tool_to_openai(spec.name, tool))
    return functions


def _tool_to_openai(skill_name: str, tool: ToolMeta) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []

    for field_name, field_schema in tool.input.items():
        prop: dict[str, Any] = {"type": field_schema.type, "description": field_schema.description}
        if field_schema.enum:
            prop["enum"] = field_schema.enum
        properties[field_name] = prop
        if field_schema.required:
            required.append(field_name)

    return {
        "type": "function",
        "function": {
            "name": f"{skill_name}__{tool.name}",
            "description": tool.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
