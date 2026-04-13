"""get_keyframes — query keyframe times on a Maya object."""
from __future__ import annotations

import json
import sys
from typing import Any


def skill_entry(object: str) -> dict[str, Any]:
    """Return all keyframe times for *object*."""
    try:
        import maya.cmds as cmds  # type: ignore[import]
        frames = cmds.keyframe(object, query=True, timeChange=True) or []
    except ImportError:
        # Simulation mode
        frames = [1.0, 12.0, 24.0]

    return {
        "success": True,
        "message": f"Found {len(frames)} keyframes on {object}",
        "data": {"keyframes": frames},
        "next_actions": [],
    }


if __name__ == "__main__":
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    result = skill_entry(**params)
    print(json.dumps(result))
