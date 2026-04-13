"""set_render_output — configure Blender render output settings."""
from __future__ import annotations

import json
import sys
from typing import Any


def skill_entry(
    output_path: str,
    file_format: str = "PNG",
    resolution_x: int = 1920,
    resolution_y: int = 1080,
) -> dict[str, Any]:
    """Apply render output settings to the active scene."""
    try:
        import bpy  # type: ignore[import]
        scene = bpy.context.scene
        scene.render.filepath = output_path
        scene.render.image_settings.file_format = file_format
        scene.render.resolution_x = int(resolution_x)
        scene.render.resolution_y = int(resolution_y)
        message = (
            f"Render output set: {output_path} [{file_format}]"
            f" {int(resolution_x)}x{int(resolution_y)}"
        )
    except ImportError:
        message = (
            f"[sim] Would set render output: {output_path} [{file_format}]"
            f" {int(resolution_x)}x{int(resolution_y)}"
        )

    return {
        "success": True,
        "message": message,
        "data": {
            "filepath": output_path,
            "format": file_format,
            "resolution_x": int(resolution_x),
            "resolution_y": int(resolution_y),
        },
        "next_actions": ["render_scene"],
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
