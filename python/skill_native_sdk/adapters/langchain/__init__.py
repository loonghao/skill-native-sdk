"""LangChain Tool adapter for skill-native-sdk.

Converts a SkillRegistry into a list of LangChain ``BaseTool`` instances.

Usage::

    from skill_native_sdk import SkillRegistry
    from skill_native_sdk.adapters.langchain import to_langchain_tools

    registry = SkillRegistry.from_path("./my-skills")
    tools = to_langchain_tools(registry)
    # Pass `tools` to a LangChain agent or chain
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...executor import SkillExecutor
from ...registry import SkillRegistry

if TYPE_CHECKING:
    pass


def to_langchain_tools(registry: SkillRegistry) -> list[Any]:
    """Return a list of LangChain ``StructuredTool`` objects.

    Requires ``langchain-core`` to be installed::

        pip install skill-native-sdk[langchain]
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as e:
        raise ImportError(
            "langchain-core is required. Install it with: pip install skill-native-sdk[langchain]"
        ) from e

    executor = SkillExecutor(registry)
    tools = []

    for spec in registry:
        for tool_meta in spec.tools:
            _skill_name = spec.name
            _tool_name = tool_meta.name
            _description = tool_meta.description

            def _make_func(sn: str, tn: str):  # closure capture
                def _fn(**kwargs: Any) -> str:
                    result = executor.execute(sn, tn, kwargs)
                    return result.message if result.success else f"Error: {result.error}"
                return _fn

            lc_tool = StructuredTool.from_function(
                func=_make_func(_skill_name, _tool_name),
                name=f"{_skill_name}__{_tool_name}",
                description=_description,
            )
            tools.append(lc_tool)

    return tools
