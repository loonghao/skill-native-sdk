#!/usr/bin/env python3
"""blender_runner.py — thin wrapper that runs a skill script inside real Blender.

Usage (same interface as the old mock entrypoint):
    blender  <script.py>  '<json_params>'

Internally executes:
    /usr/bin/blender --background --python <script.py> -- <json_params>

Blender emits verbose startup messages to stdout.  This wrapper captures the
combined output, locates the **last line that starts with ``{``** (our JSON
result), and prints only that – so callers receive clean JSON regardless of
how chatty Blender is at startup.
"""

from __future__ import annotations

import json
import subprocess
import sys

# Absolute path to the real Blender binary inside the container.
# /usr/local/bin/blender (this wrapper) shadows /usr/bin/blender in PATH,
# so we must reference the real binary explicitly to avoid infinite recursion.
BLENDER_BIN = "/usr/bin/blender"


def main() -> None:
    if len(sys.argv) < 2:
        _fail("Usage: blender <script.py> [params_json]")
        return

    script = sys.argv[1]
    params = sys.argv[2] if len(sys.argv) > 2 else "{}"

    proc = subprocess.run(
        [BLENDER_BIN, "--background", "--python", script, "--", params],
        capture_output=True,
        text=True,
    )

    # Blender writes startup noise to stdout mixed with script output.
    # Find the last line that looks like a JSON object (our result).
    for line in reversed(proc.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            print(line)
            return

    # Nothing found – report failure with diagnostic context.
    stderr_tail = proc.stderr[-400:] if proc.stderr else ""
    _fail(
        f"No JSON output from blender (rc={proc.returncode})",
        stderr=stderr_tail,
    )
    sys.exit(1)


def _fail(msg: str, **extra: object) -> None:
    print(json.dumps({"success": False, "error": msg, **extra}))


if __name__ == "__main__":
    main()
