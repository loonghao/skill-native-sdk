"""mayapy_mock — Autodesk mayapy drop-in for e2e testing.

Usage (mirrors real mayapy):
    mayapy_mock.py  script.py  '{"object":"pCube1","time":24}'

Injects minimal ``maya.cmds`` and ``maya.standalone`` stubs so skill scripts
that do::

    try:
        import maya.standalone
        maya.standalone.initialize()
        import maya.cmds as cmds
        cmds.setKeyframe(...)
    except ImportError:
        ...  # simulation fallback

take the *real* code path rather than the ``[sim]`` fallback, proving the
subprocess → DCC API round-trip works end-to-end.
"""
from __future__ import annotations

import json
import sys
import types


# ── Build maya.cmds stub ──────────────────────────────────────────────────────

def _build_maya_stubs() -> types.ModuleType:
    """Return a ``maya`` module whose ``cmds`` sub-module has animation stubs."""
    maya_mod = types.ModuleType("maya")
    cmds_mod = types.ModuleType("maya.cmds")

    _store: dict[tuple[str, str], list[float]] = {}

    def setKeyframe(obj: str, attribute: str = "translateX",
                    time: float = 0.0, **_kw: object) -> list[float]:
        key = (obj, attribute)
        _store.setdefault(key, []).append(float(time))
        return [float(time)]

    def keyframe(obj: str, query: bool = False,
                 timeChange: bool = False, **_kw: object) -> list[float]:
        times: list[float] = []
        for (o, _), frames in _store.items():
            if o == obj:
                times.extend(frames)
        return sorted(set(times)) if times else [1.0, 12.0, 24.0]

    def bakeResults(obj: str, simulation: bool = True,
                    time: tuple[float, float] = (1.0, 24.0),
                    sampleBy: int = 1, **_kw: object) -> bool:
        start, end = time
        attr_key = (obj, "translateX")
        for f in range(int(start), int(end) + 1, int(sampleBy)):
            _store.setdefault(attr_key, []).append(float(f))
        return True

    cmds_mod.setKeyframe = setKeyframe   # type: ignore[attr-defined]
    cmds_mod.keyframe = keyframe         # type: ignore[attr-defined]
    cmds_mod.bakeResults = bakeResults   # type: ignore[attr-defined]

    maya_mod.cmds = cmds_mod             # type: ignore[attr-defined]
    return maya_mod


def _build_standalone_stub(maya_mod: types.ModuleType) -> types.ModuleType:
    """Return a ``maya.standalone`` stub that satisfies initialize() calls."""
    standalone_mod = types.ModuleType("maya.standalone")

    def initialize(name: str = "python") -> None:  # noqa: ARG001
        """No-op: standalone is already "initialized" in mock mode."""

    def uninitialize() -> None:
        """No-op."""

    standalone_mod.initialize = initialize       # type: ignore[attr-defined]
    standalone_mod.uninitialize = uninitialize   # type: ignore[attr-defined]
    maya_mod.standalone = standalone_mod         # type: ignore[attr-defined]
    return standalone_mod


# ── Inject stubs ──────────────────────────────────────────────────────────────

_maya = _build_maya_stubs()
_standalone = _build_standalone_stub(_maya)
sys.modules["maya"] = _maya
sys.modules["maya.cmds"] = _maya.cmds            # type: ignore[attr-defined]
sys.modules["maya.standalone"] = _standalone

# ── Execute target script ─────────────────────────────────────────────────────

if len(sys.argv) < 2:
    print(json.dumps({"success": False, "error": "Usage: mayapy_mock.py script.py [params_json]"}))
    sys.exit(1)

script_path = sys.argv[1]
# Rewrite sys.argv so the target script sees [script_path, params_json, ...]
sys.argv = sys.argv[1:]

with open(script_path, encoding="utf-8") as _f:
    _code = compile(_f.read(), script_path, "exec")

exec(_code, {"__name__": "__main__", "__file__": script_path})  # noqa: S102
