"""blender_mock — Blender CLI drop-in for e2e testing.

Usage (mirrors: blender --background --python script.py -- params_json):
    blender_mock.py  script.py  '{"output_path":"/tmp/out","file_format":"PNG"}'

Injects a minimal ``bpy`` stub so skill scripts that do::

    try:
        import bpy
        bpy.ops.render.render(write_still=True)
    except ImportError:
        ...  # simulation fallback

take the *real* code path rather than the ``[sim]`` fallback.

Note: when called by SubprocessBridge the interpreter is invoked as
    blender_mock.py  script.py  params_json
(no ``--background --python -- `` flags).  This matches the simple
subprocess form.  For tests that exercise the real Blender CLI arg shape,
see the Docker-based tests.
"""
from __future__ import annotations

import json
import sys
import types


# ── Build bpy stub ────────────────────────────────────────────────────────────

def _build_bpy_stub() -> types.ModuleType:
    bpy = types.ModuleType("bpy")

    # bpy.context.scene.render
    render_settings = types.SimpleNamespace(
        filepath="//render_",
        resolution_x=1920,
        resolution_y=1080,
        engine="CYCLES",
        image_settings=types.SimpleNamespace(file_format="PNG"),
    )
    scene = types.SimpleNamespace(
        name="Scene",
        render=render_settings,
        frame_start=1,
        frame_end=250,
        frame_current=1,
    )
    bpy.context = types.SimpleNamespace(scene=scene)  # type: ignore[attr-defined]

    # bpy.ops.render
    _render_log: list[dict] = []

    def _render(write_still: bool = False, animation: bool = False) -> str:
        entry = {
            "write_still": write_still,
            "animation": animation,
            "filepath": render_settings.filepath,
            "format": render_settings.image_settings.file_format,
        }
        _render_log.append(entry)
        return "FINISHED"

    bpy.ops = types.SimpleNamespace(  # type: ignore[attr-defined]
        render=types.SimpleNamespace(render=_render),
    )

    # bpy.data
    bpy.data = types.SimpleNamespace(scenes=[scene], objects=[])  # type: ignore[attr-defined]

    # Expose the log so scripts can record calls
    bpy._render_log = _render_log  # type: ignore[attr-defined]
    return bpy


# ── Inject stub ───────────────────────────────────────────────────────────────

sys.modules["bpy"] = _build_bpy_stub()

# ── Execute target script ─────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "Usage: blender_mock.py script.py [params_json]"}))
    sys.exit(1)

script_path = sys.argv[1]
sys.argv = sys.argv[1:]

with open(script_path, encoding="utf-8") as _f:
    _code = compile(_f.read(), script_path, "exec")

exec(_code, {"__name__": "__main__", "__file__": script_path})  # noqa: S102
