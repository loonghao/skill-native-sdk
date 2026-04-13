"""LangChain Tool adapter for skill-native-sdk.

Converts a SkillRegistry into a list of LangChain ``StructuredTool`` instances
with full ``args_schema`` so the LLM receives correct parameter types and
descriptions.

Usage::

    from skill_native_sdk import SkillRegistry
    from skill_native_sdk.adapters.langchain import to_langchain_tools

    registry = SkillRegistry.from_path("./my-skills")
    tools = to_langchain_tools(registry)
    # Pass `tools` to a LangChain agent or ReAct chain
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from ...executor import SkillExecutor
from ...models import FieldSchema, ToolMeta
from ...registry import SkillRegistry

# JSON-schema type → Python type mapping
_TYPE_MAP: Dict[str, Any] = {
    "string":  str,
    "number":  float,
    "integer": int,
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


def _build_args_schema(tool: ToolMeta) -> Optional[Type[Any]]:
    """Dynamically build a Pydantic model for the tool's input schema.

    Returns ``None`` if the tool has no inputs (LangChain handles that case).
    Pydantic is always available when LangChain is installed.
    """
    if not tool.input:
        return None

    try:
        from pydantic import Field
        from pydantic import create_model  # type: ignore[attr-defined]
    except ImportError:
        return None  # Graceful degradation — tool still works, just no schema

    fields: Dict[str, Any] = {}
    for fname, fs in tool.input.items():
        python_type = _TYPE_MAP.get(fs.type, str)
        field_kwargs: Dict[str, Any] = {"description": fs.description or fname}

        if fs.enum:
            # Represent enum as Literal when possible
            try:
                from typing import Literal  # Python 3.8+
                literal_type = Literal[tuple(fs.enum)]  # type: ignore[misc]
                python_type = literal_type
            except Exception:
                pass  # Fall back to plain type + description

        if fs.required:
            fields[fname] = (python_type, Field(..., **field_kwargs))
        else:
            default = fs.default if fs.default is not None else None
            fields[fname] = (Optional[python_type], Field(default=default, **field_kwargs))

    model_name = "".join(w.capitalize() for w in tool.name.split("_")) + "Input"
    return create_model(model_name, **fields)


def to_langchain_tools(registry: SkillRegistry) -> List[Any]:
    """Return a list of LangChain ``StructuredTool`` objects.

    Each tool carries a full ``args_schema`` (Pydantic model) so the LLM
    receives correct parameter types, descriptions, and enum constraints.

    Requires ``langchain-core`` to be installed::

        pip install skill-native-sdk[langchain]
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:
        raise ImportError(
            "langchain-core is required. "
            "Install it with: pip install skill-native-sdk[langchain]"
        ) from exc

    executor = SkillExecutor(registry)
    tools: List[Any] = []

    for spec in registry:
        for tool_meta in spec.tools:
            _skill_name = spec.name
            _tool_name = tool_meta.name

            # Build safety-aware description
            desc = tool_meta.description
            hints: List[str] = []
            if tool_meta.read_only:
                hints.append("read-only")
            if tool_meta.destructive:
                hints.append("⚠️ destructive — pass __confirmed__=true to execute")
            if tool_meta.idempotent:
                hints.append("idempotent/cacheable")
            if tool_meta.on_success.suggest:
                hints.append("on_success → [" + ", ".join(tool_meta.on_success.suggest) + "]")
            if hints:
                desc += " [" + ", ".join(hints) + "]"

            def _make_func(sn: str, tn: str):
                def _fn(**kwargs: Any) -> str:
                    result = executor.execute(sn, tn, dict(kwargs))
                    if result.success:
                        txt = result.message
                        if result.next_actions:
                            txt += "\n\nSuggested next: " + " → ".join(result.next_actions)
                        return txt
                    return f"Error: {result.error or result.message}"
                return _fn

            schema = _build_args_schema(tool_meta)
            lc_tool = StructuredTool.from_function(
                func=_make_func(_skill_name, _tool_name),
                name=f"{_skill_name}__{_tool_name}",
                description=desc,
                **({"args_schema": schema} if schema is not None else {}),
            )
            tools.append(lc_tool)

    return tools
