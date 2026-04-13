"""bake_simulation — bake simulation to keyframes on a Maya object."""
from __future__ import annotations

import json
import sys
from typing import Any


def skill_entry(object: str, start_frame: float, end_frame: float) -> dict[str, Any]:
    """Bake simulation to keyframes for *object* over [start_frame, end_frame]."""
    try:
        import maya.standalone  # type: ignore[import]
        maya.standalone.initialize()
        import maya.cmds as cmds  # type: ignore[import]
        cmds.bakeResults(
            object,
            simulation=True,
            time=(start_frame, end_frame),
            sampleBy=1,
        )
        baked = int(end_frame - start_frame + 1)
        message = f"Baked {baked} frames on {object} ({start_frame}–{end_frame})"
    except ImportError:
        # Simulation mode — Maya not available
        baked = int(end_frame - start_frame + 1)
        message = f"[sim] Would bake {baked} frames on {object} ({start_frame}–{end_frame})"

    return {
        "success": True,
        "message": message,
        "data": {"baked_frames": baked},
        "next_actions": ["get_keyframes"],
    }


if __name__ == "__main__":
    import inspect
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
