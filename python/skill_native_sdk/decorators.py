"""Decorators for skill entry points."""
from __future__ import annotations

import functools
import inspect
import sys
from typing import Any, Callable, List, Optional, TypeVar

from .models import ToolResult

F = TypeVar("F", bound=Callable[..., Any])


def skill_entry(func: F) -> F:
    """Mark a function as a skill entry point.

    Wraps the function so that:
    - Exceptions are caught and returned as ``ToolResult.fail(...)``
    - Plain return values are wrapped in ``ToolResult.ok(...)``
    - Already-returned ``ToolResult`` objects pass through unchanged
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        try:
            result = func(*args, **kwargs)
            if isinstance(result, ToolResult):
                return result
            if result is None:
                return ToolResult.ok(f"{func.__name__} completed")
            return ToolResult.ok(str(result), data=result)
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(
                error=f"{type(exc).__name__}: {exc}",
                message=f"Error in {func.__name__}",
            )

    return wrapper  # type: ignore[return-value]


def skill_success(message: str, data: Any = None, next_actions: Optional[List[str]] = None) -> ToolResult:
    """Convenience helper — build a successful :class:`ToolResult`."""
    return ToolResult.ok(message=message, data=data, next_actions=next_actions or [])


def skill_error(error: str, message: str = "") -> ToolResult:
    """Convenience helper — build a failed :class:`ToolResult`."""
    return ToolResult.fail(error=error, message=message)


# ---------------------------------------------------------------------------
# run_main — allow skills to be executed as scripts directly
# ---------------------------------------------------------------------------

def run_main(entry_fn: Callable[..., ToolResult], output: str = "json") -> None:
    """Execute *entry_fn* from CLI arguments and print the result.

    Usage at the bottom of a skill script::

        if __name__ == "__main__":
            run_main(my_skill_function)
    """
    import json

    # Very simple: parse --key value pairs from sys.argv
    params: Any = {}
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i][2:]
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                params[key] = args[i + 1]
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1

    # Filter to only params accepted by the function
    sig = inspect.signature(entry_fn)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}

    result: ToolResult = entry_fn(**filtered)

    if output == "toon":
        print(json.dumps(result.to_toon()))
    elif output == "mcp":
        print(json.dumps(result.to_mcp()))
    else:
        print(json.dumps(result.to_dict()))
