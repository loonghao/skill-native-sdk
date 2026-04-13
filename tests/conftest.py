"""Shared pytest fixtures and configuration for skill-native-sdk tests."""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ── Repository roots ──────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).parent.parent
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SKILLS_EXAMPLES = REPO_ROOT / "skills" / "examples"
SKN_BIN = REPO_ROOT / "target" / "debug" / ("skn.exe" if sys.platform == "win32" else "skn")


# ── Custom marks ──────────────────────────────────────────────────────────────

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "docker: requires a running Docker daemon (skip with -m 'not docker')",
    )
    config.addinivalue_line(
        "markers",
        "dcc_mock: uses in-process DCC mock interpreter (always available)",
    )


# ── skn binary fixture ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def skn_bin() -> Path:
    """Return path to the compiled skn binary, skip if not built."""
    if not SKN_BIN.exists():
        pytest.skip(f"skn binary not found at {SKN_BIN}. Run: cargo build -p skill-cli --bin skn")
    return SKN_BIN


@pytest.fixture(scope="session")
def skills_dir() -> Path:
    """Return the examples skills directory."""
    return SKILLS_EXAMPLES


# ── DCC mock interpreter fixtures ─────────────────────────────────────────────

def _make_wrapper(tmp_path: Path, mock_script: Path, name: str) -> Path:
    """Create a platform-native wrapper that calls ``python mock_script "$@"``."""
    if sys.platform == "win32":
        wrapper = tmp_path / f"{name}.cmd"
        wrapper.write_text(
            f'@echo off\n"{sys.executable}" "{mock_script}" %*\n',
            encoding="utf-8",
        )
    else:
        wrapper = tmp_path / name
        wrapper.write_text(
            f'#!/bin/sh\nexec "{sys.executable}" "{mock_script}" "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
    return wrapper


@pytest.fixture()
def mayapy_interp(tmp_path: Path) -> Path:
    """Platform wrapper that calls mayapy_mock.py — usable as SKILL.md interpreter."""
    return _make_wrapper(tmp_path, FIXTURES_DIR / "mayapy_mock.py", "mayapy")


@pytest.fixture()
def blender_interp(tmp_path: Path) -> Path:
    """Platform wrapper that calls blender_mock.py — usable as SKILL.md interpreter."""
    return _make_wrapper(tmp_path, FIXTURES_DIR / "blender_mock.py", "blender")


# ── Docker availability ───────────────────────────────────────────────────────

def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=5
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@pytest.fixture(scope="session")
def docker_available() -> bool:
    return _docker_available()


# ── Dynamic SKILL.md factory ──────────────────────────────────────────────────

@pytest.fixture()
def make_skill_md(tmp_path: Path):
    """Return a callable that writes a SKILL.md under tmp_path and returns its dir."""
    def _factory(content: str, subdir: str = "test-skill") -> Path:
        d = tmp_path / subdir
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(content, encoding="utf-8")
        return d
    return _factory
