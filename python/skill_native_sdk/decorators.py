"""Decorators and helpers for skill entry points.

Inspired by (but not copied from) dcc-mcp-core's skill.py.
Our version preserves ToolResult as the return type and adds
``prompt`` / ``context`` fields for AI-agent guidance.
"""
from __future__ import annotations

import functools
import inspect
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .models import ToolResult

F = TypeVar("F", bound=Callable[..., Any])

# ---------------------------------------------------------------------------
# Bundled skills directory helpers
# ---------------------------------------------------------------------------

# The ``skills/`` subdirectory is co-located with this module inside the wheel.
_BUNDLED_SKILLS_DIR: Path = Path(__file__).parent / "skills"


def get_bundled_skills_dir() -> str:
    """Return the absolute path to the bundled skills directory.

    The directory contains the general-purpose skill packages shipped with
    ``skill-native-sdk`` (hello-world, maya-animation, invoice-parser, etc.).

    Returns:
        Absolute path string.  The directory is guaranteed to exist when the
        package is installed from a wheel; it may not exist in editable/source
        installs unless ``skills/examples/`` was copied to the package.
    """
    return str(_BUNDLED_SKILLS_DIR)


def get_bundled_skill_paths(include_bundled: bool = True) -> List[str]:
    """Return a list containing the bundled skills directory (when it exists).

    Convenience wrapper used by DCC adapters to build their skill search path.
    Pass ``include_bundled=False`` to disable bundled skills entirely.

    Args:
        include_bundled: If ``False``, return an empty list so callers can
            easily opt-out of the bundled skills.

    Returns:
        A list with the bundled skills directory path, or ``[]`` if the
        directory does not exist or ``include_bundled`` is ``False``.
    """
    if not include_bundled:
        return []
    bundled = _BUNDLED_SKILLS_DIR
    return [str(bundled)] if bundled.is_dir() else []


# ---------------------------------------------------------------------------
# Skill entry decorator
# ---------------------------------------------------------------------------


def skill_entry(func: F) -> F:
    """Mark a function as a skill entry point.

    Wraps the function so that:
    - ``ImportError`` (DCC module missing) is caught and returned as a structured error.
    - Generic ``Exception`` is caught and returned as ``ToolResult.fail(...)``
    - Plain return values are wrapped in ``ToolResult.ok(...)``
    - Already-returned ``ToolResult`` objects pass through unchanged

    The decorator preserves ``__name__``, ``__doc__``, and ``__module__`` of
    the original function via ``functools.wraps``.
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
        except ImportError as exc:
            dcc_name = _guess_dcc_from_import_error(exc)
            return ToolResult.fail(
                error=repr(exc),
                message=f"{dcc_name} is not available in this environment",
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult.fail(
                error=f"{type(exc).__name__}: {exc}",
                message=f"Error in {func.__name__}",
            )

    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Result builder helpers (borrowing dcc-mcp-core conventions, our style)
# ---------------------------------------------------------------------------


def skill_success(
    message: str,
    data: Any = None,
    next_actions: Optional[List[str]] = None,
    prompt: Optional[str] = None,
    **context: Any,
) -> ToolResult:
    """Convenience helper — build a successful :class:`ToolResult`.

    Args:
        message: Human-readable summary of what was accomplished.
        data: Primary result payload (e.g. a dict or list).
        next_actions: Suggested follow-up tool names for chaining.
        prompt: Optional AI guidance hint (e.g. "Inspect the viewport").
        **context: Arbitrary key/value pairs stored in ``metadata``.

    Returns:
        A successful :class:`ToolResult`.
    """
    result = ToolResult.ok(message=message, data=data, next_actions=next_actions or [])
    if prompt:
        result.metadata["prompt"] = prompt
    if context:
        result.metadata.update(context)
    return result


def skill_error(
    message: str,
    error: str = "",
    prompt: Optional[str] = None,
    possible_solutions: Optional[List[str]] = None,
    **context: Any,
) -> ToolResult:
    """Convenience helper — build a failed :class:`ToolResult`.

    Args:
        message: User-facing description of what went wrong.
        error: Technical error string (exception repr, error code …).
        prompt: Optional recovery hint for the AI agent.
        possible_solutions: Actionable suggestions stored in ``metadata``.
        **context: Additional key/value pairs stored in ``metadata``.

    Returns:
        A failed :class:`ToolResult`.
    """
    result = ToolResult.fail(error=error or message, message=message)
    result.metadata["prompt"] = prompt or "Check the error details and try again."
    if possible_solutions:
        result.metadata["possible_solutions"] = possible_solutions
    if context:
        result.metadata.update(context)
    return result


def skill_warning(
    message: str,
    warning: str = "",
    prompt: Optional[str] = None,
    **context: Any,
) -> ToolResult:
    """Build a success-but-with-warning :class:`ToolResult`.

    The action succeeded, but there is something the caller should be aware of.

    Args:
        message: Summary of what was done.
        warning: Description of the condition that should be noted.
        prompt: Optional follow-up hint for the AI agent.
        **context: Additional key/value pairs stored in ``metadata``.

    Returns:
        A successful :class:`ToolResult` with ``metadata["warning"]`` set.
    """
    result = ToolResult.ok(message=message)
    result.metadata["warning"] = warning
    if prompt:
        result.metadata["prompt"] = prompt
    if context:
        result.metadata.update(context)
    return result


def skill_exception(
    exc: BaseException,
    message: Optional[str] = None,
    prompt: Optional[str] = None,
    include_traceback: bool = True,
    possible_solutions: Optional[List[str]] = None,
    **context: Any,
) -> ToolResult:
    """Build a failed :class:`ToolResult` from an exception.

    Captures the exception type, repr, and optionally the full traceback.

    Args:
        exc: The caught exception.
        message: Optional custom message.  Defaults to ``"Error: <exc>"``.
        prompt: Optional recovery hint.
        include_traceback: When ``True`` (default), attach the formatted traceback.
        possible_solutions: Optional list of actionable suggestions.
        **context: Additional key/value pairs stored in ``metadata``.

    Returns:
        A failed :class:`ToolResult`.
    """
    error_str = repr(exc)
    meta: Dict[str, Any] = {"error_type": type(exc).__name__}
    if include_traceback:
        meta["traceback"] = traceback.format_exc()
    if possible_solutions:
        meta["possible_solutions"] = possible_solutions
    meta.update(context)

    result = ToolResult.fail(
        error=error_str,
        message=message or f"Error: {exc}",
    )
    result.metadata["prompt"] = prompt or "Check the error details and try again."
    result.metadata.update(meta)
    return result


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

    try:
        result: ToolResult = entry_fn(**filtered)
        if not isinstance(result, ToolResult):
            # Bare return value — wrap it
            result = ToolResult.ok(str(result), data=result) if result is not None else ToolResult.ok(f"{entry_fn.__name__} completed")
    except Exception as exc:  # noqa: BLE001
        result = ToolResult.fail(
            error=f"{type(exc).__name__}: {exc}",
            message=f"Unhandled error in {entry_fn.__name__}",
        )

    if output == "toon":
        print(json.dumps(result.to_toon()))
    elif output == "mcp":
        print(json.dumps(result.to_mcp()))
    else:
        print(json.dumps(result.to_dict()))
    sys.exit(0 if result.success else 1)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _guess_dcc_from_import_error(exc: ImportError) -> str:
    """Best-effort guess of the DCC name from an ImportError message."""
    msg = str(exc).lower()
    for dcc in ("maya", "houdini", "nuke", "blender", "cinema4d", "3dsmax", "unreal"):
        if dcc in msg:
            return dcc.capitalize()
    if exc.name:
        top = exc.name.split(".")[0]
        return top
    return "DCC"
