"""set_keyframe — Maya animation skill script.

In a real Maya environment this imports maya.cmds.
Here we provide a simulation-safe implementation for testing.
"""
from __future__ import annotations

import sys
import json
from typing import Any


def skill_entry(object: str, time: float, attribute: str = "translateX") -> dict[str, Any]:
    """Set a keyframe on *object* at *time* on *attribute*.

    Returns a dict that skill-native-sdk will wrap into a ToolResult.
    """
    try:
        import maya.cmds as cmds  # type: ignore[import]
        cmds.setKeyframe(object, attribute=attribute, time=time)
        message = f"Set keyframe on {object}.{attribute} at frame {time}"
    except ImportError:
        # Maya not available — simulation mode for testing
        message = f"[sim] Would set keyframe on {object}.{attribute} at frame {time}"

    return {
        "success": True,
        "message": message,
        "next_actions": ["get_keyframes", "bake_simulation"],
    }


if __name__ == "__main__":
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = skill_entry(**params)
    print(json.dumps(result))
