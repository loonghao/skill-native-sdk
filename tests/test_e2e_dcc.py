"""End-to-end DCC environment tests.

Two layers of tests:

**Mock layer** (``@pytest.mark.dcc_mock``, always runs):
  Uses ``mayapy_mock.py`` / ``blender_mock.py`` as the subprocess interpreter.
  Verifies the full SubprocessBridge → DCC API → ToolResult pipeline without
  any real DCC installation.  The key assertion: ``"[sim]"`` must NOT appear
  in the result message, proving the DCC stub was active.

**Docker layer** (``@pytest.mark.docker``, skipped when Docker is absent):
  Builds the images from ``docker/mayapy/`` and ``docker/blender/`` and runs
  each skill script inside the container, then parses stdout as JSON.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from skill_native_sdk import SkillRegistry
from skill_native_sdk.executor import SkillExecutor

REPO_ROOT = Path(__file__).parent.parent
SKILLS_EXAMPLES = REPO_ROOT / "skills" / "examples"
FIXTURES = Path(__file__).parent / "fixtures"


# ── helpers ───────────────────────────────────────────────────────────────────

def _skill_md(interpreter: str | Path, skill_name: str, domain: str,
              tools_yaml: str, scripts_dir: Path) -> str:
    """Render a SKILL.md string with the given interpreter.

    NOTE: intentionally NOT using textwrap.dedent so that the multi-line
    tools_yaml block (which has its own 0-based indentation) is embedded at
    the correct column-0 level without the dedent stripping going wrong.
    """
    interp = str(interpreter).replace("\\", "/")
    return (
        "---\n"
        f"name: {skill_name}\n"
        f"domain: {domain}\n"
        'version: "1.0.0"\n'
        'description: "E2E test skill"\n'
        f"{tools_yaml}\n"
        "runtime:\n"
        "  type: subprocess\n"
        f'  interpreter: "{interp}"\n'
        "  entry: skill_entry\n"
        "permissions:\n"
        "  network: false\n"
        "  filesystem: none\n"
        "---\n"
    )


MAYA_TOOLS_YAML = textwrap.dedent("""\
    tools:
      - name: set_keyframe
        description: "Set keyframe"
        source_file: scripts/set_keyframe.py
        read_only: false
        on_success:
          suggest: [get_keyframes]
      - name: get_keyframes
        description: "Get keyframes"
        source_file: scripts/get_keyframes.py
        read_only: true
        on_success:
          suggest: []
      - name: bake_simulation
        description: "Bake simulation"
        source_file: scripts/bake_simulation.py
        read_only: false
        on_success:
          suggest: [get_keyframes]
""")

BLENDER_TOOLS_YAML = textwrap.dedent("""\
    tools:
      - name: set_render_output
        description: "Set render output"
        source_file: scripts/set_render_output.py
        read_only: false
        on_success:
          suggest: [render_scene]
      - name: render_scene
        description: "Render scene"
        source_file: scripts/render_scene.py
        read_only: false
        on_success:
          suggest: []
""")


def _copy_scripts(src: Path, dst: Path) -> None:
    """Copy all .py files from src/scripts to dst/scripts."""
    import shutil
    (dst / "scripts").mkdir(parents=True, exist_ok=True)
    for f in (src / "scripts").glob("*.py"):
        shutil.copy(f, dst / "scripts" / f.name)


def _make_executor(tmp_path: Path, interp: Path,
                   skill_name: str, domain: str,
                   tools_yaml: str, src_skill: Path) -> SkillExecutor:
    skill_dir = tmp_path / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    _copy_scripts(src_skill, skill_dir)
    md = _skill_md(str(interp).replace("\\", "/"), skill_name, domain, tools_yaml, skill_dir)
    (skill_dir / "SKILL.md").write_text(md, encoding="utf-8")
    registry = SkillRegistry.from_path(tmp_path)
    return SkillExecutor(registry)



# ══════════════════════════════════════════════════════════════════════════════
# Mock-layer tests — mayapy
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.dcc_mock
class TestMayapyMock:
    """Run maya-animation skill scripts via mayapy_mock (no real Maya needed)."""

    SRC = SKILLS_EXAMPLES / "maya-animation"

    def _exec(self, tmp_path: Path, mayapy_interp: Path) -> SkillExecutor:
        return _make_executor(
            tmp_path, mayapy_interp, "maya-animation", "maya",
            MAYA_TOOLS_YAML, self.SRC,
        )

    def test_set_keyframe_no_sim(self, tmp_path: Path, mayapy_interp: Path) -> None:
        """maya.cmds stub active → message must NOT contain '[sim]'."""
        ex = self._exec(tmp_path, mayapy_interp)
        result = ex.execute("maya-animation", "set_keyframe",
                            {"object": "pCube1", "time": 24})
        assert result.success, result.error
        assert "[sim]" not in result.message, (
            f"Expected real maya.cmds path, got simulation fallback: {result.message}"
        )
        assert "pCube1" in result.message
        assert "24" in result.message

    def test_get_keyframes_returns_data(self, tmp_path: Path, mayapy_interp: Path) -> None:
        ex = self._exec(tmp_path, mayapy_interp)
        result = ex.execute("maya-animation", "get_keyframes", {"object": "pCube1"})
        assert result.success, result.error
        assert result.data is not None
        assert "keyframes" in result.data
        assert isinstance(result.data["keyframes"], list)

    def test_bake_simulation_no_sim(self, tmp_path: Path, mayapy_interp: Path) -> None:
        ex = self._exec(tmp_path, mayapy_interp)
        result = ex.execute("maya-animation", "bake_simulation",
                            {"object": "pCube1", "start_frame": 1, "end_frame": 24})
        assert result.success, result.error
        assert "[sim]" not in result.message
        assert result.data is not None
        assert result.data["baked_frames"] == 24

    def test_chain_set_then_get_via_skn(
        self, tmp_path: Path, mayapy_interp: Path, skn_bin: Path
    ) -> None:
        """Full chain: set_keyframe → get_keyframes via the skn binary."""
        skill_dir = tmp_path / "maya-animation"
        skill_dir.mkdir(parents=True, exist_ok=True)
        _copy_scripts(self.SRC, skill_dir)
        md = _skill_md(mayapy_interp, "maya-animation", "maya", MAYA_TOOLS_YAML, skill_dir)
        (skill_dir / "SKILL.md").write_text(md, encoding="utf-8")

        proc = subprocess.run(
            [str(skn_bin), "chain", "maya-animation",
             "--entry", "set_keyframe",
             "--params", '{"object":"pSphere1","time":48}',
             "--follow-success", "--output", "toon",
             "--skills-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        # toon format emits one compact JSON object per line
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        assert len(lines) >= 2, f"Expected ≥2 JSON results, got:\n{proc.stdout}"
        step1 = json.loads(lines[0])
        step2 = json.loads(lines[1])
        assert step1["ok"], step1          # toon format uses "ok"
        assert "[sim]" not in step1.get("msg", "")
        assert step2["ok"], step2


# ══════════════════════════════════════════════════════════════════════════════
# Mock-layer tests — blender
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.dcc_mock
class TestBlenderMock:
    """Run blender-render skill scripts via blender_mock (no real Blender needed)."""

    SRC = SKILLS_EXAMPLES / "blender-render"

    def _exec(self, tmp_path: Path, blender_interp: Path) -> SkillExecutor:
        return _make_executor(
            tmp_path, blender_interp, "blender-render", "blender",
            BLENDER_TOOLS_YAML, self.SRC,
        )

    def test_set_render_output_no_sim(self, tmp_path: Path, blender_interp: Path) -> None:
        """bpy stub active → message must NOT contain '[sim]'."""
        ex = self._exec(tmp_path, blender_interp)
        result = ex.execute("blender-render", "set_render_output",
                            {"output_path": "/tmp/render/", "file_format": "PNG"})
        assert result.success, result.error
        assert "[sim]" not in result.message, (
            f"Expected real bpy path, got simulation fallback: {result.message}"
        )
        assert result.data is not None
        assert result.data["format"] == "PNG"

    def test_render_scene_no_sim(self, tmp_path: Path, blender_interp: Path) -> None:
        ex = self._exec(tmp_path, blender_interp)
        result = ex.execute("blender-render", "render_scene", {"write_still": True})
        assert result.success, result.error
        assert "[sim]" not in result.message
        assert result.data is not None
        assert result.data["status"] == "FINISHED"

    def test_chain_set_then_render_via_skn(
        self, tmp_path: Path, blender_interp: Path, skn_bin: Path
    ) -> None:
        """Full chain: set_render_output → render_scene via the skn binary."""
        skill_dir = tmp_path / "blender-render"
        skill_dir.mkdir(parents=True, exist_ok=True)
        _copy_scripts(self.SRC, skill_dir)
        md = _skill_md(blender_interp, "blender-render", "blender", BLENDER_TOOLS_YAML, skill_dir)
        (skill_dir / "SKILL.md").write_text(md, encoding="utf-8")

        proc = subprocess.run(
            [str(skn_bin), "chain", "blender-render",
             "--entry", "set_render_output",
             "--params", '{"output_path":"/tmp/render/","file_format":"JPEG"}',
             "--follow-success", "--output", "toon",
             "--skills-dir", str(tmp_path)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        lines = [l.strip() for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        assert len(lines) >= 2, f"Expected ≥2 JSON results, got:\n{proc.stdout}"
        step1, step2 = json.loads(lines[0]), json.loads(lines[1])
        assert step1["ok"] and "[sim]" not in step1.get("msg", "")
        assert step2["ok"] and "[sim]" not in step2.get("msg", "")


# ══════════════════════════════════════════════════════════════════════════════
# Docker-layer tests
# ══════════════════════════════════════════════════════════════════════════════

def _docker_run(image: str, script: str, params: dict) -> dict:
    proc = subprocess.run(
        ["docker", "run", "--rm", image, script, json.dumps(params)],
        capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, f"docker run failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip())


@pytest.mark.docker
class TestMayapyDocker:
    IMAGE = "skill-native-sdk-mayapy"

    @pytest.fixture(scope="class", autouse=True)
    def build_image(self, docker_available: bool) -> None:
        if not docker_available:
            pytest.skip("Docker not available")
        r = subprocess.run(
            ["docker", "build", "-t", self.IMAGE, "-f", "docker/mayapy/Dockerfile", "."],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0, f"docker build failed:\n{r.stderr}"

    def test_set_keyframe(self) -> None:
        result = _docker_run(self.IMAGE,
            "/skills/examples/maya-animation/scripts/set_keyframe.py",
            {"object": "pCube1", "time": 24})
        assert result["success"] and "[sim]" not in result["message"]

    def test_get_keyframes(self) -> None:
        result = _docker_run(self.IMAGE,
            "/skills/examples/maya-animation/scripts/get_keyframes.py",
            {"object": "pCube1"})
        assert result["success"]
        assert "keyframes" in result.get("data", {})

    def test_bake_simulation(self) -> None:
        result = _docker_run(self.IMAGE,
            "/skills/examples/maya-animation/scripts/bake_simulation.py",
            {"object": "pCube1", "start_frame": 1, "end_frame": 12})
        assert result["success"] and "[sim]" not in result["message"]
        assert result["data"]["baked_frames"] == 12


@pytest.mark.docker
class TestBlenderDocker:
    IMAGE = "skill-native-sdk-blender"

    @pytest.fixture(scope="class", autouse=True)
    def build_image(self, docker_available: bool) -> None:
        if not docker_available:
            pytest.skip("Docker not available")
        r = subprocess.run(
            ["docker", "build", "-t", self.IMAGE, "-f", "docker/blender/Dockerfile", "."],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        assert r.returncode == 0, f"docker build failed:\n{r.stderr}"

    def test_set_render_output(self) -> None:
        result = _docker_run(self.IMAGE,
            "/skills/examples/blender-render/scripts/set_render_output.py",
            {"output_path": "/tmp/render/", "file_format": "PNG"})
        assert result["success"] and "[sim]" not in result["message"]
        assert result["data"]["format"] == "PNG"

    def test_render_scene(self) -> None:
        result = _docker_run(self.IMAGE,
            "/skills/examples/blender-render/scripts/render_scene.py",
            {"write_still": True})
        assert result["success"] and "[sim]" not in result["message"]
        assert result["data"]["status"] == "FINISHED"
