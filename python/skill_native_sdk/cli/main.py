"""skill CLI — thin Python shim that delegates to the Rust implementation.

When the Rust extension (``_skill_native_core``) is present (normal install),
``run_cli`` is just::

    import sys
    from skill_native_sdk._skill_native_core import run_cli
    sys.exit(run_cli(sys.argv))

A stdlib-only fallback is kept for the rare case where the wheel has not been
built yet (e.g. running directly from a source checkout without ``maturin
develop``).
"""
from __future__ import annotations

import sys

# ---------------------------------------------------------------------------
# Attempt to use the fast Rust implementation first
# ---------------------------------------------------------------------------
try:
    from .._skill_native_core import run_cli as _rust_run_cli  # type: ignore[import]
    _RUST_CLI = True
except ImportError:
    _RUST_CLI = False


def main() -> None:  # noqa: C901
    """Entry point registered in pyproject.toml ``[project.scripts]``."""
    if _RUST_CLI:
        sys.exit(_rust_run_cli(sys.argv))
    else:
        _stdlib_main()


# ---------------------------------------------------------------------------
# Stdlib fallback (no Rust extension available)
# ---------------------------------------------------------------------------
import argparse  # noqa: E402 (after the fast path)
import json  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import List, Optional  # noqa: E402

from ..executor import SkillExecutor  # noqa: E402
from ..registry import SkillRegistry  # noqa: E402

DEFAULT_SKILLS_DIR = "./skills"

# ── ANSI helpers (stdlib only) ────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def cyan(t: str) -> str:    return _c(t, "36")
def green(t: str) -> str:   return _c(t, "32")
def yellow(t: str) -> str:  return _c(t, "33")
def red(t: str) -> str:     return _c(t, "31")
def dim(t: str) -> str:     return _c(t, "2")
def bold(t: str) -> str:    return _c(t, "1")


def _load_registry(skills_dir: str) -> SkillRegistry:
    p = Path(skills_dir)
    if not p.exists():
        print(red(f"Skills directory not found: {skills_dir}"), file=sys.stderr)
        sys.exit(1)
    return SkillRegistry.from_path(p)


# ── skill list ────────────────────────────────────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    registry = _load_registry(args.skills_dir)
    specs = registry.list(domain=args.domain)
    if not specs:
        print(yellow("No skills found."))
        return
    print(bold(f"\n{'Name':<25} {'Domain':<12} {'Ver':<8} {'Tools':>5}  Description"))
    print("─" * 72)
    for spec in specs:
        print(
            f"{cyan(spec.name):<35} {spec.domain:<12} {spec.version:<8} "
            f"{len(spec.tools):>5}  {spec.description[:40]}"
        )
    print()


# ── skill describe ────────────────────────────────────────────────────────────

def cmd_describe(args: argparse.Namespace) -> None:
    registry = _load_registry(args.skills_dir)
    spec = registry.get(args.skill_name)
    if spec is None:
        print(red(f"Skill not found: {args.skill_name}"), file=sys.stderr)
        sys.exit(1)

    print(f"\n{bold(cyan(spec.name))} v{spec.version} ({spec.domain})")
    print(f"  {spec.description}")
    print(f"  {dim('Tags:')} {', '.join(spec.tags) or 'none'}")
    print(f"  {dim('Runtime:')} {spec.runtime.type} / entry={spec.runtime.entry}")
    print(f"  {dim('Permissions:')} network={spec.permissions.network}  "
          f"filesystem={spec.permissions.filesystem}\n")

    for tool in spec.tools:
        flags: List[str] = []
        if tool.read_only:    flags.append(green("read-only"))
        if tool.destructive:  flags.append(red("destructive"))
        if tool.idempotent:   flags.append(cyan("idempotent"))
        print(f"  {bold('●')} {bold(tool.name)}  {' '.join(flags)}")
        print(f"    {tool.description}")
        if tool.on_success.suggest:
            print(f"    {dim('on_success →')} {tool.on_success.suggest}")
        print()


# ── skill graph ───────────────────────────────────────────────────────────────

def cmd_graph(args: argparse.Namespace) -> None:
    registry = _load_registry(args.skills_dir)
    graph = registry.capability_graph(args.skill_name)
    if not graph:
        print(red(f"Skill not found: {args.skill_name}"), file=sys.stderr)
        sys.exit(1)
    print(json.dumps(graph, indent=2))


# ── skill run ─────────────────────────────────────────────────────────────────

def cmd_run(args: argparse.Namespace) -> None:
    registry = _load_registry(args.skills_dir)
    executor = SkillExecutor(registry)
    params = json.loads(args.params) if args.params else {}
    result = executor.execute(args.skill_name, args.tool_name, params)

    if args.output == "toon":
        print(json.dumps(result.to_toon()))
    elif args.output == "mcp":
        print(json.dumps(result.to_mcp()))
    else:
        print(json.dumps(result.to_dict(), indent=2))

    if not result.success:
        sys.exit(1)


# ── skill chain ───────────────────────────────────────────────────────────────

def cmd_chain(args: argparse.Namespace) -> None:
    registry = _load_registry(args.skills_dir)
    executor = SkillExecutor(registry)
    params = json.loads(args.params) if args.params else {}
    current_tool: Optional[str] = args.entry
    step = 1

    while current_tool:
        print(f"\n{dim(f'Step {step}:')} {bold(args.skill_name)} / {bold(current_tool)}")
        result = executor.execute(args.skill_name, current_tool, params if step == 1 else {})

        if args.output == "toon":
            print(json.dumps(result.to_toon()))
        else:
            print(json.dumps(result.to_dict(), indent=2))

        if not result.success or not args.follow_success:
            break

        spec = registry.get(args.skill_name)
        if spec:
            tool_meta = spec.get_tool(current_tool)
            if tool_meta and tool_meta.on_success.suggest:
                current_tool = tool_meta.on_success.suggest[0]
                step += 1
                continue
        break


# ── Argument parser ───────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="skill",
        description="skill-native-sdk CLI — SKILL.md → anywhere",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    def _add_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument("--skills-dir", "-d", default=DEFAULT_SKILLS_DIR,
                       metavar="DIR", help="Skills root directory")

    # list
    p_list = sub.add_parser("list", help="List available skills")
    _add_dir(p_list)
    p_list.add_argument("--domain", default=None, help="Filter by domain")

    # describe
    p_desc = sub.add_parser("describe", help="Show skill details")
    _add_dir(p_desc)
    p_desc.add_argument("skill_name", metavar="SKILL")

    # graph
    p_graph = sub.add_parser("graph", help="Show capability graph (JSON)")
    _add_dir(p_graph)
    p_graph.add_argument("skill_name", metavar="SKILL")

    # run
    p_run = sub.add_parser("run", help="Execute a skill tool")
    _add_dir(p_run)
    p_run.add_argument("skill_name", metavar="SKILL")
    p_run.add_argument("tool_name", metavar="TOOL")
    p_run.add_argument("--params", "-p", default=None, metavar="JSON")
    p_run.add_argument("--output", "-o", default="json",
                       choices=["json", "toon", "mcp"])

    # chain
    p_chain = sub.add_parser("chain", help="Execute and follow on_success chain")
    _add_dir(p_chain)
    p_chain.add_argument("skill_name", metavar="SKILL")
    p_chain.add_argument("--entry", required=True, metavar="TOOL")
    p_chain.add_argument("--params", "-p", default=None, metavar="JSON")
    p_chain.add_argument("--follow-success", action="store_true")
    p_chain.add_argument("--output", "-o", default="toon",
                         choices=["json", "toon", "mcp"])

    return parser


def _stdlib_main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "list":     cmd_list,
        "describe": cmd_describe,
        "graph":    cmd_graph,
        "run":      cmd_run,
        "chain":    cmd_chain,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
