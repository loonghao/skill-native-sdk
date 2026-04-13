"""skill CLI — discover, inspect, and execute skills from the command line."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from ..executor import SkillExecutor
from ..registry import SkillRegistry

app = typer.Typer(
    name="skill",
    help="skill-native-sdk CLI — SKILL.md → anywhere",
    rich_markup_mode="rich",
)
console = Console()

# Default skills directory (can be overridden via --skills-dir option)
DEFAULT_SKILLS_DIR = "./skills"


def _load_registry(skills_dir: str) -> SkillRegistry:
    p = Path(skills_dir)
    if not p.exists():
        rprint(f"[red]Skills directory not found: {skills_dir}[/red]")
        raise typer.Exit(1)
    return SkillRegistry.from_path(p)


# ---------------------------------------------------------------------------
# skill list
# ---------------------------------------------------------------------------

@app.command("list")
def cmd_list(
    skills_dir: str = typer.Option(DEFAULT_SKILLS_DIR, "--skills-dir", "-d", help="Skills root directory"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Filter by domain"),
) -> None:
    """List all available skills."""
    registry = _load_registry(skills_dir)
    specs = registry.list(domain=domain)

    if not specs:
        rprint("[yellow]No skills found.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Available Skills", show_lines=True)
    table.add_column("Name", style="cyan bold")
    table.add_column("Domain", style="magenta")
    table.add_column("Version")
    table.add_column("Tools", justify="right")
    table.add_column("Description")

    for spec in specs:
        table.add_row(spec.name, spec.domain, spec.version, str(len(spec.tools)), spec.description[:60])

    console.print(table)


# ---------------------------------------------------------------------------
# skill describe
# ---------------------------------------------------------------------------

@app.command("describe")
def cmd_describe(
    skill_name: str = typer.Argument(..., help="Skill name"),
    skills_dir: str = typer.Option(DEFAULT_SKILLS_DIR, "--skills-dir", "-d"),
) -> None:
    """Show detailed information about a skill and its tools."""
    registry = _load_registry(skills_dir)
    spec = registry.get(skill_name)
    if spec is None:
        rprint(f"[red]Skill not found: {skill_name}[/red]")
        raise typer.Exit(1)

    rprint(f"\n[bold cyan]{spec.name}[/bold cyan] v{spec.version} ([magenta]{spec.domain}[/magenta])")
    rprint(f"  {spec.description}\n")
    rprint(f"  [dim]Tags:[/dim] {', '.join(spec.tags) or 'none'}")
    rprint(f"  [dim]Runtime:[/dim] {spec.runtime.type} / entry={spec.runtime.entry}")
    rprint(f"  [dim]Permissions:[/dim] network={spec.permissions.network}, "
           f"filesystem={spec.permissions.filesystem}\n")

    for tool in spec.tools:
        safety = []
        if tool.read_only:
            safety.append("[green]read-only[/green]")
        if tool.destructive:
            safety.append("[red]destructive[/red]")
        if tool.idempotent:
            safety.append("[blue]idempotent[/blue]")
        rprint(f"  [bold]● {tool.name}[/bold]  {' '.join(safety)}")
        rprint(f"    {tool.description}")
        if tool.on_success.suggest:
            rprint(f"    [dim]on_success →[/dim] {tool.on_success.suggest}")
        rprint()


# ---------------------------------------------------------------------------
# skill graph
# ---------------------------------------------------------------------------

@app.command("graph")
def cmd_graph(
    skill_name: str = typer.Argument(..., help="Skill name"),
    skills_dir: str = typer.Option(DEFAULT_SKILLS_DIR, "--skills-dir", "-d"),
) -> None:
    """Output the CapabilityGraph for a skill (JSON)."""
    registry = _load_registry(skills_dir)
    graph = registry.capability_graph(skill_name)
    if not graph:
        rprint(f"[red]Skill not found: {skill_name}[/red]")
        raise typer.Exit(1)
    rprint(json.dumps(graph, indent=2))


# ---------------------------------------------------------------------------
# skill run
# ---------------------------------------------------------------------------

@app.command("run")
def cmd_run(
    skill_name: str = typer.Argument(..., help="Skill name"),
    tool_name: str = typer.Argument(..., help="Tool name"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help="JSON params string"),
    output: str = typer.Option("json", "--output", "-o", help="Output format: json|toon|mcp"),
    skills_dir: str = typer.Option(DEFAULT_SKILLS_DIR, "--skills-dir", "-d"),
) -> None:
    """Execute a skill tool."""
    registry = _load_registry(skills_dir)
    executor = SkillExecutor(registry)

    parsed_params: dict = json.loads(params) if params else {}
    result = executor.execute(skill_name, tool_name, parsed_params)

    if output == "toon":
        rprint(json.dumps(result.to_toon()))
    elif output == "mcp":
        rprint(json.dumps(result.to_mcp()))
    else:
        rprint(json.dumps(result.to_dict(), indent=2))

    if not result.success:
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# skill chain
# ---------------------------------------------------------------------------

@app.command("chain")
def cmd_chain(
    skill_name: str = typer.Argument(..., help="Skill name"),
    entry: str = typer.Option(..., "--entry", help="Entry tool name"),
    params: Optional[str] = typer.Option(None, "--params", "-p", help="JSON params for entry tool"),
    follow_success: bool = typer.Option(False, "--follow-success", help="Auto-follow on_success hints"),
    output: str = typer.Option("toon", "--output", "-o"),
    skills_dir: str = typer.Option(DEFAULT_SKILLS_DIR, "--skills-dir", "-d"),
) -> None:
    """Execute a skill tool and optionally follow the on_success chain."""
    registry = _load_registry(skills_dir)
    executor = SkillExecutor(registry)

    parsed_params: dict = json.loads(params) if params else {}
    current_tool = entry
    step = 1

    while current_tool:
        rprint(f"\n[dim]Step {step}:[/dim] [bold]{skill_name} / {current_tool}[/bold]")
        result = executor.execute(skill_name, current_tool, parsed_params if step == 1 else {})

        if output == "toon":
            rprint(result.to_toon())
        else:
            rprint(json.dumps(result.to_dict(), indent=2))

        if not result.success or not follow_success:
            break

        # Follow on_success → take the first suggested next tool
        spec = registry.get(skill_name)
        if spec:
            tool_meta = spec.get_tool(current_tool)
            if tool_meta and tool_meta.on_success.suggest:
                current_tool = tool_meta.on_success.suggest[0]
                step += 1
                continue
        break


if __name__ == "__main__":
    app()
