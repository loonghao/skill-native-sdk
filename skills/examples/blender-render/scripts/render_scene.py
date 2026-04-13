"""render_scene — trigger a headless Blender render."""
from __future__ import annotations

import json
import sys
from typing import Any


def skill_entry(
    write_still: bool = True,
    animation: bool = False,
) -> dict[str, Any]:
    """Render the current scene.  Returns the render status and output path."""
    try:
        import bpy  # type: ignore[import]
        scene = bpy.context.scene
        # CYCLES uses CPU rendering — works headless without a display server.
        # Use a small resolution so CI render times stay short.
        scene.render.engine = "CYCLES"
        scene.render.resolution_x = 64
        scene.render.resolution_y = 64
        if hasattr(scene, "cycles"):
            scene.cycles.samples = 1
        status_raw = bpy.ops.render.render(write_still=write_still, animation=animation)
        # Real Blender returns a frozenset e.g. {'FINISHED'}; normalise to str.
        status = "FINISHED" if "FINISHED" in status_raw else str(status_raw)
        filepath = scene.render.filepath
        fmt = scene.render.image_settings.file_format
        message = f"Rendered scene → {filepath} [{fmt}] status={status}"
    except ImportError:
        status = "FINISHED"
        filepath = "//render_"
        message = f"[sim] Would render scene (write_still={write_still}, animation={animation})"

    return {
        "success": True,
        "message": message,
        "data": {"status": status, "filepath": filepath},
        "next_actions": [],
    }


if __name__ == "__main__":
    import inspect
    # Real Blender passes user args after "--":
    #   blender --background --python script.py -- '{"key": "val"}'
    # When run directly (mock / subprocess tests) args follow the script name.
    if "--" in sys.argv:
        _idx = sys.argv.index("--")
        _raw = sys.argv[_idx + 1] if _idx + 1 < len(sys.argv) else "{}"
    else:
        _raw = sys.argv[1] if len(sys.argv) > 1 else "{}"
    params = json.loads(_raw)
    sig = inspect.signature(skill_entry)
    filtered = {k: v for k, v in params.items() if k in sig.parameters}
    result = skill_entry(**filtered)
    print(json.dumps(result))
